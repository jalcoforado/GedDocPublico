"""Pagamentos v2.0 Onda A2 — auditoria de saldo na Ordem de Pagamento.

Revision ID: 0068
Revises: 0067
Create Date: 2026-07-26

RF-AUT-16: a autorização deve registrar, além de autoridade/conta/valor
reservado (já existentes), o saldo disponível ANTES e o saldo projetado APÓS
a reserva. Grava na ordem_pagamento (registro histórico imutável, seção 19).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0068"
down_revision: str | Sequence[str] | None = "0067"
branch_labels = None
depends_on = None
S = "pagamentos"


def upgrade() -> None:
    op.add_column("ordem_pagamento",
                  sa.Column("saldo_antes", sa.Numeric(14, 2), nullable=True), schema=S)
    op.add_column("ordem_pagamento",
                  sa.Column("saldo_projetado_apos", sa.Numeric(14, 2), nullable=True), schema=S)


def downgrade() -> None:
    op.drop_column("ordem_pagamento", "saldo_projetado_apos", schema=S)
    op.drop_column("ordem_pagamento", "saldo_antes", schema=S)
