"""Migration 0054 — Transporte Regulado: Renovação de Alvarás

Adiciona suporte para rastreamento de renovações de alvarás via campo renovado_de
(self-referential FK). Permite criar cadeia de alvarás renovados.

Campo novo:
  - renovado_de: Integer, nullable, FK para alvara.id (self-referential)
    Quando não null, indica que este alvará é renovação de outro.
    Permite rastrear histórico: alvara_1 -> renovado_de=null
                               alvara_2 -> renovado_de=alvara_1
                               alvara_3 -> renovado_de=alvara_2

Revision ID: 0054
Revises: 0053
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade():
    # Add renovado_de column para rastrear renovações
    op.add_column(
        "alvara",
        sa.Column("renovado_de", sa.Integer(), nullable=True),
        schema="transporte_regulado",
    )

    # Self-referential FK: álvara pode ser renovação de outro álvara
    op.create_foreign_key(
        "fk_alvara_renovado_de",
        "alvara",
        "alvara",
        ["renovado_de"],
        ["id"],
        source_schema="transporte_regulado",
        referent_schema="transporte_regulado",
    )

    # Índice em renovado_de para queries rápidas de histórico
    op.create_index(
        "ix_alvara_renovado_de",
        "alvara",
        ["renovado_de"],
        schema="transporte_regulado",
    )


def downgrade():
    op.drop_index(
        "ix_alvara_renovado_de",
        schema="transporte_regulado",
    )

    op.drop_constraint(
        "fk_alvara_renovado_de",
        "alvara",
        schema="transporte_regulado",
        type_="foreignkey",
    )

    op.drop_column(
        "alvara",
        "renovado_de",
        schema="transporte_regulado",
    )
