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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Minuta,
    MinutaHistorico,
    Processo,
    TemplateDocumento,
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
    categoria: str | None = None,
    apenas_ativos: bool = False,
) -> list[TemplateDocumento]:
    stmt = select(TemplateDocumento).where(
        TemplateDocumento.tenant_id == tenant_id,
        TemplateDocumento.excluido.is_(False),
    )
    if categoria is not None:
        stmt = stmt.where(TemplateDocumento.categoria == categoria)
    if apenas_ativos:
        stmt = stmt.where(TemplateDocumento.ativo.is_(True))
    stmt = stmt.order_by(TemplateDocumento.nome)
    return list((await db.execute(stmt)).scalars().all())


def _detectar_placeholders(corpo_html: str) -> list[str]:
    return sorted({m.group(1) for m in ph._TOKEN_RE.finditer(corpo_html)})


async def criar_template(
    db: AsyncSession,
    *,
    tenant_id: int,
    usuario_id: int,
    payload: TemplateDocumentoCreate,
) -> TemplateDocumento:
    await _validar_nome_template_unico(db, tenant_id=tenant_id, nome=payload.nome)
    t = TemplateDocumento(
        tenant_id=tenant_id,
        nome=payload.nome,
        descricao=payload.descricao,
        categoria=payload.categoria,
        corpo_html=payload.corpo_html,
        placeholders_utilizados=_detectar_placeholders(payload.corpo_html),
        ativo=payload.ativo,
        id_usuario_criacao=usuario_id,
        criado_em=_utcnow(),
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


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


async def listar_minutas(
    db: AsyncSession, *, tenant_id: int, processo_id: int
) -> list[Minuta]:
    stmt = (
        select(Minuta)
        .where(
            Minuta.tenant_id == tenant_id,
            Minuta.id_processo == processo_id,
            Minuta.excluido.is_(False),
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


async def criar_minuta(
    db: AsyncSession,
    *,
    tenant_id: int,
    processo_id: int,
    usuario: Usuario,
    payload: MinutaCreate,
) -> Minuta:
    processo = await _obter_processo(db, tenant_id=tenant_id, processo_id=processo_id)

    corpo_html: str | None
    if payload.origem == "google":
        # O documento vive no Google Docs até o import (PR-D). Sem corpo local.
        corpo_html = None
    elif payload.id_template_origem is not None:
        template = await obter_template(
            db, tenant_id=tenant_id, template_id=payload.id_template_origem
        )
        contexto = await ph.build_context(
            db, tenant_id=tenant_id, processo=processo, usuario=usuario
        )
        corpo_html = ph.resolve(template.corpo_html, contexto)
        corpo_html = sanitizar_html(corpo_html)
    else:
        corpo_html = payload.corpo_html or ""
        corpo_html = sanitizar_html(corpo_html)

    agora = _utcnow()
    m = Minuta(
        tenant_id=tenant_id,
        id_processo=processo_id,
        id_template_origem=payload.id_template_origem,
        titulo=payload.titulo,
        origem=payload.origem,
        status="rascunho",
        versao=1,
        corpo_html=corpo_html,
        id_usuario_criacao=usuario.id,
        criado_em=agora,
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
    if m.status != "rascunho":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Apenas minutas em rascunho podem ser finalizadas.",
        )

    if m.origem == "google":
        # Exportar PDF do Google Doc
        pdf_bytes = await _gerar_pdf_minuta_google(
            db, tenant_id=tenant_id, minuta_id=minuta_id, usuario_id=usuario_id, m=m
        )
    else:
        if not (m.corpo_html or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A minuta está vazia — escreva o conteúdo antes de finalizar.",
            )

        corpo_sanitizado = sanitizar_html(m.corpo_html or "")
        pdf_bytes = html_to_pdf_bytes(corpo_sanitizado, titulo=m.titulo, tenant_slug=tenant_slug)

    anexo = await anexos_svc._criar_anexo_from_bytes(
        db,
        m.id_processo,
        content=pdf_bytes,
        filename=f"{m.titulo}.pdf",
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        descricao=m.titulo,
        id_tipo_anexo=None,
        publico=True,
        usuario_id=usuario_id,
        commit=False,
    )
    await db.flush()  # garante anexo.id

    m.status = "finalizada"
    m.id_anexo_final = anexo.id
    m.id_usuario_finalizacao = usuario_id
    m.finalizada_em = _utcnow()
    m.atualizado_em = m.finalizada_em

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
