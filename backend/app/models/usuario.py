from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    senha: Mapped[str] = mapped_column(String(255), nullable=False)
    senha_bcrypt: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cpf: Mapped[str] = mapped_column(String(11), nullable=False)
    id_unidade_trabalho: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cargo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    app: Mapped[str | None] = mapped_column(String(30), nullable=True)
