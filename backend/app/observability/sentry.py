"""Integração opcional com Sentry — Fase 33.

Se `SENTRY_DSN` está setado, inicializa Sentry SDK com integração FastAPI/
SQLAlchemy automática. Para que CADA evento de erro venha com tag
`tenant_slug`, instalamos um `before_send` hook que lê o ContextVar
populado pelo `RequestLoggingMiddleware`.

Sentry SDK só é importado quando DSN está setado — projetos sem sentry-sdk
instalado continuam funcionando.
"""
from __future__ import annotations

from typing import Any

from ..config import get_settings
from .logging import (
    request_id_ctx,
    tenant_id_ctx,
    tenant_slug_ctx,
    usuario_id_ctx,
)


def init_sentry() -> bool:
    """Retorna True se Sentry foi inicializado, False caso contrário."""
    settings = get_settings()
    if not settings.sentry_dsn:
        return False
    try:
        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration  # type: ignore
    except ImportError:
        # sentry-sdk não instalado; aceita silenciosamente.
        return False

    def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
        tags = event.setdefault("tags", {})
        tid = tenant_id_ctx.get()
        slug = tenant_slug_ctx.get()
        rid = request_id_ctx.get()
        uid = usuario_id_ctx.get()
        if tid is not None:
            tags["tenant_id"] = str(tid)
        if slug:
            tags["tenant_slug"] = slug
        if rid:
            tags["request_id"] = rid
        if uid is not None:
            user = event.setdefault("user", {})
            user.setdefault("id", str(uid))
        return event

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        before_send=_before_send,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
    )
    return True
