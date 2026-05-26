"""Endpoints sobre o tenant atual.

Por enquanto só `/me` (info pro frontend buscar branding). Endpoints
admin (criar/listar tenants) ficam para fases futuras (15+).
"""
from fastapi import APIRouter, Depends

from ..auth.deps import get_current_tenant
from ..models import Tenant
from ..schemas.tenant import TenantMeResponse

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me", response_model=TenantMeResponse)
async def tenant_me(tenant: Tenant = Depends(get_current_tenant)) -> Tenant:
    return tenant
