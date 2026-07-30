"""Endpoints REST do motor de notificações — Fase 17.

Hoje cobrem só o canal in_app pro usuário logado. Marcar lida e contar
não-lidas é a fonte do Bell icon no frontend.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..database import get_db
from ..models import Notificacao, Usuario
from ..config import get_settings
from ..schemas.notificacao import (
    MarcarLidasResponse,
    NotificacaoListResponse,
    NotificacaoOut,
    PreferenciaResponse,
    PreferenciaUpdate,
    TelefoneResponse,
    TelefoneUpdate,
    WhatsAppTestRequest,
    WhatsAppTestResponse,
)
from ..services.notificacoes import (
    Destinatario,
    contar_nao_lidas,
    enviar as enviar_notif,
    get_preferencia,
    set_preferencia,
)

router = APIRouter(prefix="/notificacoes", tags=["notificacoes"])


@router.get("/me", response_model=NotificacaoListResponse)
async def listar_minhas(
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    apenas_nao_lidas: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = (
        select(Notificacao)
        .where(
            Notificacao.tenant_id == tenant_id,
            Notificacao.id_usuario == current.id,
            Notificacao.canal == "in_app",
        )
        .order_by(Notificacao.criado_em.desc())
        .limit(limit)
    )
    if apenas_nao_lidas:
        stmt = stmt.where(Notificacao.lido_em.is_(None))

    items = (await db.execute(stmt)).scalars().all()
    nao_lidas = await contar_nao_lidas(db, tenant_id=tenant_id, id_usuario=current.id)
    return NotificacaoListResponse(
        items=[NotificacaoOut.model_validate(n) for n in items],
        nao_lidas=nao_lidas,
    )


@router.post("/{notif_id}/marcar-lida", response_model=NotificacaoOut)
async def marcar_lida(
    notif_id: int,
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    n = (
        await db.execute(
            select(Notificacao).where(
                Notificacao.id == notif_id,
                Notificacao.tenant_id == tenant_id,
                Notificacao.id_usuario == current.id,
            )
        )
    ).scalar_one_or_none()
    if n is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notificação não encontrada"
        )
    if n.lido_em is None:
        n.lido_em = datetime.utcnow()
        await db.commit()
        await db.refresh(n)
    return NotificacaoOut.model_validate(n)


@router.post("/marcar-todas-lidas", response_model=MarcarLidasResponse)
async def marcar_todas_lidas(
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        update(Notificacao)
        .where(
            Notificacao.tenant_id == tenant_id,
            Notificacao.id_usuario == current.id,
            Notificacao.canal == "in_app",
            Notificacao.lido_em.is_(None),
        )
        .values(lido_em=datetime.utcnow())
    )
    await db.commit()
    return MarcarLidasResponse(atualizadas=result.rowcount or 0)


# Fase 17b — preferências do usuário corrente
@router.get("/preferencias", response_model=PreferenciaResponse)
async def get_preferencias(
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    p = await get_preferencia(db, tenant_id=tenant_id, id_usuario=current.id)
    return PreferenciaResponse(**p)


@router.put("/preferencias", response_model=PreferenciaResponse)
async def put_preferencias(
    payload: PreferenciaUpdate,
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    p = await set_preferencia(
        db,
        tenant_id=tenant_id,
        id_usuario=current.id,
        in_app=payload.in_app,
        email=payload.email,
        whatsapp=payload.whatsapp,
    )
    return PreferenciaResponse(**p)


# Fase 16 — telefone do usuário corrente
@router.get("/telefone", response_model=TelefoneResponse)
async def get_telefone(
    current: Usuario = Depends(get_current_user),
):
    return TelefoneResponse(telefone=current.telefone)


@router.put("/telefone", response_model=TelefoneResponse)
async def put_telefone(
    payload: TelefoneUpdate,
    current: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Atualiza telefone do usuário corrente. Aceita None pra limpar.
    Validação de formato (E.164) fica no frontend — o backend só persiste."""
    current.telefone = (payload.telefone or "").strip() or None
    await db.commit()
    return TelefoneResponse(telefone=current.telefone)


@router.post("/whatsapp-test", response_model=WhatsAppTestResponse)
async def whatsapp_test(
    payload: WhatsAppTestRequest,
    # Sem gate de módulo de propósito: notificação não pertence a módulo nenhum
    # (todo este router está em ENDPOINTS_TRANSVERSAIS — quem recebe notificação
    # de protocolo é o mesmo sujeito que recebe de pagamentos), e amarrar este
    # endpoint a `configuracao` faria um tenant sem `administracao` não conseguir
    # validar a própria configuração de WhatsApp. Ver a nota no relatório da
    # Task 8: o que sobra aqui é uma questão de autorização — qualquer usuário
    # autenticado do tenant dispara um envio —, não de modularização.
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Envia mensagem teste pelo driver WhatsApp atual. Útil pra validar
    config Zenvia em prod. Ignora preferências do destinatário (canal único)."""
    settings = get_settings()
    criadas = await enviar_notif(
        db,
        tenant_id=tenant_id,
        destinatarios=[Destinatario(telefone=payload.telefone)],
        canais=["whatsapp"],
        tipo="teste_whatsapp",
        titulo="Teste de WhatsApp",
        mensagem=payload.mensagem,
        prioridade="baixa",
    )
    if not criadas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma notificação criada (telefone inválido?)",
        )
    n = criadas[0]
    return WhatsAppTestResponse(
        id_notificacao=n.id,
        enviado_em=n.enviado_em.isoformat() if n.enviado_em else None,
        erro=n.erro,
        provider=settings.whatsapp_provider,
    )
