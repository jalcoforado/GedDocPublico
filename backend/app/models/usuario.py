from sqlalchemy import Boolean, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
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
    # Fase 16 — necessário pra canal whatsapp. Formato livre (sugerido E.164).
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Sigilo gradual (LAI) — credencial de acesso. Pode ver processos cujo
    # nível seja <= esta credencial. Default 'interno' = vê ostensivo+interno.
    nivel_acesso_sigilo: Mapped[str] = mapped_column(
        String(20), nullable=False, default="interno"
    )
    # SEC-1 — força troca de senha no primeiro acesso. Default false:
    # usuários existentes e novos cadastros nascem sem obrigação; só vira
    # true quando provisionamento/reset definirem explicitamente (próximos
    # commits do SEC-1).
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
