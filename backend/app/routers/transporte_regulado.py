"""Transporte Regulado — router do cadastro de Permissionários (fundação).

`permissionarios_router` (prefix `/transporte-regulado/permissionarios`): CRUD
interno, autenticado + permissão `transporte_regulado`. Mesmo padrão dos routers
de `frota`. Sem portal público nesta etapa.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.transporte_regulado import (
    PermissionarioCreate,
    PermissionarioOut,
    PermissionarioUpdate,
)
from ..services import transporte_regulado as tr_svc

permissionarios_router = APIRouter(
    prefix="/transporte-regulado/permissionarios", tags=["transporte-regulado"]
)


@permissionarios_router.get("", response_model=list[PermissionarioOut])
async def list_permissionarios(
    situacao: str | None = None,
    tipo_servico: str | None = None,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[PermissionarioOut]:
    rows = await tr_svc.listar_permissionarios(
        db, tenant_id=tenant_id, situacao=situacao, tipo_servico=tipo_servico
    )
    return [PermissionarioOut.model_validate(r) for r in rows]


@permissionarios_router.get("/{permissionario_id}", response_model=PermissionarioOut)
async def get_permissionario(
    permissionario_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PermissionarioOut:
    p = await tr_svc.obter_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id
    )
    return PermissionarioOut.model_validate(p)


@permissionarios_router.post(
    "", response_model=PermissionarioOut, status_code=status.HTTP_201_CREATED
)
async def create_permissionario(
    payload: PermissionarioCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PermissionarioOut:
    p = await tr_svc.criar_permissionario(db, tenant_id=tenant_id, payload=payload)
    return PermissionarioOut.model_validate(p)


@permissionarios_router.put("/{permissionario_id}", response_model=PermissionarioOut)
async def update_permissionario(
    permissionario_id: int,
    payload: PermissionarioUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PermissionarioOut:
    p = await tr_svc.atualizar_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id, payload=payload
    )
    return PermissionarioOut.model_validate(p)


@permissionarios_router.post(
    "/{permissionario_id}/inativar", response_model=PermissionarioOut
)
async def inativar_permissionario(
    permissionario_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PermissionarioOut:
    p = await tr_svc.set_situacao_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id, situacao="inativo"
    )
    return PermissionarioOut.model_validate(p)


@permissionarios_router.post(
    "/{permissionario_id}/reativar", response_model=PermissionarioOut
)
async def reativar_permissionario(
    permissionario_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PermissionarioOut:
    p = await tr_svc.set_situacao_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id, situacao="ativo"
    )
    return PermissionarioOut.model_validate(p)


@permissionarios_router.post(
    "/{permissionario_id}/suspender", response_model=PermissionarioOut
)
async def suspender_permissionario(
    permissionario_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PermissionarioOut:
    p = await tr_svc.set_situacao_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id, situacao="suspenso"
    )
    return PermissionarioOut.model_validate(p)


@permissionarios_router.delete(
    "/{permissionario_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_permissionario(
    permissionario_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await tr_svc.excluir_permissionario(
        db, tenant_id=tenant_id, permissionario_id=permissionario_id
    )
