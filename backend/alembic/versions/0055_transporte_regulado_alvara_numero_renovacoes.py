"""Migration 0055 — Transporte Regulado: Permitir numero duplicado para alvarás renovados

Ajusta o índice único de numero_alvara para permitir duplicatas em renovações.
Regra: numero_alvara é único por tenant apenas para alvarás originais (renovado_de IS NULL).
Alvarás renovados (renovado_de NOT NULL) podem ter o mesmo número do original.

Revision ID: 0055
Revises: 0054
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade():
    # Drop old unique index that didn't account for renovações
    op.drop_index(
        "ix_alvara_numero_unico",
        schema="transporte_regulado",
    )

    # Create new unique index: numero_alvara único por tenant apenas para originais (não renovados)
    op.create_index(
        "ix_alvara_numero_unico",
        "alvara",
        ["tenant_id", "numero_alvara"],
        schema="transporte_regulado",
        unique=True,
        postgresql_where=sa.text("excluido = false AND renovado_de IS NULL"),
    )


def downgrade():
    op.drop_index(
        "ix_alvara_numero_unico",
        schema="transporte_regulado",
    )

    # Restore old unique index (less specific)
    op.create_index(
        "ix_alvara_numero_unico",
        "alvara",
        ["tenant_id", "numero_alvara"],
        schema="transporte_regulado",
        unique=True,
        postgresql_where=sa.text("excluido = false"),
    )
