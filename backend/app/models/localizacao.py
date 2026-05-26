from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Estado(Base):
    __tablename__ = "estado"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estado: Mapped[str] = mapped_column(String(50), nullable=False)
    uf: Mapped[str] = mapped_column(String(2), nullable=False)
    id_regiao: Mapped[int | None] = mapped_column(Integer, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Cidade(Base):
    __tablename__ = "cidade"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cidade: Mapped[str] = mapped_column(String(255), nullable=False)
    id_estado: Mapped[int | None] = mapped_column(ForeignKey("utils.estado.id"), nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Bairro(Base):
    __tablename__ = "bairro"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_cidade: Mapped[int | None] = mapped_column(
        ForeignKey("utils.cidade.id"), nullable=True
    )
    bairro: Mapped[str] = mapped_column(String(255), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Endereco(Base):
    __tablename__ = "endereco"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_cidade: Mapped[int | None] = mapped_column(
        ForeignKey("utils.cidade.id"), nullable=True
    )
    id_bairro: Mapped[int | None] = mapped_column(
        ForeignKey("utils.bairro.id"), nullable=True
    )
    id_estado: Mapped[int | None] = mapped_column(
        ForeignKey("utils.estado.id"), nullable=True
    )
    rua: Mapped[str | None] = mapped_column(String(255), nullable=True)
    numero: Mapped[str | None] = mapped_column(String(255), nullable=True)
    complemento: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(11, 8), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(11, 8), nullable=True)
    excluido: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
