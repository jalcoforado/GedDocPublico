"""Pagamentos v2.0 Fase 2 — campos ricos de fonte/conta + liquidação no débito.

Revision ID: 0065
Revises: 0064
Create Date: 2026-07-25

RF-FON-01/07, RF-CTA-01/08, RF-VAL-02/RN-01 (spec seções 4/10):
- fonte_recursos: exercício, esfera, vinculação, situação, vigência.
- conta_bancaria: dígito, tipo, titularidade, órgão gestor, finalidade, abertura
  e modo_movimentacao (PAGA/RECEBE/TRANSFERE/RESTRITA). Só contas 'PAGA' são
  elegíveis como conta pagadora.
- debito: liquidacao_confirmada + data_liquidacao (guarda antes de autorizar).

Todos os defaults preservam o comportamento atual (contas existentes ficam
'PAGA'; situação de fonte 'ATIVA').
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0065"
down_revision: str | Sequence[str] | None = "0064"
branch_labels = None
depends_on = None
S = "pagamentos"


def upgrade() -> None:
    # --- fonte_recursos ---
    op.add_column("fonte_recursos", sa.Column("exercicio", sa.Integer(), nullable=True), schema=S)
    op.add_column("fonte_recursos", sa.Column("esfera_origem", sa.String(20), nullable=True), schema=S)
    op.add_column("fonte_recursos", sa.Column("tipo_vinculacao", sa.String(30), nullable=True), schema=S)
    op.add_column("fonte_recursos",
                  sa.Column("situacao", sa.String(20), nullable=False, server_default="ATIVA"), schema=S)
    op.add_column("fonte_recursos", sa.Column("vigencia_inicio", sa.Date(), nullable=True), schema=S)
    op.add_column("fonte_recursos", sa.Column("vigencia_fim", sa.Date(), nullable=True), schema=S)
    op.create_check_constraint(
        "ck_fonte_situacao", "fonte_recursos",
        "situacao IN ('ATIVA','SUSPENSA','ENCERRADA')", schema=S)

    # --- conta_bancaria ---
    op.add_column("conta_bancaria", sa.Column("digito", sa.String(5), nullable=True), schema=S)
    op.add_column("conta_bancaria", sa.Column("tipo", sa.String(20), nullable=True), schema=S)
    op.add_column("conta_bancaria", sa.Column("titularidade", sa.String(150), nullable=True), schema=S)
    op.add_column("conta_bancaria", sa.Column("orgao_gestor", sa.String(150), nullable=True), schema=S)
    op.add_column("conta_bancaria", sa.Column("finalidade", sa.String(255), nullable=True), schema=S)
    op.add_column("conta_bancaria", sa.Column("data_abertura", sa.Date(), nullable=True), schema=S)
    op.add_column("conta_bancaria",
                  sa.Column("modo_movimentacao", sa.String(15), nullable=False, server_default="PAGA"),
                  schema=S)
    op.create_check_constraint(
        "ck_conta_modo_movimentacao", "conta_bancaria",
        "modo_movimentacao IN ('PAGA','RECEBE','TRANSFERE','RESTRITA')", schema=S)

    # --- debito ---
    op.add_column("debito",
                  sa.Column("liquidacao_confirmada", sa.Boolean(), nullable=False,
                            server_default=sa.text("FALSE")), schema=S)
    op.add_column("debito", sa.Column("data_liquidacao", sa.Date(), nullable=True), schema=S)


def downgrade() -> None:
    op.drop_column("debito", "data_liquidacao", schema=S)
    op.drop_column("debito", "liquidacao_confirmada", schema=S)

    op.drop_constraint("ck_conta_modo_movimentacao", "conta_bancaria", schema=S, type_="check")
    for c in ("modo_movimentacao", "data_abertura", "finalidade", "orgao_gestor",
              "titularidade", "tipo", "digito"):
        op.drop_column("conta_bancaria", c, schema=S)

    op.drop_constraint("ck_fonte_situacao", "fonte_recursos", schema=S, type_="check")
    for c in ("vigencia_fim", "vigencia_inicio", "situacao", "tipo_vinculacao",
              "esfera_origem", "exercicio"):
        op.drop_column("fonte_recursos", c, schema=S)
