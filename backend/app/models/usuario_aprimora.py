from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class UsuarioAprimora(Base):
    """Usuário independente no schema aprimora_py (sem dependência de utils.usuario legado)."""
    __tablename__ = "usuario"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    senha_bcrypt: Mapped[str] = mapped_column(String(255), nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
