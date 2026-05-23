from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Sistema(Base):
    __tablename__ = "sistema"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sistema: Mapped[str] = mapped_column(String(255), nullable=False)
    app: Mapped[str | None] = mapped_column(String(50), nullable=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    icone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
