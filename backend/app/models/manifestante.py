from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class TipoManifestante(Base):
    __tablename__ = "tipo_manifestante"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo_manifestante: Mapped[str | None] = mapped_column(String(150), nullable=True)
    id_categoria: Mapped[int] = mapped_column(Integer, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Manifestante(Base):
    __tablename__ = "manifestante"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_tipo_manifestante: Mapped[int] = mapped_column(
        ForeignKey("protocolos.tipo_manifestante.id"), nullable=False
    )
    cpf_cnpj: Mapped[str | None] = mapped_column(String(14), nullable=True)
    nome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_sexo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    responsavel: Mapped[str | None] = mapped_column(String(255), nullable=True)
    organizacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefone_residencial: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telefone_celular: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telefone_comercial: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
