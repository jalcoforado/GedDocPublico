"""Branding/white-label do tenant atual — público (Fase 15)."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Tenant
from ..schemas.branding import BrandingResponse

router = APIRouter(prefix="/branding", tags=["branding"])


@router.get("/me", response_model=BrandingResponse)
async def branding_me(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> BrandingResponse:
    """Retorna info de branding do tenant resolvido pelo Host. Endpoint público
    — usado pelo frontend ANTES do login para customizar cor/logo/título.
    """
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant não resolvido para este host",
        )
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tid))
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado"
        )
    return BrandingResponse.model_validate(tenant, from_attributes=True)
