from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base

FINALIDADES = ("convite", "verificar_email", "redefinir_senha", "codigo_2fa")


class TokenConta(Base):
    """Segredo de uso único da conta (migration 0136).

    Guarda só o HMAC do segredo (`segredo_hash`) — o link e o código vão por
    e-mail e não ficam no banco. Titular é um servidor (`id_usuario`) OU um
    cidadão (`id_usuario_externo`), nunca os dois. Regras de emissão e consumo
    em `services/conta_tokens.py`.
    """

    __tablename__ = "token_conta"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("utils.usuario.id"), nullable=True)
    id_usuario_externo: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario_externo.id"), nullable=True
    )
    finalidade: Mapped[str] = mapped_column(String(30), nullable=False)
    segredo_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tentativas: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    expira_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    usado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
