"""Endpoints sobre o tenant atual.

- GET  /api/v2/tenants/me            — info pro frontend (branding + institucional)
- PUT  /api/v2/tenants/me            — atualiza dados institucionais (PR 3b)
- GET  /api/v2/tenants/me/onboarding — checklist de configuração inicial (PR 3b)
- PUT  /api/v2/tenants/me/nup-config — config NUP federal (Fase P2)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_tenant, get_current_user, require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Tenant, Usuario
from ..schemas.tenant import (
    OnboardingResponse,
    TenantInstitucionalUpdate,
    TenantMeResponse,
    TenantNupConfigUpdate,
)
from ..services.tenant_config import atualizar_config_institucional, calcular_onboarding

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me", response_model=TenantMeResponse)
async def tenant_me(tenant: Tenant = Depends(get_current_tenant)) -> Tenant:
    return tenant


@router.put("/me", response_model=TenantMeResponse)
async def update_tenant_me(
    payload: TenantInstitucionalUpdate,
    _: Usuario = Depends(require_permission("configuracao", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    # Escopo SEMPRE de request.state.tenant_id (via require_tenant_id) — nunca do
    # corpo. Whitelist de campos institucionais aplicada no serviço.
    return await atualizar_config_institucional(db, tenant_id=tenant_id, payload=payload)


@router.get("/me/onboarding", response_model=OnboardingResponse)
async def tenant_onboarding(
    _: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> OnboardingResponse:
    return await calcular_onboarding(db, tenant_id=tenant_id, tenant=tenant)


@router.put("/me/nup-config", response_model=TenantMeResponse)
async def update_nup_config(
    payload: TenantNupConfigUpdate,
    # PR 3b — gate consolidado na permissão específica `configuracao:atualizar`.
    _: Usuario = Depends(require_permission("configuracao", "atualizar")),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    # Não permite ativar NUP sem código de órgão preenchido.
    novo_codigo = (
        payload.codigo_orgao_nup
        if payload.codigo_orgao_nup is not None
        else tenant.codigo_orgao_nup
    )
    novo_flag = (
        payload.usar_nup_federal
        if payload.usar_nup_federal is not None
        else tenant.usar_nup_federal
    )
    if novo_flag and not novo_codigo:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Defina o código do órgão (5 dígitos) antes de ativar a geração de NUP.",
        )

    if payload.codigo_orgao_nup is not None:
        tenant.codigo_orgao_nup = payload.codigo_orgao_nup
    if payload.usar_nup_federal is not None:
        tenant.usar_nup_federal = payload.usar_nup_federal

    await db.commit()
    await db.refresh(tenant)
    return tenant
