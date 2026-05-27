from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Tenant(Base):
    __tablename__ = "tenant"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cnpj: Mapped[str | None] = mapped_column(String(20), nullable=True)
    id_cidade: Mapped[int | None] = mapped_column(
        ForeignKey("utils.cidade.id"), nullable=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    plano: Mapped[str] = mapped_column(String(20), nullable=False, default="basico")
    cor_primaria: Mapped[str | None] = mapped_column(String(7), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Fase P2 — NUP federal (Decreto 8.539/2015). Opt-in por tenant.
    codigo_orgao_nup: Mapped[str | None] = mapped_column(String(5), nullable=True)
    usar_nup_federal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
