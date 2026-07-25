"""Pagamentos v2.0 Fase 1 — fonte no débito + conta pagadora na autorização.

Revision ID: 0063
Revises: 0062
Create Date: 2026-07-25

Alinha o débito à Especificação v2.0 (seções 8/23; RF-AUT-02/03/04, RN-02/05/06):
- debito.id_fonte_recursos (NOT NULL): a fonte vem do empenho, é vinculante.
- debito.id_conta passa a NULLABLE: vira sugestão não-vinculante (seção 6.1).
- debito.id_conta_pagadora (NULL): conta escolhida/reservada na autorização
  (prefeito/secretário), gravada imutável.
- ordem_pagamento.id_conta_pagadora + valor_reservado: registro histórico
  imutável da autorização (seção 19 Autorizacao).

Backfill dos débitos existentes: id_fonte_recursos := conta.id_fonte_recursos;
id_conta_pagadora := id_conta para os já AUTORIZADO+.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0063"
down_revision: str | Sequence[str] | None = "0062"
branch_labels = None
depends_on = None
S = "pagamentos"


def upgrade() -> None:
    # --- debito ---
    op.add_column("debito", sa.Column("id_fonte_recursos", sa.Integer(), nullable=True), schema=S)
    op.add_column("debito", sa.Column("id_conta_pagadora", sa.Integer(), nullable=True), schema=S)
    op.create_foreign_key("fk_debito_fonte", "debito", "fonte_recursos",
                          ["id_fonte_recursos"], ["id"], source_schema=S, referent_schema=S)
    op.create_foreign_key("fk_debito_conta_pagadora", "debito", "conta_bancaria",
                          ["id_conta_pagadora"], ["id"], source_schema=S, referent_schema=S)

    # Backfill: fonte vem da conta sugerida; conta pagadora = conta atual dos já autorizados.
    op.execute(f"""
        UPDATE {S}.debito d
        SET id_fonte_recursos = c.id_fonte_recursos
        FROM {S}.conta_bancaria c
        WHERE d.id_conta = c.id AND d.id_fonte_recursos IS NULL
    """)
    op.execute(f"""
        UPDATE {S}.debito
        SET id_conta_pagadora = id_conta
        WHERE id_conta_pagadora IS NULL
          AND status IN ('AUTORIZADO','PAGO_PARCIAL','PAGO')
    """)

    # id_fonte_recursos torna-se obrigatória; id_conta torna-se opcional (sugestão).
    op.alter_column("debito", "id_fonte_recursos", nullable=False, schema=S)
    op.alter_column("debito", "id_conta", nullable=True, schema=S)

    op.create_index("ix_debito_tenant_fonte", "debito", ["tenant_id", "id_fonte_recursos"], schema=S)
    op.create_index("ix_debito_tenant_conta_pagadora", "debito",
                    ["tenant_id", "id_conta_pagadora"], schema=S)

    # --- ordem_pagamento (append-only: registro histórico da autorização) ---
    op.add_column("ordem_pagamento",
                  sa.Column("id_conta_pagadora", sa.Integer(), nullable=True), schema=S)
    op.add_column("ordem_pagamento",
                  sa.Column("valor_reservado", sa.Numeric(14, 2), nullable=True), schema=S)
    op.create_foreign_key("fk_op_conta_pagadora", "ordem_pagamento", "conta_bancaria",
                          ["id_conta_pagadora"], ["id"], source_schema=S, referent_schema=S)


def downgrade() -> None:
    op.drop_constraint("fk_op_conta_pagadora", "ordem_pagamento", schema=S, type_="foreignkey")
    op.drop_column("ordem_pagamento", "valor_reservado", schema=S)
    op.drop_column("ordem_pagamento", "id_conta_pagadora", schema=S)

    op.drop_index("ix_debito_tenant_conta_pagadora", "debito", schema=S)
    op.drop_index("ix_debito_tenant_fonte", "debito", schema=S)
    op.alter_column("debito", "id_conta", nullable=False, schema=S)
    op.drop_constraint("fk_debito_conta_pagadora", "debito", schema=S, type_="foreignkey")
    op.drop_constraint("fk_debito_fonte", "debito", schema=S, type_="foreignkey")
    op.drop_column("debito", "id_conta_pagadora", schema=S)
    op.drop_column("debito", "id_fonte_recursos", schema=S)
