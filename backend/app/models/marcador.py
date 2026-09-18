"""Favoritos e marcadores de processo (F5, benchmark SUiTE, migration 0114)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ProcessoFavorito(Base):
    """Lista de acompanhamento pessoal — sobrevive à tramitação para outro
    setor. Toggle: desfavoritar apaga a linha, sem soft-delete."""

    __tablename__ = "processo_favorito"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    id_processo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=False
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Marcador(Base):
    """Catálogo de etiquetas coloridas, por tenant.

    `id_unidade_trabalho` registra quem ADMINISTRA a etiqueta (a
    administração é setorial); a visibilidade não é — qualquer processo do
    tenant pode receber qualquer marcador do catálogo.
    """

    __tablename__ = "marcador"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_unidade_trabalho: Mapped[int | None] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=True
    )
    nome: Mapped[str] = mapped_column(String(60), nullable=False)
    cor: Mapped[str] = mapped_column(String(7), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ProcessoMarcador(Base):
    """Vínculo N:N processo↔marcador. Toggle: desmarcar apaga a linha."""

    __tablename__ = "processo_marcador"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_processo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=False
    )
    id_marcador: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.marcador.id"), nullable=False
    )
    id_usuario: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
