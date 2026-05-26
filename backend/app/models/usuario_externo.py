from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class UsuarioExterno(Base):
    __tablename__ = "usuario_externo"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    nome: Mapped[str | None] = mapped_column(String(100), nullable=True)
    senha: Mapped[str | None] = mapped_column(String(150), nullable=True)
    senha_bcrypt: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cpf_cnpj: Mapped[str | None] = mapped_column(String(14), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    login_govbr: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    uid: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    data_criacao: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    data_limite_ativacao: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    app: Mapped[str | None] = mapped_column(String, nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    telefone_whatsapp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
