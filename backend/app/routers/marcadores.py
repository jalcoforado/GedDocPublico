"""Catálogo de marcadores (F5, benchmark SUiTE) — CRUD por tenant.

Mesmo padrão de `TipoManifestante` em `manifestantes.py`: catálogo simples,
soft-delete, sem versionamento. `require_permission("catalogo", ...)` porque
`catalogo` já é a transação usada por outros catálogos do módulo protocolo
(assuntos, tipos de anexo) — não há motivo pra criar uma nova.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.modulos import require_modulo
from ..auth.perms import require_permission
from ..database import get_db, tenant_filter
from ..models import Marcador, Usuario
from ..schemas.marcador import MarcadorCreate, MarcadorOut, MarcadorUpdate
from ._crud import get_or_404

router = APIRouter(tags=["marcadores"])


@router.get(
    "/marcadores",
    response_model=list[MarcadorOut],
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def list_marcadores(
    _: Usuario = Depends(require_permission("catalogo")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[MarcadorOut]:
    stmt = select(Marcador).where(Marcador.excluido.is_(False))
    stmt = tenant_filter(stmt, Marcador, tenant_id).order_by(Marcador.nome)
    return [
        MarcadorOut.model_validate(m) for m in (await db.execute(stmt)).scalars().all()
    ]


@router.post(
    "/marcadores",
    response_model=MarcadorOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_marcador(
    payload: MarcadorCreate,
    _: Usuario = Depends(require_permission("catalogo", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MarcadorOut:
    m = Marcador(**payload.model_dump(), tenant_id=tenant_id, excluido=False)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return MarcadorOut.model_validate(m)


@router.put("/marcadores/{marcador_id}", response_model=MarcadorOut)
async def update_marcador(
    marcador_id: int,
    payload: MarcadorUpdate,
    _: Usuario = Depends(require_permission("catalogo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MarcadorOut:
    m = await get_or_404(db, Marcador, marcador_id, tenant_id=tenant_id, label="Marcador")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    await db.commit()
    await db.refresh(m)
    return MarcadorOut.model_validate(m)


@router.delete("/marcadores/{marcador_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_marcador(
    marcador_id: int,
    _: Usuario = Depends(require_permission("catalogo", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    m = await get_or_404(db, Marcador, marcador_id, tenant_id=tenant_id, label="Marcador")
    m.excluido = True
    await db.commit()
