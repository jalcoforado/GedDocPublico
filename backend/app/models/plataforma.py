"""Identidade e trilha do operador de plataforma — SEC-01A / ADR-016.

Duas tabelas de **plataforma**: sem `tenant_id`, sem RLS, sem policies. Mesmo
precedente de `aprimora_py.tenant`, `modulo` e `tenant_modulo`. Criadas na
migration `0076_platform_admin_identity.py`, que documenta as constraints.

O que estes modelos NÃO podem ganhar, nunca:

- coluna `tenant_id` ou qualquer FK para `utils.*` / `protocolos.*` — o
  ADR-016 §2.2 proíbe vincular o principal a cadastro de tenant, e é
  exatamente esse acoplamento que produziu o achado F-01;
- um campo de e-mail que participe de decisão. `display_label` existe para
  humano ler; quem decide é o par `(issuer, subject)`.

Há teste travando as duas coisas em `tests/test_platform_admin_identity.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class PlatformPrincipal(Base):
    """Operador de plataforma. Chave natural OIDC `(issuer, subject)`."""

    __tablename__ = "platform_principal"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    # Rótulo de exibição (tipicamente o e-mail do IdP). NUNCA decide nada.
    display_label: Mapped[str] = mapped_column(String(255), nullable=False)

    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    break_glass: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    concedido_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    concedido_por: Mapped[str] = mapped_column(String(255), nullable=False)
    motivo_concessao: Mapped[str] = mapped_column(Text, nullable=False)

    revogado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revogado_por: Mapped[str | None] = mapped_column(String(255), nullable=True)
    motivo_revogacao: Mapped[str | None] = mapped_column(Text, nullable=True)

    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def vigente_em(self, agora: datetime) -> bool:
        """Vigência da matriz de claims §3: ativo, não revogado e dentro da
        janela `[valid_from, valid_until)`.

        `valid_until` é o que expira a janela de break-glass (60 min, ADR §2.8)
        — o cenário 20 da matriz é exatamente um principal cuja janela venceu e
        que, mesmo com `ativo = true` gravado, **não** pode operar.
        """
        if not self.ativo or self.revogado_em is not None:
            return False
        if self.valid_from is not None and agora < self.valid_from:
            return False
        if self.valid_until is not None and agora >= self.valid_until:
            return False
        return True


class PlatformAuditLog(Base):
    """Trilha AUTORITATIVA das operações de plataforma (decisão D-a).

    Não substitui `aprimora_py.audit_log`: a entrada que o **município**
    enxerga continua sendo gravada lá, com o `tenant_id` do alvo. Ver
    `app/services/plataforma_auditoria.py`.
    """

    __tablename__ = "platform_audit_log"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Nulo quando a tentativa foi NEGADA por não haver principal — é dessa
    # linha que o runbook §2 manda colher `(iss, sub)` para o bootstrap.
    platform_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("aprimora_py.platform_principal.id"), nullable=True
    )
    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    acao: Mapped[str] = mapped_column(String(80), nullable=False)
    tenant_alvo_id: Mapped[int | None] = mapped_column(
        ForeignKey("aprimora_py.tenant.id", ondelete="SET NULL"), nullable=True
    )
    detalhe: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
