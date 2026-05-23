from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Modulo(Base):
    __tablename__ = "modulos"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    modulo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    icone: Mapped[str | None] = mapped_column(String(50), nullable=True)


class ConfiguracoesModulos(Base):
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
