"""RequestLoggingMiddleware — Fase 33.

Loga 1 linha JSON estruturada por request:
- request_id (uuid4)
- método + path
- status
- duração em ms
- tenant_id/slug (do TenantMiddleware, que roda antes)
- usuario_id (se conhecível pelo cookie — leitura passiva, sem auth)

Popula context vars consumidas pelo `JsonFormatter` para correlacionar logs
internos da request com a linha de acesso.
"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..observability.logging import (
    request_id_ctx,
    tenant_id_ctx,
    tenant_slug_ctx,
    usuario_id_ctx,
)

logger = logging.getLogger("aprimora.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # request_id sempre disponível (vem do header X-Request-Id se presente,
        # senão gerado aqui — útil pra correlacionar com cliente/load balancer).
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        token_req = request_id_ctx.set(request_id)
        # tenant_id/slug/usuario_id são populados por middlewares/deps internos
        # — context vars são "set" lá. Aqui apenas garantimos baseline None.
        token_tid = tenant_id_ctx.set(None)
        token_slug = tenant_slug_ctx.set(None)
        token_uid = usuario_id_ctx.set(None)

        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["x-request-id"] = request_id
            return response
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            # request.state pode ter sido populado por Tenant/auth deps; sync
            # nas context vars para a linha final de log.
            tid = getattr(request.state, "tenant_id", None)
            slug = getattr(request.state, "tenant_slug", None)
            uid = getattr(request.state, "usuario_id", None)
            if tid is not None:
                tenant_id_ctx.set(tid)
            if slug is not None:
                tenant_slug_ctx.set(slug)
            if uid is not None:
                usuario_id_ctx.set(uid)
            logger.info(
                "http_request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": duration_ms,
                    "client": request.client.host if request.client else None,
                },
            )
            # Restaura context vars (importante em ambientes que reusam loop tasks).
            request_id_ctx.reset(token_req)
            tenant_id_ctx.reset(token_tid)
            tenant_slug_ctx.reset(token_slug)
            usuario_id_ctx.reset(token_uid)
