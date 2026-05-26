"""Audit log — Fase 24."""
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_usuario: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    acao: Mapped[str] = mapped_column(String(80), nullable=False)
    entidade: Mapped[str] = mapped_column(String(60), nullable=False)
    id_entidade: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
