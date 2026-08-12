"""Endpoint organograma — tree de unidades com KPIs por nó."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.organograma import OrganogramaNo
from ..services.organograma import tree as build_tree

router = APIRouter(prefix="/organograma", tags=["organograma"])


@router.get(
    "",
    dependencies=[Depends(require_permission("unidadeTrabalho"))],
    response_model=list[OrganogramaNo],
)
async def get_organograma(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    rows = await build_tree(db, tenant_id=tenant_id)
    return [OrganogramaNo.model_validate(r) for r in rows]
