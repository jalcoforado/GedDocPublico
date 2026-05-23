from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..database import get_db
from ..models import Assunto, AssuntoTipoProcessoTipoAnexo, TipoAnexo, TipoProcesso, Usuario
from ..schemas.assunto import (
    AssuntoCreate,
    AssuntoOut,
    AssuntoTipoAnexoCreate,
    AssuntoTipoAnexoOut,
    AssuntoTipoAnexoUpdate,
    AssuntoUpdate,
    TipoAnexoCreate,
    TipoAnexoOut,
    TipoAnexoUpdate,
    TipoProcessoCreate,
    TipoProcessoOut,
    TipoProcessoUpdate,
)
from ..schemas.common import Paginated
from ._crud import get_or_404, paginated_list

router = APIRouter(tags=["assuntos"])


# --- TipoProcesso -------------------------------------------------------------
@router.get("/tipos-processo", response_model=list[TipoProcessoOut])
async def list_tipos_processo(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(TipoProcesso)
        .where(TipoProcesso.excluido.is_(False))
        .order_by(TipoProcesso.tipo_processo)
    )
    return [TipoProcessoOut.model_validate(t) for t in (await db.execute(stmt)).scalars().all()]


@router.post("/tipos-processo", response_model=TipoProcessoOut, status_code=status.HTTP_201_CREATED)
async def create_tipo_processo(
    payload: TipoProcessoCreate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    t = TipoProcesso(**payload.model_dump(), excluido=False)
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return TipoProcessoOut.model_validate(t)


@router.put("/tipos-processo/{tipo_id}", response_model=TipoProcessoOut)
async def update_tipo_processo(
    tipo_id: int,
    payload: TipoProcessoUpdate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    t = await get_or_404(db, TipoProcesso, tipo_id, label="Tipo de processo")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    await db.commit()
    await db.refresh(t)
    return TipoProcessoOut.model_validate(t)


@router.delete("/tipos-processo/{tipo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tipo_processo(
    tipo_id: int,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    t = await get_or_404(db, TipoProcesso, tipo_id, label="Tipo de processo")
    t.excluido = True
    await db.commit()


# --- Assunto ------------------------------------------------------------------
@router.get("/assuntos", response_model=Paginated[AssuntoOut])
async def list_assuntos(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    id_tipo_processo: int | None = None,
):
    extra = Assunto.id_tipo_processo == id_tipo_processo if id_tipo_processo else None
    return await paginated_list(
        db,
        Assunto,
        out_model=AssuntoOut,
        page=page,
        page_size=page_size,
        q=q,
        search_fields=[Assunto.assunto],
        order_by=Assunto.assunto,
        extra_filter=extra,
    )


@router.post("/assuntos", response_model=AssuntoOut, status_code=status.HTTP_201_CREATED)
async def create_assunto(
    payload: AssuntoCreate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a = Assunto(**payload.model_dump(), excluido=False)
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return AssuntoOut.model_validate(a)


@router.put("/assuntos/{assunto_id}", response_model=AssuntoOut)
async def update_assunto(
    assunto_id: int,
    payload: AssuntoUpdate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a = await get_or_404(db, Assunto, assunto_id, label="Assunto")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    await db.commit()
    await db.refresh(a)
    return AssuntoOut.model_validate(a)


@router.delete("/assuntos/{assunto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assunto(
    assunto_id: int,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a = await get_or_404(db, Assunto, assunto_id, label="Assunto")
    a.excluido = True
    await db.commit()


# --- TipoAnexo ----------------------------------------------------------------
@router.get("/tipos-anexo", response_model=list[TipoAnexoOut])
async def list_tipos_anexo(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(TipoAnexo)
        .where(TipoAnexo.excluido.is_(False))
        .order_by(TipoAnexo.tipo_anexo)
    )
    return [TipoAnexoOut.model_validate(t) for t in (await db.execute(stmt)).scalars().all()]


@router.post("/tipos-anexo", response_model=TipoAnexoOut, status_code=status.HTTP_201_CREATED)
async def create_tipo_anexo(
    payload: TipoAnexoCreate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    t = TipoAnexo(**payload.model_dump(), excluido=False)
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return TipoAnexoOut.model_validate(t)


@router.put("/tipos-anexo/{tipo_id}", response_model=TipoAnexoOut)
async def update_tipo_anexo(
    tipo_id: int,
    payload: TipoAnexoUpdate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    t = await get_or_404(db, TipoAnexo, tipo_id, label="Tipo de anexo")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    await db.commit()
    await db.refresh(t)
    return TipoAnexoOut.model_validate(t)


@router.delete("/tipos-anexo/{tipo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tipo_anexo(
    tipo_id: int,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    t = await get_or_404(db, TipoAnexo, tipo_id, label="Tipo de anexo")
    t.excluido = True
    await db.commit()


# --- AssuntoTipoAnexo (relacionamento) ----------------------------------------
@router.get("/assunto-tipo-anexo", response_model=list[AssuntoTipoAnexoOut])
async def list_assunto_tipo_anexo(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    id_assunto: int | None = None,
    id_tipo_anexo: int | None = None,
):
    stmt = select(AssuntoTipoProcessoTipoAnexo).where(
        AssuntoTipoProcessoTipoAnexo.excluido.is_(False)
    )
    if id_assunto:
        stmt = stmt.where(AssuntoTipoProcessoTipoAnexo.id_assunto == id_assunto)
    if id_tipo_anexo:
        stmt = stmt.where(AssuntoTipoProcessoTipoAnexo.id_tipo_anexo == id_tipo_anexo)
    return [
        AssuntoTipoAnexoOut.model_validate(r)
        for r in (await db.execute(stmt)).scalars().all()
    ]


@router.post(
    "/assunto-tipo-anexo",
    response_model=AssuntoTipoAnexoOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_assunto_tipo_anexo(
    payload: AssuntoTipoAnexoCreate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = AssuntoTipoProcessoTipoAnexo(**payload.model_dump(), excluido=False)
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return AssuntoTipoAnexoOut.model_validate(r)


@router.put("/assunto-tipo-anexo/{rel_id}", response_model=AssuntoTipoAnexoOut)
async def update_assunto_tipo_anexo(
    rel_id: int,
    payload: AssuntoTipoAnexoUpdate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await get_or_404(db, AssuntoTipoProcessoTipoAnexo, rel_id, label="Vínculo")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    await db.commit()
    await db.refresh(r)
    return AssuntoTipoAnexoOut.model_validate(r)


@router.delete("/assunto-tipo-anexo/{rel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assunto_tipo_anexo(
    rel_id: int,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await get_or_404(db, AssuntoTipoProcessoTipoAnexo, rel_id, label="Vínculo")
    r.excluido = True
    await db.commit()
