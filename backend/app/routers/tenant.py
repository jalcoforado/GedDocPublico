"""Endpoints sobre o tenant atual.

- GET  /api/v2/tenants/me            — info pro frontend (branding + flags)
- PUT  /api/v2/tenants/me/nup-config — config NUP federal (Fase P2)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_tenant
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Tenant, Usuario
from ..schemas.tenant import TenantMeResponse, TenantNupConfigUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me", response_model=TenantMeResponse)
async def tenant_me(tenant: Tenant = Depends(get_current_tenant)) -> Tenant:
    return tenant


@router.put("/me/nup-config", response_model=TenantMeResponse)
async def update_nup_config(
    payload: TenantNupConfigUpdate,
    # Gate: precisa de permissão administrativa. `usuario.atualizar` é o mais
    # próximo do que temos hoje pra "admin do tenant".
    _: Usuario = Depends(require_permission("usuario", "atualizar")),
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
