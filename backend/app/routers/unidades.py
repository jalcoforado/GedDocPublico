from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..database import get_db
from ..models import UnidadeTrabalho, Usuario
from ..schemas.common import Paginated
from ..schemas.unidade import (
    UnidadeTrabalhoCreate,
    UnidadeTrabalhoOut,
    UnidadeTrabalhoUpdate,
)

router = APIRouter(prefix="/unidades-trabalho", tags=["unidades-trabalho"])


@router.get("", response_model=Paginated[UnidadeTrabalhoOut])
async def list_unidades(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str | None = None,
) -> Paginated[UnidadeTrabalhoOut]:
    base = select(UnidadeTrabalho).where(UnidadeTrabalho.excluido.is_(False))
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


@router.get("/{unidade_id}", response_model=UnidadeTrabalhoOut)
async def get_unidade(
    unidade_id: int,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnidadeTrabalhoOut:
    u = (
        await db.execute(
            select(UnidadeTrabalho).where(
                UnidadeTrabalho.id == unidade_id, UnidadeTrabalho.excluido.is_(False)
            )
        )
    ).scalar_one_or_none()
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unidade não encontrada")
    return UnidadeTrabalhoOut.model_validate(u)


@router.post("", response_model=UnidadeTrabalhoOut, status_code=status.HTTP_201_CREATED)
async def create_unidade(
    payload: UnidadeTrabalhoCreate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnidadeTrabalhoOut:
    u = UnidadeTrabalho(**payload.model_dump(), excluido=False)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return UnidadeTrabalhoOut.model_validate(u)


@router.put("/{unidade_id}", response_model=UnidadeTrabalhoOut)
async def update_unidade(
    unidade_id: int,
    payload: UnidadeTrabalhoUpdate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnidadeTrabalhoOut:
    u = (
        await db.execute(
            select(UnidadeTrabalho).where(
                UnidadeTrabalho.id == unidade_id, UnidadeTrabalho.excluido.is_(False)
            )
        )
    ).scalar_one_or_none()
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unidade não encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(u, k, v)
    await db.commit()
    await db.refresh(u)
    return UnidadeTrabalhoOut.model_validate(u)


@router.delete("/{unidade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unidade(
    unidade_id: int,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    u = (
        await db.execute(
            select(UnidadeTrabalho).where(
                UnidadeTrabalho.id == unidade_id, UnidadeTrabalho.excluido.is_(False)
            )
        )
    ).scalar_one_or_none()
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unidade não encontrada")
    u.excluido = True
    await db.commit()
