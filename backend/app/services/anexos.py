"""Upload, download e soft-delete de anexos vinculados a processos.

Storage (Fase 14): por tenant em `{tenants_storage_root}/{slug}/anexos/`.
Para anexos legacy (pré Fase 14) que estão em `{uploads_dir}/`, o
`resolve_anexo_path` faz fallback de leitura.

O acesso físico passa por `services/storage.py` (`obter_storage()`): hoje o
filesystem local acima, com o mesmo comportamento de antes da abstração.

Nome do arquivo no disco: `{anexo_id}.{ext}` — guardado no campo `e_doc`
(unique constraint). O vínculo `protocolos.anexo_processo` requer
`id_movimentacao`; usamos `id_ultima_movimentacao` do processo.
"""
import hashlib

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Anexo, AnexoProcesso, AssinaturaAnexo, Minuta, Processo, Servico
from . import cota_anexacao
from .sigilo import SigiloAcessoError, assert_acesso_processo
from .storage import obter_storage


class AnexoError(Exception):
    pass


ALLOWED_EXTS = {
    "pdf", "png", "jpg", "jpeg", "gif", "webp", "txt", "csv",
    "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods",
}


def _ext_of(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].strip().lower()[:10]


def contar_paginas_pdf(content: bytes) -> int | None:
    """Páginas do PDF, lidas pela árvore de páginas (pypdf).

    Até o SI-72 a conta era `content.count(b"/Type /Page")`, que também casa
    com o nó `/Type /Pages` da árvore: um PDF de 17 páginas virava 18, e o
    erro se propagava para as "fls." de todo documento seguinte. Em PDF com
    object streams comprimidos a mesma busca contava a menos. A busca textual
    fica só como último recurso, para PDF que o pypdf não consegue abrir, e
    descontando os nós `/Pages`.
    """
    try:
        from io import BytesIO

        from pypdf import PdfReader

        return len(PdfReader(BytesIO(content)).pages) or None
    except Exception:  # noqa: BLE001 — PDF malformado: cai na estimativa
        try:
            n = content.count(b"/Type /Page") - content.count(b"/Type /Pages")
            return n if n > 0 else None
        except Exception:  # noqa: BLE001
            return None


async def _ler_upload(file: UploadFile) -> bytes:
    """Valida nome, extensão e tamanho do arquivo enviado e devolve os bytes.
    Comum ao upload avulso e à versão nova (SI-72)."""
    settings = get_settings()
    if not file.filename:
        raise AnexoError("Arquivo sem nome")
    ext = _ext_of(file.filename)
    if ext not in ALLOWED_EXTS:
        raise AnexoError(f"Extensão '.{ext}' não permitida")
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise AnexoError(f"Arquivo excede {settings.max_upload_size_mb} MB")
    return content


async def upload_anexo(
    db: AsyncSession,
    processo_id: int,
    file: UploadFile,
    *,
    tenant_id: int,
    tenant_slug: str,
    descricao: str | None,
    id_tipo_anexo: int | None,
    publico: bool,
    usuario_id: int | None,
    documento_exigido_key: str | None = None,
) -> Anexo:
    """Recebe um `UploadFile` (upload manual): valida nome/extensão/tamanho e
    delega a criação do anexo ao núcleo `_criar_anexo_from_bytes`."""
    content = await _ler_upload(file)

    return await _criar_anexo_from_bytes(
        db,
        processo_id,
        content=content,
        filename=file.filename,
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        descricao=descricao,
        id_tipo_anexo=id_tipo_anexo,
        publico=publico,
        usuario_id=usuario_id,
        documento_exigido_key=documento_exigido_key,
    )


async def _persistir_arquivo(
    db: AsyncSession,
    *,
    content: bytes,
    filename: str,
    tenant_id: int,
    tenant_slug: str,
    descricao: str | None,
    id_tipo_anexo: int | None,
    publico: bool,
    usuario_id: int | None,
    documento_exigido_key: str | None = None,
    id_anexo_anterior: int | None = None,
    versao: int = 1,
    motivo_versao: str | None = None,
) -> Anexo:
    """Núcleo PURO de persistência: valida extensão, grava o arquivo no storage
    do tenant e cria a linha `Anexo`. NÃO valida processo, NÃO cria vínculo
    `AnexoProcesso` — isso é responsabilidade do caller.

    Extraído de `_criar_anexo_from_bytes` (F2 de pagamentos, Task 5) para que o
    upload ligado a processo e o upload ligado a débito (`services/
    pagamentos_anexos.py`) usem exatamente o mesmo storage/extensão/paginação
    sem duplicar a lógica. `_criar_anexo_from_bytes` continua existindo, com o
    MESMO comportamento de antes, apenas delegando esta parte para cá — não
    comita, sempre foi o caller (`upload_anexo`/`finalizar_minuta`) quem decide.
    """
    ext = _ext_of(filename)
    if ext not in ALLOWED_EXTS:
        raise AnexoError(f"Extensão '.{ext}' não permitida")

    qtd_paginas = contar_paginas_pdf(content) if ext == "pdf" else None

    anexo = Anexo(
        tenant_id=tenant_id,
        id_tipo_anexo=id_tipo_anexo,
        publico=publico,
        id_usuario=usuario_id,
        ativo=True,
        excluido=False,
        descricao=(descricao or filename)[:512],
        qtd_paginas=qtd_paginas,
        tamanho_bytes=len(content),
        documento_exigido_key=documento_exigido_key,
        id_anexo_anterior=id_anexo_anterior,
        versao=versao,
        motivo_versao=motivo_versao,
    )
    db.add(anexo)
    # O flush vem ANTES de gravar no storage: na versão nova (SI-72) é ele que
    # esbarra no índice único da sucessora, e aí nenhum byte fica órfão.
    await db.flush()

    e_doc = f"{anexo.id}.{ext}"
    anexo.e_doc = e_doc

    # Storage por tenant (Fase 14), via abstração (backlog §3.1).
    await obter_storage().put(tenant_slug, e_doc, content)

    return anexo


async def _criar_anexo_from_bytes(
    db: AsyncSession,
    processo_id: int,
    *,
    content: bytes,
    filename: str,
    tenant_id: int,
    tenant_slug: str,
    descricao: str | None,
    id_tipo_anexo: int | None,
    publico: bool,
    usuario_id: int | None,
    documento_exigido_key: str | None = None,
    commit: bool = True,
    id_anexo_principal: int | None = None,
    id_anexo_anterior: int | None = None,
    versao: int = 1,
    motivo_versao: str | None = None,
) -> Anexo:
    """Núcleo compartilhado da criação de anexo a partir de bytes em memória.

    Usado tanto pelo upload manual (`upload_anexo`) quanto pela finalização de
    minutas (`services/minutas.finalizar_minuta`, PR-C). Aplica as MESMAS regras
    de negócio (processo ativo, movimentação, documento exigido), grava no storage
    por tenant e cria o vínculo `AnexoProcesso`. Com `commit=False` o caller
    controla a transação (finalização atômica anexo + minuta).
    """
    processo = (
        await db.execute(
            select(Processo).where(
                Processo.id == processo_id,
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if processo is None:
        raise AnexoError("Processo não encontrado")
    if not processo.ativo:
        raise AnexoError("Processo inativo — não permite anexos")
    if processo.id_ultima_movimentacao is None:
        raise AnexoError("Processo sem movimentação — abra-o antes de anexar")

    # F6 (benchmark SUiTE) — cota de anexação por processo, por sigilo.
    # Checa ANTES de gravar no storage: recusar depois de escrever o arquivo
    # deixaria bytes órfãos no disco sem linha nenhuma apontando pra eles.
    limite = cota_anexacao.limite_bytes(processo.nivel_sigilo)
    usado = await cota_anexacao.usado_bytes(db, processo_id, tenant_id)
    if usado + len(content) > limite:
        limite_mb = limite // (1024 * 1024)
        usado_mb = usado / (1024 * 1024)
        raise AnexoError(
            f"Cota de anexação do processo excedida: {usado_mb:.1f} MB usados de "
            f"{limite_mb} MB (nível '{processo.nivel_sigilo}')."
        )

    # PR 4c — vínculo a item de documento exigido: a key precisa existir em
    # `servico.documentos_exigidos` do serviço vinculado ao processo.
    if documento_exigido_key is not None:
        if processo.id_servico is None:
            raise AnexoError(
                "Este processo não foi aberto por serviço; envio geral apenas."
            )
        servico = (
            await db.execute(
                select(Servico).where(
                    Servico.id == processo.id_servico,
                    Servico.tenant_id == tenant_id,
                    Servico.excluido.is_(False),
                )
            )
        ).scalar_one_or_none()
        docs = (servico.documentos_exigidos if servico else None) or []
        keys_validas = {
            d["key"] for d in docs
            if isinstance(d, dict) and d.get("key")
        }
        if not keys_validas:
            raise AnexoError("Este serviço não exige documentos específicos.")
        if documento_exigido_key not in keys_validas:
            raise AnexoError("Documento exigido inválido para este serviço.")

    anexo = await _persistir_arquivo(
        db,
        content=content,
        filename=filename,
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        descricao=descricao,
        id_tipo_anexo=id_tipo_anexo,
        publico=publico,
        usuario_id=usuario_id,
        documento_exigido_key=documento_exigido_key,
        id_anexo_anterior=id_anexo_anterior,
        versao=versao,
        motivo_versao=motivo_versao,
    )

    next_ordem = (
        await db.execute(
            select(func.coalesce(func.max(AnexoProcesso.ordem), 0) + 1).where(
                AnexoProcesso.id_processo == processo_id,
                AnexoProcesso.tenant_id == tenant_id,
                AnexoProcesso.excluido.is_(False),
            )
        )
    ).scalar_one()

    db.add(
        AnexoProcesso(
            tenant_id=tenant_id,
            id_processo=processo_id,
            id_anexo=anexo.id,
            id_movimentacao=processo.id_ultima_movimentacao,
            id_usuario=usuario_id,
            ordem=next_ordem,
            ativo=True,
            excluido=False,
            anexo_herdado=False,
            id_anexo_principal=id_anexo_principal,
        )
    )

    if commit:
        await db.commit()
        await db.refresh(anexo)
    return anexo


async def get_anexo_path(
    db: AsyncSession,
    anexo_id: int,
    *,
    tenant_id: int,
    tenant_slug: str,
):
    anexo = (
        await db.execute(
            select(Anexo).where(
                Anexo.id == anexo_id,
                Anexo.tenant_id == tenant_id,
                Anexo.excluido.is_(False),
                Anexo.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if anexo is None:
        raise AnexoError("Anexo não encontrado")
    if not anexo.e_doc:
        raise AnexoError("Anexo sem arquivo físico associado")
    storage = obter_storage()
    if not await storage.exists(tenant_slug, anexo.e_doc):
        raise AnexoError(f"Arquivo {anexo.e_doc} não está no storage")
    # `path` é None quando o storage não é local (S3, experimental): quem
    # serve o arquivo cai no `get_stream` do storage em vez de `FileResponse`.
    path = await storage.get_local_path_if_possible(tenant_slug, anexo.e_doc)
    return anexo, path


async def get_anexo_path_autorizado(
    db: AsyncSession,
    anexo_id: int,
    *,
    tenant_id: int,
    tenant_slug: str,
    usuario,
):
    """`get_anexo_path` + checagem de sigilo do processo dono do anexo.

    **É esta função, e não `get_anexo_path`, que endpoint algum deve pular.**
    `get_anexo_path` é o carregador cru: filtra tenant, `excluido` e `ativo`, e
    nada mais. Até 2026-08-05 os dois endpoints que servem conteúdo de anexo
    (`/download` e `/carimbado.pdf`) chamavam o carregador cru direto, então
    qualquer autenticado do tenant baixava o anexo de processo **ultrassecreto**
    iterando `anexo_id` — o processo não aparecia na listagem dele (que filtra
    por `nivel_sigilo`), mas o documento vinha.

    O guard `assert_acesso_processo` já existia e já era usado em quatro
    lugares, inclusive no download **pela via de assinatura**. Só a via direta
    ficou de fora. `tests/test_guarda_anexo_sigiloso.py` reprova quem voltar a
    chamar o carregador cru de dentro de um router.

    Anexo **sem** vínculo utilizável é negado, e isso é deliberado: o único
    caminho de criação (`upload_anexo`) cria o vínculo na mesma transação, então
    um anexo solto ou é resíduo do schema legado ou é vínculo apagado — em
    nenhum dos dois casos há processo cujo sigilo consultar, e negar é a direção
    segura. Medido no banco de dev na data: 16 anexos ativos, 0 sem vínculo.

    **O predicado do vínculo espelha o da listagem** (`processos.py::
    _anexos_do_processo`): `excluido = false` e `desentranhado_em IS NULL`.
    Espelhar não é preciosismo — é a regra que impede que este conserto repita
    o defeito que ele corrige. Anexo **desentranhado** (removido formalmente do
    processo, Fase P6) some da listagem; se o download não filtrasse igual, ele
    continuaria alcançável por id, que é exatamente a forma do defeito original,
    uma camada acima. `AnexoProcesso.ativo` **não** entra, porque a listagem
    também não o usa: divergir aqui esconderia da tela um anexo que o download
    entrega, ou o contrário.

    **Vários vínculos são possíveis** — o schema tem `anexo_herdado`, e as
    tabelas `protocolos.*` são compartilhadas com o legado. Por isso a consulta
    devolve todos e o acesso é concedido se a credencial alcançar **qualquer
    um** deles. É a semântica que casa com a tela: se o anexo aparece na
    listagem de um processo que o usuário pode ver, ele pode baixá-lo. Exigir
    acesso a *todos* negaria download legítimo de processo ostensivo por causa
    de um segundo vínculo que o usuário nem sabe que existe.
    """
    # A autorização vem ANTES de resolver o arquivo, de propósito. Na ordem
    # inversa, um anexo cujo arquivo sumiu do storage responderia "Arquivo X
    # não está no storage" em vez de "não encontrado" — distinguindo, para
    # quem não pode ver o documento, o anexo que existe do que não existe.
    processo_ids = list(
        (
            await db.execute(
                select(AnexoProcesso.id_processo).where(
                    AnexoProcesso.id_anexo == anexo_id,
                    AnexoProcesso.tenant_id == tenant_id,
                    AnexoProcesso.excluido.is_(False),
                    AnexoProcesso.desentranhado_em.is_(None),
                )
            )
        ).scalars()
    )
    if not processo_ids:
        raise SigiloAcessoError("Anexo não encontrado")
    for processo_id in processo_ids:
        try:
            await assert_acesso_processo(
                db, tenant_id=tenant_id, processo_id=processo_id, usuario=usuario
            )
        except SigiloAcessoError:
            continue
        return await get_anexo_path(
            db, anexo_id, tenant_id=tenant_id, tenant_slug=tenant_slug
        )
    raise SigiloAcessoError("Anexo não encontrado")


async def anexo_esta_assinado(
    db: AsyncSession, anexo_id: int, *, tenant_id: int
) -> bool:
    """True se há assinatura concluída (`status='assinada'`) sobre o anexo —
    inclui o legado, cujo backfill marcou `status='assinada'` quando assinado."""
    achou = (
        await db.execute(
            select(AssinaturaAnexo.id).where(
                AssinaturaAnexo.id_anexo == anexo_id,
                AssinaturaAnexo.tenant_id == tenant_id,
                AssinaturaAnexo.status == "assinada",
                AssinaturaAnexo.excluido.is_(False),
            )
        )
    ).first()
    return achou is not None


async def hash_anexo(
    db: AsyncSession, anexo_id: int, *, tenant_id: int, tenant_slug: str
) -> tuple[str, str]:
    """SHA-256 do conteúdo exato do anexo no disco. Retorna (hex, 'sha256')."""
    anexo, _path = await get_anexo_path(
        db, anexo_id, tenant_id=tenant_id, tenant_slug=tenant_slug
    )
    h = hashlib.sha256()
    async for chunk in obter_storage().get_stream(tenant_slug, anexo.e_doc):
        h.update(chunk)
    return h.hexdigest(), "sha256"


async def delete_anexo(
    db: AsyncSession, processo_id: int, anexo_id: int, *, tenant_id: int
) -> None:
    """Soft delete: marca anexo + vínculo como excluído. Mantém arquivo físico."""
    # Imutabilidade (Assinatura v2): anexo assinado não pode ser removido.
    if await anexo_esta_assinado(db, anexo_id, tenant_id=tenant_id):
        raise AnexoError(
            "Anexo possui assinatura e não pode ser excluído. "
            "Gere uma nova versão do documento se precisar alterá-lo."
        )
    anexo = (
        await db.execute(
            select(Anexo).where(
                Anexo.id == anexo_id,
                Anexo.tenant_id == tenant_id,
                Anexo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if anexo is None:
        raise AnexoError("Anexo não encontrado")

    # SI-72: a versão SUBSTITUÍDA é histórico e não sai. A VIGENTE pode ser
    # excluída (arquivo errado enviado por engano), desde que não assinada —
    # checado acima; a anterior volta a ser a vigente, porque a sucessora
    # excluída deixa de contar (`sucessora_de` e o índice único olham só
    # `excluido = false`).
    if await sucessora_de(db, anexo_id, tenant_id=tenant_id) is not None:
        raise AnexoError(
            "Este documento já foi substituído por uma versão posterior e "
            "faz parte do histórico; não pode ser excluído."
        )
    # SI-73: documento com avaliação registrada (aguardando ou decidida) não
    # sai. Excluir a correção "ressuscitaria" a versão devolvida, e excluir a
    # aprovada apagaria do processo o que o avaliador aprovou.
    from .avaliacoes import anexo_tem_avaliacao  # lazy: evita ciclo de import

    if await anexo_tem_avaliacao(db, anexo_id, tenant_id=tenant_id):
        raise AnexoError(
            "Este documento tem avaliação registrada e faz parte do histórico; "
            "não pode ser excluído. Envie uma versão nova se precisar corrigi-lo."
        )

    vinculo = (
        await db.execute(
            select(AnexoProcesso).where(
                AnexoProcesso.id_anexo == anexo_id,
                AnexoProcesso.id_processo == processo_id,
                AnexoProcesso.tenant_id == tenant_id,
                AnexoProcesso.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if vinculo is None:
        raise AnexoError("Anexo não está vinculado a este processo")

    anexo.excluido = True
    anexo.ativo = False
    vinculo.excluido = True

    # Se este anexo foi gerado pela finalização de uma minuta, reverte a minuta
    # para rascunho (limpa o vínculo) para que possa ser reeditada/refinalizada —
    # em vez de deixá-la 'finalizada' apontando para um anexo excluído.
    minuta = (
        await db.execute(
            select(Minuta).where(
                Minuta.id_anexo_final == anexo_id,
                Minuta.tenant_id == tenant_id,
                Minuta.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if minuta is not None:
        minuta.status = "rascunho"
        minuta.id_anexo_final = None
        minuta.id_usuario_finalizacao = None
        minuta.finalizada_em = None

    await db.commit()


# ---------------------------------------------------------------------------
# SI-72 (RF-04 V1) — versão nova de documento
# ---------------------------------------------------------------------------


class AnexoNaoEncontrado(AnexoError):
    """→ 404. Vínculo inexistente, de outro processo ou de outra prefeitura."""


class AnexoConflito(AnexoError):
    """→ 409. O documento existe, mas o estado dele não admite versão nova."""


async def sucessora_de(db: AsyncSession, anexo_id: int, *, tenant_id: int) -> int | None:
    """Id da versão viva que substitui `anexo_id`, ou None se ele é o vigente."""
    return (
        await db.execute(
            select(Anexo.id).where(
                Anexo.id_anexo_anterior == anexo_id,
                Anexo.tenant_id == tenant_id,
                Anexo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()


async def motivo_sem_nova_versao(
    db: AsyncSession, anexo: Anexo, vinculo: AnexoProcesso, *, tenant_id: int
) -> str | None:
    """Por que este documento NÃO aceita versão nova; None quando aceita.

    Fica fora, cada um por um motivo:
    - versão já substituída: só a vigente recebe correção (sem ramificar);
    - herdado de apensamento: o documento pertence a outro processo;
    - arquivo que acompanha outro documento (anexo do despacho, SI-62) e o
      próprio documento principal: a peça é o conjunto, que já foi assinado.

    Documento redigido no sistema ACEITA (desde o SI-72 com versão redigida):
    a versão nova pode ser outro arquivo ou um rascunho com o texto dele.
    """
    from .avaliacoes import anexo_aguarda_avaliacao  # lazy: evita ciclo de import

    if await sucessora_de(db, anexo.id, tenant_id=tenant_id) is not None:
        return "Este documento já foi substituído; envie a correção sobre a versão vigente."
    # SI-73: a avaliação aponta para esta versão exata; corrigir no meio dela
    # deixaria o avaliador decidindo sobre um arquivo que já não vale.
    if await anexo_aguarda_avaliacao(db, anexo.id, tenant_id=tenant_id):
        return "Documento aguardando avaliação: espere a decisão antes de enviar versão nova."
    if vinculo.anexo_herdado:
        return "Documento herdado de processo apensado; corrija-o no processo de origem."
    if vinculo.id_anexo_principal is not None:
        return "Este arquivo acompanha outro documento e não recebe versão própria."
    tem_filhos = (
        await db.execute(
            select(AnexoProcesso.id).where(
                AnexoProcesso.id_anexo_principal == anexo.id,
                AnexoProcesso.tenant_id == tenant_id,
                AnexoProcesso.excluido.is_(False),
            ).limit(1)
        )
    ).first()
    if tem_filhos is not None:
        return "Documento com arquivos vinculados (despacho) não recebe versão nova."
    return None


async def alvo_de_versao(
    db: AsyncSession,
    processo_id: int,
    anexo_id: int,
    *,
    tenant_id: int,
    travar: bool,
) -> Anexo:
    """O anexo que vai receber versão nova, já validado; senão
    `AnexoNaoEncontrado` (404) ou `AnexoConflito` (409).

    Comum ao envio de arquivo e à versão redigida (criação do rascunho e
    finalização). `travar=True` põe FOR UPDATE: dois envios simultâneos sobre a
    mesma versão ficam em fila, e o segundo encontra a sucessora do primeiro.
    """
    from .acoes_processo import _esta_arquivado  # lazy: evita ciclo de import

    stmt = select(Anexo).where(
        Anexo.id == anexo_id,
        Anexo.tenant_id == tenant_id,
        Anexo.excluido.is_(False),
        Anexo.ativo.is_(True),
    )
    if travar:
        stmt = stmt.with_for_update()
    anexo = (await db.execute(stmt)).scalar_one_or_none()
    vinculo = None
    if anexo is not None:
        vinculo = (
            await db.execute(
                select(AnexoProcesso).where(
                    AnexoProcesso.id_anexo == anexo_id,
                    AnexoProcesso.id_processo == processo_id,
                    AnexoProcesso.tenant_id == tenant_id,
                    AnexoProcesso.excluido.is_(False),
                    AnexoProcesso.desentranhado_em.is_(None),
                )
            )
        ).scalar_one_or_none()
    if anexo is None or vinculo is None:
        raise AnexoNaoEncontrado("Documento não encontrado neste processo")

    if await _esta_arquivado(db, processo_id, tenant_id):
        raise AnexoConflito("Processo arquivado: desarquive-o para enviar uma versão nova.")
    motivo_bloqueio = await motivo_sem_nova_versao(db, anexo, vinculo, tenant_id=tenant_id)
    if motivo_bloqueio is not None:
        raise AnexoConflito(motivo_bloqueio)
    return anexo


async def criar_versao_sem_commit(
    db: AsyncSession,
    anterior: Anexo,
    processo_id: int,
    *,
    content: bytes,
    filename: str,
    tenant_id: int,
    tenant_slug: str,
    usuario_id: int,
    motivo: str | None,
    descricao: str | None = None,
) -> Anexo:
    """Cria a versão nova de `anterior` (já validado por `alvo_de_versao`, com
    trava) e registra na auditoria. NÃO comita: o upload comita em seguida; a
    finalização da minuta comita junto com o estado dela.

    Entra NO FIM do processo como qualquer juntada (folha não se renumera) e
    herda tipo, publicidade e documento exigido. Assinatura não passa adiante.
    """
    from .audit import log as audit_log

    motivo = (motivo or "").strip() or None
    nova = await _criar_anexo_from_bytes(
        db,
        processo_id,
        content=content,
        filename=filename,
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        descricao=(descricao or "").strip() or anterior.descricao,
        id_tipo_anexo=anterior.id_tipo_anexo,
        publico=anterior.publico,
        usuario_id=usuario_id,
        documento_exigido_key=anterior.documento_exigido_key,
        commit=False,
        id_anexo_anterior=anterior.id,
        versao=(anterior.versao or 1) + 1,
        motivo_versao=motivo[:1000] if motivo else None,
    )
    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.anexo_nova_versao",
        entidade="processo",
        id_entidade=processo_id,
        payload={
            "id_anexo_anterior": anterior.id,
            "id_anexo": nova.id,
            "versao": nova.versao,
            "descricao_anexo": nova.descricao,
            "motivo": nova.motivo_versao,
        },
    )
    return nova


async def enviar_nova_versao(
    db: AsyncSession,
    processo_id: int,
    anexo_id: int,
    file: UploadFile,
    *,
    tenant_id: int,
    tenant_slug: str,
    usuario_id: int,
    motivo: str | None,
    descricao: str | None = None,
) -> Anexo:
    """Junta ao processo uma versão nova de `anexo_id` (arquivo enviado), sem
    apagar a anterior.

    O guard de sigilo é do router (a autorização vem antes de resolver o
    recurso, CLAUDE.md §Sigilo); aqui ficam as regras do documento.
    """
    anterior = await alvo_de_versao(db, processo_id, anexo_id, tenant_id=tenant_id, travar=True)
    content = await _ler_upload(file)
    nova = await criar_versao_sem_commit(
        db, anterior, processo_id,
        content=content, filename=file.filename,
        tenant_id=tenant_id, tenant_slug=tenant_slug, usuario_id=usuario_id,
        motivo=motivo, descricao=descricao,
    )
    await db.commit()
    await db.refresh(nova)
    return nova


async def versao_substituta(
    db: AsyncSession, anexo_ids: list[int], *, tenant_id: int
) -> dict[int, int]:
    """{id do anexo substituído: número da versão que o substituiu}, só para
    os que têm sucessora viva. Alimenta a faixa "substituído" do carimbo
    (`pdf_carimbo`), no botão Carimbar, no PDF completo e no pré-carimbo."""
    if not anexo_ids:
        return {}
    rows = (
        await db.execute(
            select(Anexo.id_anexo_anterior, Anexo.versao).where(
                Anexo.id_anexo_anterior.in_(anexo_ids),
                Anexo.tenant_id == tenant_id,
                Anexo.excluido.is_(False),
            )
        )
    ).all()
    return {anterior: versao for anterior, versao in rows}
