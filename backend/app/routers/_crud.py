"""Helper genérico para CRUD repetitivo (Fase 2 + Fase 13a tenant).

Cada endpoint replica o padrão dos routers da Fase 1:
- soft-delete via flag `excluido`
- paginação opcional via `Paginated[T]`
- busca por substring em campos textuais
- escopo por tenant via `tenant_id` (None = catálogo global)
"""
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import tenant_filter


async def paginated_list(
    db: AsyncSession,
    model: Any,
    *,
    tenant_id: int | None,
    out_model: Any,
    page: int,
    page_size: int,
    q: str | None,
    search_fields: list,
    order_by,
    extra_filter=None,
):
    """tenant_id obrigatório: int p/ tabelas tenanted, None p/ catálogos globais.

    Veja `database.tenant_filter` para a regra completa de validação.
    """
    from ..schemas.common import Paginated

    base = select(model).where(model.excluido.is_(False))
    base = tenant_filter(base, model, tenant_id)
    if extra_filter is not None:
        base = base.where(extra_filter)
    if q and search_fields:
        like = f"%{q.lower()}%"
        base = base.where(
            or_(*(func.lower(f).like(like) for f in search_fields))
        )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    stmt = base.order_by(order_by).offset((page - 1) * page_size).limit(page_size)
    items = [out_model.model_validate(r) for r in (await db.execute(stmt)).scalars().all()]
    return Paginated(items=items, total=total, page=page, page_size=page_size)


async def get_or_404(
    db: AsyncSession,
    model: Any,
    item_id: int,
    *,
    tenant_id: int | None,
    label: str,
):
    """tenant_id obrigatório: int p/ tabelas tenanted, None p/ catálogos globais."""
    from fastapi import HTTPException, status

    stmt = select(model).where(model.id == item_id, model.excluido.is_(False))
    stmt = tenant_filter(stmt, model, tenant_id)
    obj = (await db.execute(stmt)).scalar_one_or_none()
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} não encontrado"
        )
    return obj
