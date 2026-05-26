from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..database import get_db
from ..models import Bairro, Cidade, Endereco, Estado, Usuario
from ..schemas.common import Paginated
from ..schemas.localizacao import (
    BairroCreate,
    BairroOut,
    BairroUpdate,
    CidadeCreate,
    CidadeOut,
    CidadeUpdate,
    EnderecoCreate,
    EnderecoOut,
    EnderecoUpdate,
    EstadoOut,
)
from ._crud import get_or_404, paginated_list

router = APIRouter(tags=["localizacao"])


# --- Estado (read only, catálogo GLOBAL) -------------------------------------
@router.get("/estados", response_model=list[EstadoOut])
async def list_estados(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EstadoOut]:
    stmt = select(Estado).where(Estado.excluido.is_(False)).order_by(Estado.uf)
    return [EstadoOut.model_validate(e) for e in (await db.execute(stmt)).scalars().all()]


# --- Cidade (catálogo GLOBAL — IBGE) -----------------------------------------
@router.get("/cidades", response_model=Paginated[CidadeOut])
async def list_cidades(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    id_estado: int | None = None,
):
    extra = Cidade.id_estado == id_estado if id_estado else None
    return await paginated_list(
        db,
        Cidade,
        tenant_id=None,
        out_model=CidadeOut,
        page=page,
        page_size=page_size,
        q=q,
        search_fields=[Cidade.cidade],
        order_by=Cidade.cidade,
        extra_filter=extra,
    )


@router.post("/cidades", response_model=CidadeOut, status_code=status.HTTP_201_CREATED)
async def create_cidade(
    payload: CidadeCreate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    c = Cidade(**payload.model_dump(), excluido=False)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return CidadeOut.model_validate(c)


@router.put("/cidades/{cidade_id}", response_model=CidadeOut)
async def update_cidade(
    cidade_id: int,
    payload: CidadeUpdate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    c = await get_or_404(db, Cidade, cidade_id, tenant_id=None, label="Cidade")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    await db.commit()
    await db.refresh(c)
    return CidadeOut.model_validate(c)


@router.delete("/cidades/{cidade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cidade(
    cidade_id: int,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    c = await get_or_404(db, Cidade, cidade_id, tenant_id=None, label="Cidade")
    c.excluido = True
    await db.commit()


# --- Bairro (catálogo GLOBAL) ------------------------------------------------
@router.get("/bairros", response_model=Paginated[BairroOut])
async def list_bairros(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    id_cidade: int | None = None,
):
    extra = Bairro.id_cidade == id_cidade if id_cidade else None
    return await paginated_list(
        db,
        Bairro,
        tenant_id=None,
        out_model=BairroOut,
        page=page,
        page_size=page_size,
        q=q,
        search_fields=[Bairro.bairro],
        order_by=Bairro.bairro,
        extra_filter=extra,
    )


@router.post("/bairros", response_model=BairroOut, status_code=status.HTTP_201_CREATED)
async def create_bairro(
    payload: BairroCreate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    b = Bairro(**payload.model_dump(), excluido=False)
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return BairroOut.model_validate(b)


@router.put("/bairros/{bairro_id}", response_model=BairroOut)
async def update_bairro(
    bairro_id: int,
    payload: BairroUpdate,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    b = await get_or_404(db, Bairro, bairro_id, tenant_id=None, label="Bairro")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(b, k, v)
    await db.commit()
    await db.refresh(b)
    return BairroOut.model_validate(b)


@router.delete("/bairros/{bairro_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bairro(
    bairro_id: int,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    b = await get_or_404(db, Bairro, bairro_id, tenant_id=None, label="Bairro")
    b.excluido = True
    await db.commit()


# --- Endereco (TENANTED) -----------------------------------------------------
@router.get("/enderecos", response_model=Paginated[EnderecoOut])
async def list_enderecos(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    id_cidade: int | None = None,
    id_bairro: int | None = None,
):
    extra = None
    if id_cidade:
        extra = Endereco.id_cidade == id_cidade
    if id_bairro:
        c = Endereco.id_bairro == id_bairro
        extra = c if extra is None else (extra) & (c)
    return await paginated_list(
        db,
        Endereco,
        tenant_id=tenant_id,
        out_model=EnderecoOut,
        page=page,
        page_size=page_size,
        q=q,
        search_fields=[Endereco.rua],
        order_by=Endereco.id.desc(),
        extra_filter=extra,
    )


@router.post("/enderecos", response_model=EnderecoOut, status_code=status.HTTP_201_CREATED)
async def create_endereco(
    payload: EnderecoCreate,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    e = Endereco(**payload.model_dump(), tenant_id=tenant_id, excluido=False)
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return EnderecoOut.model_validate(e)


@router.put("/enderecos/{endereco_id}", response_model=EnderecoOut)
async def update_endereco(
    endereco_id: int,
    payload: EnderecoUpdate,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    e = await get_or_404(db, Endereco, endereco_id, tenant_id=tenant_id, label="Endereço")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(e, k, v)
    await db.commit()
    await db.refresh(e)
    return EnderecoOut.model_validate(e)


@router.delete("/enderecos/{endereco_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endereco(
    endereco_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    e = await get_or_404(db, Endereco, endereco_id, tenant_id=tenant_id, label="Endereço")
    e.excluido = True
    await db.commit()
