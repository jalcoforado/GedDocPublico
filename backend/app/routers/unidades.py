from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db, tenant_filter
from ..models import UnidadeTrabalho, Usuario
from ..schemas.common import Paginated
from ..schemas.unidade import (
    UnidadeTrabalhoCreate,
    UnidadeTrabalhoOut,
    UnidadeTrabalhoUpdate,
)

router = APIRouter(prefix="/unidades-trabalho", tags=["unidades-trabalho"])


@router.get(
    "",
    dependencies=[Depends(require_permission("unidadeTrabalho"))],
    response_model=Paginated[UnidadeTrabalhoOut],
)
async def list_unidades(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str | None = None,
) -> Paginated[UnidadeTrabalhoOut]:
    base = select(UnidadeTrabalho).where(UnidadeTrabalho.excluido.is_(False))
    base = tenant_filter(base, UnidadeTrabalho, tenant_id)
    if q:
        like = f"%{q.lower()}%"
        base = base.where(
            or_(
                func.lower(UnidadeTrabalho.unidade_trabalho).like(like),
                func.lower(UnidadeTrabalho.sigla).like(like),
            )
        )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    stmt = (
        base.order_by(UnidadeTrabalho.unidade_trabalho)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        UnidadeTrabalhoOut.model_validate(u)
        for u in (await db.execute(stmt)).scalars().all()
    ]
    return Paginated(items=items, total=total, page=page, page_size=page_size)


async def _get_unidade_or_404(
    db: AsyncSession, unidade_id: int, tenant_id: int
) -> UnidadeTrabalho:
    u = (
        await db.execute(
            select(UnidadeTrabalho).where(
                UnidadeTrabalho.id == unidade_id,
                UnidadeTrabalho.tenant_id == tenant_id,
                UnidadeTrabalho.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unidade não encontrada")
    return u


@router.get(
    "/{unidade_id}",
    dependencies=[Depends(require_permission("unidadeTrabalho"))],
    response_model=UnidadeTrabalhoOut,
)
async def get_unidade(
    unidade_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> UnidadeTrabalhoOut:
    u = await _get_unidade_or_404(db, unidade_id, tenant_id)
    return UnidadeTrabalhoOut.model_validate(u)


@router.post("", response_model=UnidadeTrabalhoOut, status_code=status.HTTP_201_CREATED)
async def create_unidade(
    payload: UnidadeTrabalhoCreate,
    _: Usuario = Depends(require_permission("unidadeTrabalho", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> UnidadeTrabalhoOut:
    u = UnidadeTrabalho(**payload.model_dump(), tenant_id=tenant_id, excluido=False)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return UnidadeTrabalhoOut.model_validate(u)


async def _validar_sem_ciclo(
    db: AsyncSession,
    *,
    unidade_id: int,
    novo_pai_id: int | None,
    tenant_id: int,
) -> None:
    """Garante que `unidade_id` não fica como ancestral dela mesma se receber
    `novo_pai_id` como pai. Walking ancestor chain to detect cycle.
    """
    if novo_pai_id is None:
        return
    if novo_pai_id == unidade_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uma unidade não pode ser pai de si mesma.",
        )
    cur: int | None = novo_pai_id
    visitados: set[int] = set()
    while cur is not None:
        if cur in visitados:
            # Estrutura já tinha ciclo — aborta walk e aceita (não pioramos)
            return
        visitados.add(cur)
        if cur == unidade_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Não pode mover a unidade para baixo de uma subordinada — "
                    "isso criaria um ciclo na hierarquia."
                ),
            )
        row = await db.execute(
            select(UnidadeTrabalho.id_unidade_pai).where(
                UnidadeTrabalho.id == cur,
                UnidadeTrabalho.tenant_id == tenant_id,
                UnidadeTrabalho.excluido.is_(False),
            )
        )
        cur = row.scalar_one_or_none()


@router.put("/{unidade_id}", response_model=UnidadeTrabalhoOut)
async def update_unidade(
    unidade_id: int,
    payload: UnidadeTrabalhoUpdate,
    _: Usuario = Depends(require_permission("unidadeTrabalho", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> UnidadeTrabalhoOut:
    u = await _get_unidade_or_404(db, unidade_id, tenant_id)
    data = payload.model_dump(exclude_unset=True)
    if "id_unidade_pai" in data and data["id_unidade_pai"] != u.id_unidade_pai:
        await _validar_sem_ciclo(
            db,
            unidade_id=unidade_id,
            novo_pai_id=data["id_unidade_pai"],
            tenant_id=tenant_id,
        )
    for k, v in data.items():
        setattr(u, k, v)
    await db.commit()
    await db.refresh(u)
    return UnidadeTrabalhoOut.model_validate(u)


@router.delete("/{unidade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unidade(
    unidade_id: int,
    _: Usuario = Depends(require_permission("unidadeTrabalho", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    u = await _get_unidade_or_404(db, unidade_id, tenant_id)
    u.excluido = True
    await db.commit()
