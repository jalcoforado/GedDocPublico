"""Modelos `Notificacao` + `NotificacaoPreferenciaEvento` — Fase 17/17b, F9."""
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Notificacao(Base):
    __tablename__ = "notificacao"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_usuario: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    destinatario_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    canal: Mapped[str] = mapped_column(String(20), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    prioridade: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    lido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)


class NotificacaoPreferenciaEvento(Base):
    """Preferências de canal por usuário, por EVENTO (F9, benchmark SUiTE).

    N rows por usuário do tenant — uma por `evento` (mesmo valor de
    `Notificacao.tipo`), unique em (tenant_id, id_usuario, evento). Se a row
    não existir pro (usuário, evento), o motor assume defaults: in_app=true,
    email=true, whatsapp=false (`services/notificacoes.py::DEFAULT_PREFS`).

    O catálogo de eventos válidos vive em código
    (`services/notificacoes.py::EVENTOS_NOTIFICACAO`), não aqui — a coluna
    `evento` não tem FK porque não há tabela de catálogo, só o dict.
    """

    __tablename__ = "notificacao_preferencia_evento"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    evento: Mapped[str] = mapped_column(String(60), nullable=False)
    canal_in_app: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    canal_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    canal_whatsapp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
