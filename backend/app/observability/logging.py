"""Logging estruturado em JSON com contexto multi-tenant — Fase 33.

Cada request loga 1 linha JSON com `request_id`, `tenant_id/slug`, `usuario_id`,
método/path/status/duração. Em produção, agregadores (Loki, ELK, Cloudwatch
Insights) parseiam direto.

Uso interno: `from .observability.logging import get_logger; logger = get_logger(__name__)`.
"""
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

# Context vars que o RequestLoggingMiddleware popula a cada request.
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
tenant_id_ctx: ContextVar[int | None] = ContextVar("tenant_id", default=None)
tenant_slug_ctx: ContextVar[str | None] = ContextVar("tenant_slug", default=None)
usuario_id_ctx: ContextVar[int | None] = ContextVar("usuario_id", default=None)


class JsonFormatter(logging.Formatter):
    """Formata cada log record como uma linha JSON.

    Campos sempre presentes: ts, level, logger, msg. Campos do contexto:
    request_id, tenant_id, tenant_slug, usuario_id (apenas se setados).
    Qualquer atributo extra do record (via `logger.info(..., extra={"foo": 1})`)
    é incluído.
    """

    BUILTIN_ATTRS = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Contexto do request, se houver
        for k, ctx in (
            ("request_id", request_id_ctx),
            ("tenant_id", tenant_id_ctx),
            ("tenant_slug", tenant_slug_ctx),
            ("usuario_id", usuario_id_ctx),
        ):
            v = ctx.get()
            if v is not None:
                payload[k] = v
        # Atributos extras passados via `extra={...}`
        for key, value in record.__dict__.items():
            if key not in self.BUILTIN_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configura root logger com formatter JSON. Idempotente."""
    root = logging.getLogger()
    root.setLevel(level)
    # Remove handlers default (StreamHandler do uvicorn fica, mas substituímos
    # o formatter)
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    # Também substitui o formatter dos loggers do uvicorn
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
