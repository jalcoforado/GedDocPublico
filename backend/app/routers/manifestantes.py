from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.modulos import require_modulo
from ..auth.perms import require_permission
from ..database import get_db, tenant_filter
from ..models import Manifestante, TipoManifestante, Usuario
from ..schemas.common import Paginated
from ..schemas.manifestante import (
    ManifestanteCreate,
    ManifestanteOut,
    ManifestanteUpdate,
    TipoManifestanteCreate,
    TipoManifestanteOut,
    TipoManifestanteUpdate,
)
from ._crud import get_or_404, paginated_list

router = APIRouter(tags=["manifestantes"])


# --- TipoManifestante ---------------------------------------------------------
@router.get(
    "/tipos-manifestante",
    response_model=list[TipoManifestanteOut],
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def list_tipos_manifestante(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TipoManifestante).where(TipoManifestante.excluido.is_(False))
    stmt = tenant_filter(stmt, TipoManifestante, tenant_id).order_by(TipoManifestante.tipo_manifestante)
    return [
        TipoManifestanteOut.model_validate(t)
        for t in (await db.execute(stmt)).scalars().all()
    ]


@router.post(
    "/tipos-manifestante",
    response_model=TipoManifestanteOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_tipo_manifestante(
    payload: TipoManifestanteCreate,
    _: Usuario = Depends(require_permission("manifestante", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    t = TipoManifestante(**payload.model_dump(), tenant_id=tenant_id, excluido=False)
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return TipoManifestanteOut.model_validate(t)


@router.put("/tipos-manifestante/{tipo_id}", response_model=TipoManifestanteOut)
async def update_tipo_manifestante(
    tipo_id: int,
    payload: TipoManifestanteUpdate,
    _: Usuario = Depends(require_permission("manifestante", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    t = await get_or_404(db, TipoManifestante, tipo_id, tenant_id=tenant_id, label="Tipo de manifestante")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    await db.commit()
    await db.refresh(t)
    return TipoManifestanteOut.model_validate(t)


@router.delete("/tipos-manifestante/{tipo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tipo_manifestante(
    tipo_id: int,
    _: Usuario = Depends(require_permission("manifestante", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    t = await get_or_404(db, TipoManifestante, tipo_id, tenant_id=tenant_id, label="Tipo de manifestante")
    t.excluido = True
    await db.commit()


# --- Manifestante -------------------------------------------------------------
@router.get(
    "/manifestantes",
    response_model=Paginated[ManifestanteOut],
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("manifestante"))],
)
async def list_manifestantes(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    id_tipo_manifestante: int | None = None,
):
    extra = (
        Manifestante.id_tipo_manifestante == id_tipo_manifestante
        if id_tipo_manifestante
        else None
    )
    return await paginated_list(
        db,
        Manifestante,
        tenant_id=tenant_id,
        out_model=ManifestanteOut,
        page=page,
        page_size=page_size,
        q=q,
        search_fields=[Manifestante.nome, Manifestante.cpf_cnpj, Manifestante.email],
        order_by=Manifestante.nome,
        extra_filter=extra,
    )


@router.post(
    "/manifestantes", response_model=ManifestanteOut, status_code=status.HTTP_201_CREATED
)
async def create_manifestante(
    payload: ManifestanteCreate,
    _: Usuario = Depends(require_permission("manifestante", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    m = Manifestante(**payload.model_dump(), tenant_id=tenant_id, excluido=False)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return ManifestanteOut.model_validate(m)


@router.put("/manifestantes/{manif_id}", response_model=ManifestanteOut)
async def update_manifestante(
    manif_id: int,
    payload: ManifestanteUpdate,
    _: Usuario = Depends(require_permission("manifestante", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    m = await get_or_404(db, Manifestante, manif_id, tenant_id=tenant_id, label="Manifestante")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    await db.commit()
    await db.refresh(m)
    return ManifestanteOut.model_validate(m)


@router.delete("/manifestantes/{manif_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_manifestante(
    manif_id: int,
    _: Usuario = Depends(require_permission("manifestante", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    m = await get_or_404(db, Manifestante, manif_id, tenant_id=tenant_id, label="Manifestante")
    m.excluido = True
    await db.commit()
