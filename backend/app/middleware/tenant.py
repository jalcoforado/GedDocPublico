"""TenantMiddleware — resolve o tenant atual pelo subdomínio do Host header.

Estratégia (Fase 12):

1. Lê o header `Host` (já preservado pelo nginx via `proxy_set_header Host $host`).
2. Extrai o subdomínio comparando com `settings.base_domain`.
   - `sobral.aprimora.local` + base=`aprimora.local` → `sobral`
   - `localhost:8090`         + base=`aprimora.local` → None
   - `aprimora.local`         + base=`aprimora.local` → None
3. Resolve via slug em `aprimora_py.tenant` (ativo=true).
4. Popula `request.state.tenant_id`, `request.state.tenant_slug`,
   `request.state.tenant_nome`. Se não resolver:
   - `STRICT_TENANT_RESOLUTION=True`  → 404
   - `STRICT_TENANT_RESOLUTION=False` (dev) → cai no `default_tenant_slug`

Rotas que precisam do tenant declaram `Depends(require_tenant)` em
`app/auth/deps.py`. Rotas globais (health) não declaram nada — middleware
populou o state se conseguiu, mas não bloqueia.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..config import get_settings
from ..database import SessionLocal
from ..models import Tenant
from ..observability.logging import tenant_id_ctx, tenant_slug_ctx


def extract_subdomain(host: str, base_domain: str) -> str | None:
    """Extrai subdomínio comparando host com base_domain. Ignora porta."""
    if not host:
        return None
    host_no_port = host.split(":", 1)[0].lower()
    base = base_domain.lower()
    suffix = f".{base}"
    if host_no_port.endswith(suffix):
        sub = host_no_port[: -len(suffix)]
        return sub or None
    return None


class TenantMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._settings = get_settings()

    async def dispatch(self, request: Request, call_next):
        host = request.headers.get("host", "")
        subdomain = extract_subdomain(host, self._settings.base_domain)

        slug = subdomain
        if slug is None and not self._settings.strict_tenant_resolution:
            slug = self._settings.default_tenant_slug

        tenant: Tenant | None = None
        if slug:
            async with SessionLocal() as db:
                result = await db.execute(
                    select(Tenant).where(
                        Tenant.slug == slug,
                        Tenant.ativo.is_(True),
                    )
                )
                tenant = result.scalar_one_or_none()

        if tenant is None and not self._settings.strict_tenant_resolution:
            # Subdomínio desconhecido em dev → tenta o default explicitamente.
            async with SessionLocal() as db:
                result = await db.execute(
                    select(Tenant).where(
                        Tenant.slug == self._settings.default_tenant_slug,
                        Tenant.ativo.is_(True),
                    )
                )
                tenant = result.scalar_one_or_none()

        if tenant is None and self._settings.strict_tenant_resolution:
            return JSONResponse(
                status_code=404,
                content={
                    "detail": "Tenant não encontrado",
                    "host": host,
                    "subdomain": subdomain,
                },
            )

        if tenant is not None:
            request.state.tenant_id = tenant.id
            request.state.tenant_slug = tenant.slug
            request.state.tenant_nome = tenant.nome
            # Logs estruturados (Fase 33) — context vars consumidas pelo JsonFormatter
            tenant_id_ctx.set(tenant.id)
            tenant_slug_ctx.set(tenant.slug)

        return await call_next(request)
