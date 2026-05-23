from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..database import get_db
from ..models import Grupo, GrupoTransacao, Usuario
from ..schemas.grupo import (
    GrupoCreate,
    GrupoOut,
    GrupoTransacaoOut,
    GrupoTransacoesUpdate,
    GrupoUpdate,
)

router = APIRouter(prefix="/grupos", tags=["grupos"])


@router.get("", response_model=list[GrupoOut])
async def list_grupos(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GrupoOut]:
    stmt = select(Grupo).where(Grupo.excluido.is_(False)).order_by(Grupo.grupo)
    return [GrupoOut.model_validate(g) for g in (await db.execute(stmt)).scalars().all()]


@router.get("/{grupo_id}", response_model=GrupoOut)
async def get_grupo(
    grupo_id: int,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GrupoOut:
    g = (
        await db.execute(
            select(Grupo).where(Grupo.id == grupo_id, Grupo.excluido.is_(False))
        )
    ).scalar_one_or_none()
    if g is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")
    return GrupoOut.model_validate(g)


@router.post("", response_model=GrupoOut, status_code=status.HTTP_201_CREATED)
async def create_grupo(
    payload: GrupoCreate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GrupoOut:
    g = Grupo(**payload.model_dump(), excluido=False)
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return GrupoOut.model_validate(g)


@router.put("/{grupo_id}", response_model=GrupoOut)
async def update_grupo(
    grupo_id: int,
    payload: GrupoUpdate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GrupoOut:
    g = (
        await db.execute(
            select(Grupo).where(Grupo.id == grupo_id, Grupo.excluido.is_(False))
        )
    ).scalar_one_or_none()
    if g is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(g, k, v)
    await db.commit()
    await db.refresh(g)
    return GrupoOut.model_validate(g)


@router.get("/{grupo_id}/transacoes", response_model=list[GrupoTransacaoOut])
async def list_grupo_transacoes(
    grupo_id: int,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GrupoTransacaoOut]:
    stmt = select(GrupoTransacao).where(
        GrupoTransacao.id_grupo == grupo_id, GrupoTransacao.excluido.is_(False)
    )
    return [
        GrupoTransacaoOut.model_validate(gt)
        for gt in (await db.execute(stmt)).scalars().all()
    ]


@router.put("/{grupo_id}/transacoes", response_model=list[GrupoTransacaoOut])
async def set_grupo_transacoes(
    grupo_id: int,
    payload: GrupoTransacoesUpdate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GrupoTransacaoOut]:
    g = (
        await db.execute(
            select(Grupo).where(Grupo.id == grupo_id, Grupo.excluido.is_(False))
        )
    ).scalar_one_or_none()
    if g is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")

    await db.execute(delete(GrupoTransacao).where(GrupoTransacao.id_grupo == grupo_id))
    for t in payload.transacoes:
        db.add(
            GrupoTransacao(
                id_grupo=grupo_id,
                id_transacao=t.id_transacao,
                inserir=t.inserir,
                atualizar=t.atualizar,
                excluir=t.excluir,
                excluido=False,
            )
        )
    await db.commit()

    stmt = select(GrupoTransacao).where(
        GrupoTransacao.id_grupo == grupo_id, GrupoTransacao.excluido.is_(False)
    )
    return [
        GrupoTransacaoOut.model_validate(gt)
        for gt in (await db.execute(stmt)).scalars().all()
    ]
