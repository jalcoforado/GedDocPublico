"""Upload, download e soft-delete de anexos vinculados a processos.

Storage (Fase 14): por tenant em `{tenants_storage_root}/{slug}/anexos/`.
Para anexos legacy (pré Fase 14) que estão em `{uploads_dir}/`, o
`resolve_anexo_path` faz fallback de leitura.

Nome do arquivo no disco: `{anexo_id}.{ext}` — guardado no campo `e_doc`
(unique constraint). O vínculo `protocolos.anexo_processo` requer
`id_movimentacao`; usamos `id_ultima_movimentacao` do processo.
"""
import hashlib

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings, resolve_anexo_path, tenant_anexos_dir
from ..models import Anexo, AnexoProcesso, AssinaturaAnexo, Minuta, Processo, Servico
from .sigilo import SigiloAcessoError, assert_acesso_processo


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
) -> Anexo:
    """Núcleo compartilhado da criação de anexo a partir de bytes em memória.

    Usado tanto pelo upload manual (`upload_anexo`) quanto pela finalização de
    minutas (`services/minutas.finalizar_minuta`, PR-C). Aplica as MESMAS regras
    de negócio (processo ativo, movimentação, documento exigido), grava no storage
    por tenant e cria o vínculo `AnexoProcesso`. Com `commit=False` o caller
    controla a transação (finalização atômica anexo + minuta).
    """
    ext = _ext_of(filename)
    if ext not in ALLOWED_EXTS:
        raise AnexoError(f"Extensão '.{ext}' não permitida")

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

    qtd_paginas = None
    if ext == "pdf":
        try:
            qtd_paginas = content.count(b"/Type /Page") or None
        except Exception:
            qtd_paginas = None

    anexo = Anexo(
        tenant_id=tenant_id,
        id_tipo_anexo=id_tipo_anexo,
        publico=publico,
        id_usuario=usuario_id,
        ativo=True,
        excluido=False,
        descricao=(descricao or filename)[:512],
        qtd_paginas=qtd_paginas,
        documento_exigido_key=documento_exigido_key,
    )
    db.add(anexo)
    await db.flush()

    e_doc = f"{anexo.id}.{ext}"
    anexo.e_doc = e_doc

    # Storage por tenant (Fase 14).
    path = tenant_anexos_dir(tenant_slug) / e_doc
    path.write_bytes(content)

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
    path = resolve_anexo_path(tenant_slug, anexo.e_doc)
    if path is None:
        raise AnexoError(f"Arquivo {anexo.e_doc} não está no storage")
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
    _anexo, path = await get_anexo_path(
        db, anexo_id, tenant_id=tenant_id, tenant_slug=tenant_slug
    )
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
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
