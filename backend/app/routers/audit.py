"""Endpoint de auditoria — Fase 24.

Lista paginada com filtros por ação, entidade, id_entidade, usuário e
intervalo de datas. JOIN com utils.usuario pra trazer o nome direto.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..database import get_db
from ..models import AuditLog, Usuario
from ..schemas.audit import AuditLogOut, AuditLogPage

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditLogPage)
async def list_audit(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    acao: str | None = Query(None),
    entidade: str | None = Query(None),
    id_entidade: int | None = Query(None),
    id_usuario: int | None = Query(None),
    desde: datetime | None = Query(None),
    ate: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    filters = [AuditLog.tenant_id == tenant_id]
    if acao:
        filters.append(AuditLog.acao.ilike(f"{acao}%"))
    if entidade:
        filters.append(AuditLog.entidade == entidade)
    if id_entidade is not None:
        filters.append(AuditLog.id_entidade == id_entidade)
    if id_usuario is not None:
        filters.append(AuditLog.id_usuario == id_usuario)
    if desde:
        filters.append(AuditLog.criado_em >= desde)
    if ate:
        filters.append(AuditLog.criado_em <= ate)

    cond = and_(*filters)

    total = (
        await db.execute(select(func.count(AuditLog.id)).where(cond))
    ).scalar_one()

    rows = (
        await db.execute(
            select(AuditLog, Usuario.nome)
            .outerjoin(Usuario, Usuario.id == AuditLog.id_usuario)
            .where(cond)
            .order_by(AuditLog.criado_em.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = [
        AuditLogOut(
            id=row[0].id,
            id_usuario=row[0].id_usuario,
            nome_usuario=row[1],
            acao=row[0].acao,
            entidade=row[0].entidade,
            id_entidade=row[0].id_entidade,
            payload=row[0].payload,
            request_id=row[0].request_id,
            ip=row[0].ip,
            criado_em=row[0].criado_em,
        )
        for row in rows
    ]

    return AuditLogPage(items=items, total=int(total), page=page, page_size=page_size)
