"""Transporte Regulado — routers de Permissionários e Empresas.

`permissionarios_router` / `empresas_router` (prefixos
`/transporte-regulado/permissionarios` e `/transporte-regulado/empresas`): CRUD
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
    EmpresaCreate,
    EmpresaOut,
    EmpresaUpdate,
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


# ============================ Empresas ======================================
empresas_router = APIRouter(
    prefix="/transporte-regulado/empresas", tags=["transporte-regulado"]
)


@empresas_router.get("", response_model=list[EmpresaOut])
async def list_empresas(
    situacao: str | None = None,
    tipo_servico: str | None = None,
    q: str | None = None,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[EmpresaOut]:
    rows = await tr_svc.listar_empresas(
        db, tenant_id=tenant_id, situacao=situacao, tipo_servico=tipo_servico, q=q
    )
    return [EmpresaOut.model_validate(r) for r in rows]


@empresas_router.get("/{empresa_id}", response_model=EmpresaOut)
async def get_empresa(
    empresa_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> EmpresaOut:
    e = await tr_svc.obter_empresa(db, tenant_id=tenant_id, empresa_id=empresa_id)
    return EmpresaOut.model_validate(e)


@empresas_router.post(
    "", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED
)
async def create_empresa(
    payload: EmpresaCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> EmpresaOut:
    e = await tr_svc.criar_empresa(db, tenant_id=tenant_id, payload=payload)
    return EmpresaOut.model_validate(e)


@empresas_router.put("/{empresa_id}", response_model=EmpresaOut)
async def update_empresa(
    empresa_id: int,
    payload: EmpresaUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> EmpresaOut:
    e = await tr_svc.atualizar_empresa(
        db, tenant_id=tenant_id, empresa_id=empresa_id, payload=payload
    )
    return EmpresaOut.model_validate(e)


@empresas_router.post("/{empresa_id}/inativar", response_model=EmpresaOut)
async def inativar_empresa(
    empresa_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> EmpresaOut:
    e = await tr_svc.set_situacao_empresa(
        db, tenant_id=tenant_id, empresa_id=empresa_id, situacao="inativa"
    )
    return EmpresaOut.model_validate(e)


@empresas_router.post("/{empresa_id}/reativar", response_model=EmpresaOut)
async def reativar_empresa(
    empresa_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> EmpresaOut:
    e = await tr_svc.set_situacao_empresa(
        db, tenant_id=tenant_id, empresa_id=empresa_id, situacao="ativa"
    )
    return EmpresaOut.model_validate(e)


@empresas_router.post("/{empresa_id}/suspender", response_model=EmpresaOut)
async def suspender_empresa(
    empresa_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> EmpresaOut:
    e = await tr_svc.set_situacao_empresa(
        db, tenant_id=tenant_id, empresa_id=empresa_id, situacao="suspensa"
    )
    return EmpresaOut.model_validate(e)


@empresas_router.delete("/{empresa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_empresa(
    empresa_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await tr_svc.excluir_empresa(db, tenant_id=tenant_id, empresa_id=empresa_id)
