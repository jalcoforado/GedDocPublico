from sqlalchemy import Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Configuracao(Base):
    __tablename__ = "configuracoes"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cidade: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estado: Mapped[str | None] = mapped_column(String(50), nullable=True)
    host: Mapped[str | None] = mapped_column(String(150), nullable=True)
    porta: Mapped[str | None] = mapped_column(String(6), nullable=True)
    banco: Mapped[str | None] = mapped_column(String(50), nullable=True)
    usuario: Mapped[str | None] = mapped_column(String(50), nullable=True)
    senha: Mapped[str | None] = mapped_column(String(50), nullable=True)
    url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ambiente: Mapped[str | None] = mapped_column(
        Enum("desenvolvimento", "homologacao", "producao", name="ambiente"), nullable=True
    )
