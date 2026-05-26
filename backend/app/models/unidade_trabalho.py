from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class UnidadeTrabalho(Base):
    __tablename__ = "unidade_trabalho"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    unidade_trabalho: Mapped[str] = mapped_column(String, nullable=False)
    sigla: Mapped[str | None] = mapped_column(String, nullable=True)
    id_unidade_pai: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_tipo_unidade_trabalho: Mapped[int | None] = mapped_column(
        ForeignKey("utils.tipo_unidade_trabalho.id"), nullable=True
    )
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TipoUnidadeTrabalho(Base):
    __tablename__ = "tipo_unidade_trabalho"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    tipo_unidade_trabalho: Mapped[str] = mapped_column(String, nullable=False)
    codigo: Mapped[str | None] = mapped_column(String, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
