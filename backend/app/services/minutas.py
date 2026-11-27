"""Minutas de documento + templates — serviço de domínio (PR-B).

Tenant-scoped, mesmo padrão de `services/transporte_regulado.py`:
- `tenant_id` sempre do caller, nunca do payload.
- Carga por id filtra `tenant_id` (404 cross-tenant).
- Exclusão = soft-delete.

Minuta é mutável apenas enquanto `status='rascunho'`. Cada "salvar rascunho"
incrementa `versao` e grava um snapshot em `minuta_historico` (append-only).
Lock otimista via `versao` (409 se o cliente editou uma versão desatualizada).

A FINALIZAÇÃO (rascunho → PDF → Anexo) é implementada no PR-C.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Minuta,
    MinutaHistorico,
    Processo,
    TemplateDocumento,
    Tenant,
    Usuario,
)
from ..schemas.minuta import (
    MinutaCreate,
    MinutaUpdate,
    TemplateDocumentoCreate,
    TemplateDocumentoUpdate,
)
from . import anexos as anexos_svc
from . import placeholders as ph
from .audit import log as audit_log
from .google_docs_service import GoogleDocsError, GoogleDocsService
from .html_pdf import html_to_pdf_bytes
from .html_sanitizer import sanitizar_html
from .papel_timbrado import papel_timbrado


def _utcnow() -> datetime:
    return datetime.utcnow()


# ============================ Templates =====================================
async def _validar_nome_template_unico(
    db: AsyncSession, *, tenant_id: int, nome: str, excluir_id: int | None = None
) -> None:
    stmt = select(TemplateDocumento.id).where(
        TemplateDocumento.tenant_id == tenant_id,
        TemplateDocumento.nome == nome,
        TemplateDocumento.excluido.is_(False),
    )
    if excluir_id is not None:
        stmt = stmt.where(TemplateDocumento.id != excluir_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um template com o nome '{nome}' neste tenant.",
        )


async def obter_template(
    db: AsyncSession, *, tenant_id: int, template_id: int
) -> TemplateDocumento:
    t = (
        await db.execute(
            select(TemplateDocumento).where(
                TemplateDocumento.id == template_id,
                TemplateDocumento.tenant_id == tenant_id,
                TemplateDocumento.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if t is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template não encontrado"
        )
    return t


async def listar_templates(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_especie_documental: int | None = None,
    id_unidade_trabalho: int | None = None,
    apenas_ativos: bool = False,
) -> list[TemplateDocumento]:
    stmt = select(TemplateDocumento).where(
        TemplateDocumento.tenant_id == tenant_id,
        TemplateDocumento.excluido.is_(False),
    )
    if id_especie_documental is not None:
        stmt = stmt.where(TemplateDocumento.id_especie_documental == id_especie_documental)
    if id_unidade_trabalho is not None:
        stmt = stmt.where(TemplateDocumento.id_unidade_trabalho == id_unidade_trabalho)
    if apenas_ativos:
        stmt = stmt.where(TemplateDocumento.ativo.is_(True))
    stmt = stmt.order_by(TemplateDocumento.nome)
    return list((await db.execute(stmt)).scalars().all())


def _detectar_placeholders(corpo_html: str) -> list[str]:
    return sorted({m.group(1) for m in ph._TOKEN_RE.finditer(corpo_html)})


def _validar_padrao_ativo(*, padrao: bool, ativo: bool) -> None:
    """SI-53 — o padrão vem selecionado ao redigir, e a tela de redigir só lista
    modelo ativo: um padrão inativo seria uma pré-seleção que não aparece."""
    if padrao and not ativo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Um modelo inativo não pode ser o padrão. Ative-o antes.",
        )


async def _desmarcar_padrao(
    db: AsyncSession, *, tenant_id: int, exceto_id: int | None = None
) -> None:
    """Tira a marca de padrão do modelo que a tiver, ANTES de marcar outro —
    o índice único parcial (0143) recusaria dois padrões ao mesmo tempo."""
    stmt = (
        update(TemplateDocumento)
        .where(
            TemplateDocumento.tenant_id == tenant_id,
            TemplateDocumento.padrao.is_(True),
        )
        .values(padrao=False)
    )
    if exceto_id is not None:
        stmt = stmt.where(TemplateDocumento.id != exceto_id)
    await db.execute(stmt)
    await db.flush()


async def criar_template(
    db: AsyncSession,
    *,
    tenant_id: int,
    usuario_id: int,
    payload: TemplateDocumentoCreate,
) -> TemplateDocumento:
    await _validar_nome_template_unico(db, tenant_id=tenant_id, nome=payload.nome)
    _validar_padrao_ativo(padrao=payload.padrao, ativo=payload.ativo)
    if payload.padrao:
        await _desmarcar_padrao(db, tenant_id=tenant_id)
    t = TemplateDocumento(
        tenant_id=tenant_id,
        nome=payload.nome,
        descricao=payload.descricao,
        id_especie_documental=payload.id_especie_documental,
        id_unidade_trabalho=payload.id_unidade_trabalho,
        corpo_html=payload.corpo_html,
        placeholders_utilizados=_detectar_placeholders(payload.corpo_html),
        ativo=payload.ativo,
        padrao=payload.padrao,
        id_usuario_criacao=usuario_id,
        criado_em=_utcnow(),
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


async def clonar_template(
    db: AsyncSession, *, tenant_id: int, template_id: int, usuario_id: int
) -> TemplateDocumento:
    """F10 — clonar como ato de primeira classe, não "criar de novo copiando à
    mão". Nome dedupe automático: "<nome> (cópia)", "<nome> (cópia 2)"... —
    `_validar_nome_template_unico` já existe; só falta tentar até achar um
    nome livre, porque clonar duas vezes o mesmo template é o caso comum
    (rascunho de variação), não um erro do usuário."""
    original = await obter_template(db, tenant_id=tenant_id, template_id=template_id)

    candidato = f"{original.nome} (cópia)"
    sufixo = 2
    while True:
        stmt = select(TemplateDocumento.id).where(
            TemplateDocumento.tenant_id == tenant_id,
            TemplateDocumento.nome == candidato,
            TemplateDocumento.excluido.is_(False),
        )
        if (await db.execute(stmt)).scalar_one_or_none() is None:
            break
        candidato = f"{original.nome} (cópia {sufixo})"
        sufixo += 1

    clone = TemplateDocumento(
        tenant_id=tenant_id,
        nome=candidato,
        descricao=original.descricao,
        id_especie_documental=original.id_especie_documental,
        id_unidade_trabalho=original.id_unidade_trabalho,
        corpo_html=original.corpo_html,
        placeholders_utilizados=original.placeholders_utilizados,
        ativo=original.ativo,
        id_usuario_criacao=usuario_id,
        criado_em=_utcnow(),
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return clone


async def atualizar_template(
    db: AsyncSession,
    *,
    tenant_id: int,
    template_id: int,
    payload: TemplateDocumentoUpdate,
) -> TemplateDocumento:
    t = await obter_template(db, tenant_id=tenant_id, template_id=template_id)
    dados = payload.model_dump(exclude_unset=True)
    if "nome" in dados:
        await _validar_nome_template_unico(
            db, tenant_id=tenant_id, nome=dados["nome"], excluir_id=template_id
        )
    ativo_final = dados.get("ativo", t.ativo)
    if dados.get("padrao"):
        _validar_padrao_ativo(padrao=True, ativo=ativo_final)
        await _desmarcar_padrao(db, tenant_id=tenant_id, exceto_id=template_id)
    elif not ativo_final:
        # Desativar o padrão tira a marca: a prefeitura volta ao
        # "Documento em branco" em vez de ficar com um padrão invisível.
        dados["padrao"] = False
    for campo, valor in dados.items():
        setattr(t, campo, valor)
    if "corpo_html" in dados:
        t.placeholders_utilizados = _detectar_placeholders(t.corpo_html)
    t.atualizado_em = _utcnow()
    await db.commit()
    await db.refresh(t)
    return t


async def excluir_template(
    db: AsyncSession, *, tenant_id: int, template_id: int
) -> None:
    t = await obter_template(db, tenant_id=tenant_id, template_id=template_id)
    t.excluido = True
    t.padrao = False
    t.atualizado_em = _utcnow()
    await db.commit()


# ============================ Minutas =======================================
async def _obter_processo(
    db: AsyncSession, *, tenant_id: int, processo_id: int
) -> Processo:
    p = (
        await db.execute(
            select(Processo).where(
                Processo.id == processo_id,
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado"
        )
    return p


async def obter_minuta(db: AsyncSession, *, tenant_id: int, minuta_id: int) -> Minuta:
    m = (
        await db.execute(
            select(Minuta).where(
                Minuta.id == minuta_id,
                Minuta.tenant_id == tenant_id,
                Minuta.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if m is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Minuta não encontrada"
        )
    return m


async def exigir_acesso_ao_processo(
    db: AsyncSession, *, tenant_id: int, processo_id: int, usuario: Usuario
) -> None:
    """404 se o usuário não alcança o processo (sigilo, ou rascunho de outra
    pessoa) — o guard único de `services/sigilo.py`. Para as rotas de minuta
    que recebem o id do PROCESSO (listar, criar)."""
    from .sigilo import SigiloAcessoError, assert_acesso_processo

    try:
        await assert_acesso_processo(
            db, tenant_id=tenant_id, processo_id=processo_id, usuario=usuario
        )
    except SigiloAcessoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado"
        )


async def obter_minuta_autorizada(
    db: AsyncSession, *, tenant_id: int, minuta_id: int, usuario: Usuario
) -> Minuta:
    """Carrega a minuta SÓ para quem alcança o processo dela (SI-62).

    Até aqui as rotas de minuta filtravam a prefeitura e mais nada: qualquer
    servidor com `processo.atualizar` lia (e editava, finalizava, apagava) a
    minuta de processo sigiloso acima da credencial dele iterando o id — a
    mesma classe do download de anexo que ficou aberto sete meses. A
    minuta é conteúdo do processo, então passa pelo mesmo guard dele.

    O 404 é o MESMO para "não existe", "é de outra prefeitura" e "não pode
    ver": a resposta não confirma a existência. Toda rota com `minuta_id`
    chama isto antes do serviço — `tests/test_guarda_minuta_sigilosa.py`
    reprova a que esquecer, e reprova `obter_minuta` cru em router.
    """
    from .sigilo import SigiloAcessoError, assert_acesso_processo

    m = await obter_minuta(db, tenant_id=tenant_id, minuta_id=minuta_id)
    try:
        await assert_acesso_processo(
            db, tenant_id=tenant_id, processo_id=m.id_processo, usuario=usuario
        )
    except SigiloAcessoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Minuta não encontrada"
        )
    if eh_rascunho_de_despacho_alheio(m, usuario.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Minuta não encontrada"
        )
    return m


def eh_rascunho_de_despacho_alheio(m: Minuta, usuario_id: int) -> bool:
    """SI-62: rascunho de despacho é só de quem escreve — como o rascunho de
    um e-mail. Vale também para super-usuário: é autoria, não grau de acesso
    (mesma decisão do rascunho de processo, SI-16). Depois de concluído, o
    despacho é do processo e todo mundo que vê o processo vê o despacho."""
    return (
        m.finalidade == "despacho"
        and m.status == "rascunho"
        and m.id_usuario_criacao != usuario_id
    )


def _exigir_que_nao_seja_despacho(m: Minuta, acao: str) -> None:
    if m.finalidade == "despacho":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Despacho não se {acao} por aqui: use \"Concluir despacho\", "
                   "que assina e registra o despacho no processo.",
        )


async def listar_minutas(
    db: AsyncSession, *, tenant_id: int, processo_id: int, usuario_id: int
) -> list[Minuta]:
    stmt = (
        select(Minuta)
        .where(
            Minuta.tenant_id == tenant_id,
            Minuta.id_processo == processo_id,
            Minuta.excluido.is_(False),
            # SI-62: rascunho de despacho de outra pessoa não aparece.
            ~(
                (Minuta.finalidade == "despacho")
                & (Minuta.status == "rascunho")
                & (Minuta.id_usuario_criacao != usuario_id)
            ),
        )
        .order_by(Minuta.criado_em.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def listar_historico_minuta(
    db: AsyncSession, *, tenant_id: int, minuta_id: int
) -> list[MinutaHistorico]:
    m = await obter_minuta(db, tenant_id=tenant_id, minuta_id=minuta_id)

    stmt = (
        select(MinutaHistorico)
        .where(
            MinutaHistorico.tenant_id == tenant_id,
            MinutaHistorico.id_minuta == m.id,
        )
        .order_by(MinutaHistorico.versao.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def _alvo_de_versao_http(
    db: AsyncSession, processo_id: int, anexo_id: int, *, tenant_id: int, travar: bool
):
    """`anexos.alvo_de_versao` com os erros já em HTTP (minuta fala HTTP)."""
    try:
        return await anexos_svc.alvo_de_versao(
            db, processo_id, anexo_id, tenant_id=tenant_id, travar=travar
        )
    except anexos_svc.AnexoNaoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except anexos_svc.AnexoConflito as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


async def criar_minuta(
    db: AsyncSession,
    *,
    tenant_id: int,
    processo_id: int,
    usuario: Usuario,
    payload: MinutaCreate,
) -> Minuta:
    processo = await _obter_processo(db, tenant_id=tenant_id, processo_id=processo_id)
    if payload.finalidade == "despacho" and payload.origem != "interno":
        # O conteúdo do despacho vira PDF assinado aqui; no Google Docs ele
        # sairia do sistema antes de ser ato.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Despacho é redigido no editor do sistema, não no Google Docs.",
        )

    # SI-72 — rascunho que vai virar a versão nova de um anexo do processo.
    texto_anterior: str | None = None
    if payload.id_anexo_substitui is not None:
        if payload.finalidade != "documento":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Despacho não é versão de outro documento.",
            )
        anterior = await _alvo_de_versao_http(
            db, processo_id, payload.id_anexo_substitui, tenant_id=tenant_id, travar=False
        )
        origem_anterior = (
            await db.execute(
                select(Minuta.corpo_html).where(
                    Minuta.id_anexo_final == anterior.id,
                    Minuta.tenant_id == tenant_id,
                    Minuta.excluido.is_(False),
                )
            )
        ).scalars().first()
        texto_anterior = origem_anterior

    corpo_html: str | None
    if payload.origem == "google":
        # O documento vive no Google Docs até o import (PR-D). Sem corpo local.
        corpo_html = None
    elif payload.id_template_origem is not None:
        template = await obter_template(
            db, tenant_id=tenant_id, template_id=payload.id_template_origem
        )
        contexto = await ph.build_context(
            db, tenant_id=tenant_id, processo=processo, usuario=usuario,
            destinatario=payload.destinatario,
        )
        corpo_html = ph.resolve(template.corpo_html, contexto)
        corpo_html = sanitizar_html(corpo_html)
    else:
        # Versão nova de documento redigido, sem texto informado: começa do
        # texto da versão anterior — corrigir, não reescrever.
        corpo_html = payload.corpo_html or texto_anterior or ""
        corpo_html = sanitizar_html(corpo_html)

    agora = _utcnow()
    m = Minuta(
        tenant_id=tenant_id,
        id_processo=processo_id,
        id_template_origem=payload.id_template_origem,
        titulo=payload.titulo,
        destinatario=payload.destinatario,
        origem=payload.origem,
        finalidade=payload.finalidade,
        status="rascunho",
        versao=1,
        corpo_html=corpo_html,
        id_usuario_criacao=usuario.id,
        criado_em=agora,
        id_anexo_substitui=payload.id_anexo_substitui,
        motivo_versao=(payload.motivo_versao or "").strip() or None,
    )
    db.add(m)
    await db.flush()

    if corpo_html is not None:
        db.add(
            MinutaHistorico(
                tenant_id=tenant_id,
                id_minuta=m.id,
                versao=1,
                corpo_html=corpo_html,
                id_usuario=usuario.id,
                criado_em=agora,
            )
        )
    await db.commit()
    await db.refresh(m)

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario.id,
        acao="minuta.criada",
        entidade="minuta",
        id_entidade=m.id,
        payload={"id_processo": processo_id},
    )
    await db.commit()

    return m


async def atualizar_minuta(
    db: AsyncSession,
    *,
    tenant_id: int,
    minuta_id: int,
    usuario: Usuario,
    payload: MinutaUpdate,
) -> Minuta:
    m = await obter_minuta(db, tenant_id=tenant_id, minuta_id=minuta_id)
    if m.status != "rascunho":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Minuta finalizada/cancelada não pode ser editada.",
        )
    if payload.versao is not None and payload.versao != m.versao:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A minuta foi alterada por outra pessoa. Recarregue antes de salvar."
            ),
        )

    dados = payload.model_dump(exclude_unset=True, exclude={"versao"})
    corpo_mudou = "corpo_html" in dados and dados["corpo_html"] != m.corpo_html

    if "titulo" in dados:
        m.titulo = dados["titulo"]
    if "destinatario" in dados:
        m.destinatario = dados["destinatario"]
    if "corpo_html" in dados:
        m.corpo_html = sanitizar_html(dados["corpo_html"])

    agora = _utcnow()
    m.atualizado_em = agora

    if corpo_mudou:
        m.versao += 1
        db.add(
            MinutaHistorico(
                tenant_id=tenant_id,
                id_minuta=m.id,
                versao=m.versao,
                corpo_html=m.corpo_html or "",
                id_usuario=usuario.id,
                criado_em=agora,
            )
        )
    await db.commit()
    await db.refresh(m)

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario.id,
        acao="minuta.editada",
        entidade="minuta",
        id_entidade=m.id,
        payload={"id_processo": m.id_processo},
    )
    await db.commit()

    return m


async def excluir_minuta(
    db: AsyncSession, *, tenant_id: int, minuta_id: int, usuario_id: int | None = None
) -> None:
    m = await obter_minuta(db, tenant_id=tenant_id, minuta_id=minuta_id)
    if m.status == "finalizada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Minuta finalizada não pode ser excluída (documento oficial gerado).",
        )
    m.excluido = True
    m.atualizado_em = _utcnow()
    await db.commit()

    if usuario_id:
        await audit_log(
            db,
            tenant_id=tenant_id,
            id_usuario=usuario_id,
            acao="minuta.excluida",
            entidade="minuta",
            id_entidade=m.id,
            payload={"id_processo": m.id_processo},
        )
        await db.commit()


async def criar_google_doc_para_minuta(
    db: AsyncSession,
    *,
    tenant_id: int,
    minuta_id: int,
    usuario_id: int,
) -> Minuta:
    """Criar um novo Google Doc para a minuta.

    Args:
        db: Database session.
        tenant_id: Tenant ID (from context).
        minuta_id: ID da minuta.
        usuario_id: ID do usuário solicitante.

    Returns:
        Minuta updated with google_doc_id e google_doc_url.

    Raises:
        HTTPException: Se usuário não tem credenciais Google ou API falhar.
    """
    m = await obter_minuta(db, tenant_id=tenant_id, minuta_id=minuta_id)
    _exigir_que_nao_seja_despacho(m, "leva ao Google Docs")

    if m.status != "rascunho":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Apenas minutas em rascunho podem ser criadas em Google Docs.",
        )

    service = GoogleDocsService()

    try:
        # Obter credenciais do usuário
        cred = await service.obter_credentials_usuario(
            db, tenant_id=tenant_id, usuario_id=usuario_id
        )

        # Criar Google Doc
        result = await service.criar_google_doc(
            db, cred=cred, titulo=m.titulo, corpo_html=m.corpo_html
        )

        # Atualizar minuta com google_doc_id e google_doc_url
        m.google_doc_id = result["google_doc_id"]
        m.google_doc_url = result["google_doc_url"]
        m.id_usuario_google = usuario_id
        m.atualizado_em = _utcnow()

        await db.commit()
        await db.refresh(m)

        await audit_log(
            db,
            tenant_id=tenant_id,
            id_usuario=usuario_id,
            acao="minuta.google_doc_criado",
            entidade="minuta",
            id_entidade=m.id,
            payload={"id_processo": m.id_processo, "google_doc_id": m.google_doc_id},
        )
        await db.commit()

        return m

    except GoogleDocsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao criar Google Doc: {str(e)}",
        )


async def arquivar_google_doc_para_minuta(
    db: AsyncSession,
    *,
    tenant_id: int,
    minuta_id: int,
    usuario_id: int,
) -> None:
    """Arquivar (soft delete) Google Doc da minuta.

    Nota: Minuta record NÃO é deletada; apenas o Google Doc é movido para lixo.

    Args:
        db: Database session.
        tenant_id: Tenant ID (from context).
        minuta_id: ID da minuta.
        usuario_id: ID do usuário solicitante.

    Raises:
        HTTPException: Se minuta não tem google_doc_id ou API falhar.
    """
    m = await obter_minuta(db, tenant_id=tenant_id, minuta_id=minuta_id)

    if not m.google_doc_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Minuta não tem Google Doc para arquivar.",
        )

    service = GoogleDocsService()

    try:
        # Obter credenciais do usuário
        cred = await service.obter_credentials_usuario(
            db, tenant_id=tenant_id, usuario_id=usuario_id
        )

        # Arquivar Google Doc
        await service.arquivar_google_doc(db, cred=cred, google_doc_id=m.google_doc_id)

        # Log audit
        await audit_log(
            db,
            tenant_id=tenant_id,
            id_usuario=usuario_id,
            acao="minuta.google_doc_arquivado",
            entidade="minuta",
            id_entidade=m.id,
            payload={"id_processo": m.id_processo, "google_doc_id": m.google_doc_id},
        )
        await db.commit()

    except GoogleDocsError as e:
        # Log error but don't fail (Google Doc may already be deleted)
        await audit_log(
            db,
            tenant_id=tenant_id,
            id_usuario=usuario_id,
            acao="minuta.google_doc_arquivado_erro",
            entidade="minuta",
            id_entidade=m.id,
            payload={"id_processo": m.id_processo, "erro": str(e)},
        )
        await db.commit()


async def _gerar_pdf_minuta_google(
    db: AsyncSession,
    *,
    tenant_id: int,
    minuta_id: int,
    usuario_id: int,
    m: Minuta,
) -> bytes:
    """Gera PDF a partir de Google Doc.

    Estratégia:
    1. Obtém credenciais OAuth do usuário
    2. Baixa Google Doc como PDF via API
    3. Retorna bytes do PDF

    Raises:
        HTTPException: Se credenciais não encontradas ou API falhar.
    """
    if not m.google_doc_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Doc ID não encontrado na minuta.",
        )

    service = GoogleDocsService()

    try:
        # Obter credenciais do usuário
        cred = await service.obter_credentials_usuario(
            db, tenant_id=tenant_id, usuario_id=usuario_id
        )

        # Exportar Google Doc como PDF
        pdf_bytes = await service.exportar_google_doc_como_pdf(
            db, cred=cred, google_doc_id=m.google_doc_id
        )

        return pdf_bytes

    except GoogleDocsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao finalizar documento Google: {str(e)}",
        )


async def finalizar_minuta(
    db: AsyncSession,
    *,
    tenant_id: int,
    tenant_slug: str,
    minuta_id: int,
    usuario_id: int,
) -> Minuta:
    """Gera o PDF da minuta, cria o Anexo e marca a minuta como finalizada.

    Ponto único de convergência das trilhas interno/Google. Reusa
    `anexos._criar_anexo_from_bytes` (que valida processo ativo + movimentação e
    grava no storage por tenant), com `commit=False` para transação ATÔMICA
    (anexo + status da minuta num só commit). O Anexo resultante é indistinguível
    de um upload manual — carimbo e assinatura v2 funcionam sem alteração.
    """
    m = await obter_minuta(db, tenant_id=tenant_id, minuta_id=minuta_id)
    _exigir_que_nao_seja_despacho(m, "finaliza")
    await virar_anexo_sem_commit(
        db, m, tenant_id=tenant_id, tenant_slug=tenant_slug, usuario_id=usuario_id
    )

    await db.commit()
    await db.refresh(m)

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="minuta.finalizada",
        entidade="minuta",
        id_entidade=m.id,
        payload={"id_processo": m.id_processo},
    )
    await db.commit()

    return m


async def virar_anexo_sem_commit(
    db: AsyncSession,
    m: Minuta,
    *,
    tenant_id: int,
    tenant_slug: str,
    usuario_id: int,
    publico: bool = True,
):
    """Gera o PDF da minuta, cria o Anexo e marca a minuta como finalizada,
    SEM commit — quem chama fecha a transação. Usado pela finalização comum e
    pela conclusão do despacho (SI-62), que precisa do anexo, da assinatura e
    da movimentação na MESMA transação. Devolve o Anexo.

    O anexo nasce ligado a `processo.id_ultima_movimentacao`
    (`anexos._criar_anexo_from_bytes`).

    `publico` decide se o cidadão vê o anexo no portal
    (`cidadao_processos`). A finalização comum mantém o comportamento de
    sempre (True); o despacho nasce interno (False)."""
    if m.status != "rascunho":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Apenas minutas em rascunho podem ser finalizadas.",
        )

    if m.origem == "google":
        # Exportar PDF do Google Doc
        pdf_bytes = await _gerar_pdf_minuta_google(
            db, tenant_id=tenant_id, minuta_id=m.id, usuario_id=usuario_id, m=m
        )
    else:
        if not (m.corpo_html or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A minuta está vazia — escreva o conteúdo antes de finalizar.",
            )

        corpo_sanitizado = sanitizar_html(m.corpo_html or "")
        tenant = (
            await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        ).scalar_one()
        pdf_bytes = html_to_pdf_bytes(
            corpo_sanitizado,
            titulo=m.titulo,
            tenant_slug=tenant_slug,
            timbre=papel_timbrado(tenant),
        )

    if m.id_anexo_substitui is not None:
        # SI-72 — versão redigida: revalida AGORA, com trava (entre criar o
        # rascunho e finalizar, outra versão pode ter chegado — aí 409 e o
        # rascunho fica para ser refeito sobre a vigente).
        anterior = await _alvo_de_versao_http(
            db, m.id_processo, m.id_anexo_substitui, tenant_id=tenant_id, travar=True
        )
        anexo = await anexos_svc.criar_versao_sem_commit(
            db, anterior, m.id_processo,
            content=pdf_bytes, filename=f"{m.titulo}.pdf",
            tenant_id=tenant_id, tenant_slug=tenant_slug, usuario_id=usuario_id,
            motivo=m.motivo_versao, descricao=m.titulo,
        )
    else:
        anexo = await anexos_svc._criar_anexo_from_bytes(
            db,
            m.id_processo,
            content=pdf_bytes,
            filename=f"{m.titulo}.pdf",
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            descricao=m.titulo,
            id_tipo_anexo=None,
            publico=publico,
            usuario_id=usuario_id,
            commit=False,
        )
    await db.flush()  # garante anexo.id

    m.status = "finalizada"
    m.id_anexo_final = anexo.id
    m.id_usuario_finalizacao = usuario_id
    m.finalizada_em = _utcnow()
    m.atualizado_em = m.finalizada_em
    return anexo


async def sincronizar_google_doc_para_minuta(
    db: AsyncSession,
    *,
    tenant_id: int,
    minuta_id: int,
    usuario_id: int,
) -> Minuta:
    """Sincroniza o conteúdo do Google Doc de volta para a Minuta local.
    
    1. Baixa os bytes em formato DOCX da API do Google.
    2. Converte para HTML com formatação, listas, títulos e tabelas (docx_para_html).
    3. Sanitiza o HTML.
    4. Se houver mudanças, atualiza o corpo_html, incrementa a versão e grava histórico.
    """
    from .docx_para_html import docx_para_html

    m = await obter_minuta(db, tenant_id=tenant_id, minuta_id=minuta_id)

    if m.status != "rascunho":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Apenas minutas em rascunho podem ser sincronizadas."
        )

    if not m.google_doc_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A minuta não tem um Google Doc associado."
        )

    service = GoogleDocsService()

    try:
        cred = await service.obter_credentials_usuario(
            db, tenant_id=tenant_id, usuario_id=usuario_id
        )
        docx_bytes = await service.sincronizar_google_doc(
            db, cred=cred, google_doc_id=m.google_doc_id
        )
    except GoogleDocsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao sincronizar do Google Docs: {str(e)}",
        )

    # Formatação, listas, títulos, alinhamento e tabelas (ver docx_para_html);
    # texto sempre escapado, e o resultado ainda passa pelo sanitizador.
    novo_corpo_html = sanitizar_html(docx_para_html(docx_bytes))

    if m.corpo_html != novo_corpo_html:
        m.corpo_html = novo_corpo_html
        m.versao += 1
        m.atualizado_em = _utcnow()

        db.add(
            MinutaHistorico(
                tenant_id=tenant_id,
                id_minuta=m.id,
                versao=m.versao,
                corpo_html=m.corpo_html,
                id_usuario=usuario_id,
                criado_em=m.atualizado_em,
            )
        )
        await db.commit()
        await db.refresh(m)

        await audit_log(
            db,
            tenant_id=tenant_id,
            id_usuario=usuario_id,
            acao="minuta.google_doc_sincronizado",
            entidade="minuta",
            id_entidade=m.id,
            payload={"id_processo": m.id_processo, "versao": m.versao},
        )
        await db.commit()

    return m
