from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Nivel(Base):
    __tablename__ = "nivel"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nivel: Mapped[str] = mapped_column(String(255), nullable=False)
    valor: Mapped[int] = mapped_column(Integer, nullable=False)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
