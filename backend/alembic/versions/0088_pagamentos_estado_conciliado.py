"""Pagamentos — representa a conciliação na dimensão de execução.

Revision ID: 0088
Revises: 0087
Create Date: 2026-08-07
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0088"
down_revision: str | Sequence[str] | None = "0087"
branch_labels = None
depends_on = None
S = "pagamentos"

PAGAMENTO_ANTIGO = (
    "NAO_INICIADA", "PROGRAMADA", "ENVIADA_BANCO", "EM_PROCESSAMENTO",
    "PAGA_PARCIAL", "PAGA", "FALHOU", "CANCELADA", "ESTORNADA",
)


def _in(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


def upgrade() -> None:
    op.drop_constraint(
        "ck_debito_situacao_pagamento", "debito", schema=S, type_="check")
    op.create_check_constraint(
        "ck_debito_situacao_pagamento", "debito",
        f"situacao_pagamento IN ({_in(PAGAMENTO_ANTIGO + ('CONCILIADA',))})",
        schema=S,
    )


def downgrade() -> None:
    op.execute(
        f"UPDATE {S}.debito SET situacao_pagamento = 'PAGA', status = 'PAGO' "
        "WHERE situacao_pagamento = 'CONCILIADA'"
    )
    op.drop_constraint(
        "ck_debito_situacao_pagamento", "debito", schema=S, type_="check")
    op.create_check_constraint(
        "ck_debito_situacao_pagamento", "debito",
        f"situacao_pagamento IN ({_in(PAGAMENTO_ANTIGO)})", schema=S,
    )
