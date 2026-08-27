"""Modelo `ComplementacaoDocumental` — PR 4d.

Solicitação formal de complementação documental do servidor ao cidadão
(ver `docs/archive/servicos-pr4d-complementacao-documental-escopo-implementavel.md`).
"""
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ComplementacaoDocumental(Base):
    __tablename__ = "complementacao_documental"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_processo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=False
    )
    id_usuario_solicitante: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="aberta"
    )
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    documentos_solicitados: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False
    )
    motivo_cancelamento: Mapped[str | None] = mapped_column(Text, nullable=True)
    # `criado_em` = dt_solicitacao por convenção (D-MODELO).
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    respondido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
