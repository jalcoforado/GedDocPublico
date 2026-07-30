from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..database import Base


class Modulo(Base):
    """Catálogo GLOBAL de módulos do produto. Sem tenant_id de propósito."""

    __tablename__ = "modulo"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(String(80), nullable=False)
    icone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contratavel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ModuloTransacao(Base):
    """Junção GLOBAL módulo <-> utils.transacao. Do nosso lado, não do legado."""

    __tablename__ = "modulo_transacao"
    __table_args__ = (
        UniqueConstraint("id_modulo", "id_transacao", name="uq_modulo_transacao"),
        {"schema": "aprimora_py"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_modulo: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.modulo.id"), nullable=False
    )
    id_transacao: Mapped[int] = mapped_column(
        ForeignKey("utils.transacao.id"), nullable=False
    )


class TenantModulo(Base):
    """Contratação de um módulo por um tenant. SEM RLS — ver spec §4.1."""

    __tablename__ = "tenant_modulo"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_modulo: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.modulo.id"), nullable=False
    )
    contratado_em: Mapped[object] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


# --- Legado do PHP. Sai do ORM na fatia F4; ninguém deve passar a usar. ---


class ModuloLegado(Base):
    __tablename__ = "modulos"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    modulo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    icone: Mapped[str | None] = mapped_column(String(50), nullable=True)


class ConfiguracoesModulosLegado(Base):
    __tablename__ = "configuracoes_modulos"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_configuracao: Mapped[int] = mapped_column(
        ForeignKey("public.configuracoes.id"), nullable=False
    )
    id_modulo: Mapped[int] = mapped_column(ForeignKey("public.modulos.id"), nullable=False)
    ambiente: Mapped[str | None] = mapped_column(
        Enum("desenvolvimento", "homologacao", "producao", name="ambiente"), nullable=True
    )
    url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ativo: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
