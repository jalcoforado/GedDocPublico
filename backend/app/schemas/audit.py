"""Schema do audit log — Fase 24."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_usuario: int | None
    nome_usuario: str | None  # JOIN com utils.usuario
    acao: str
    entidade: str
    id_entidade: int | None
    payload: dict[str, Any] | None
    request_id: str | None
    ip: str | None
    criado_em: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int
