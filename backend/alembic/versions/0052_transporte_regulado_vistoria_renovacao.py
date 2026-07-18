"""Migration 0052 — Transporte Regulado: vistoria renovação

Adiciona suporte a renovação/revalidação de vistorias regulatórias.

Campos novos:
  - data_validade: quando a vistoria expira (para identificar vencidas)
  - renovada_de: FK para vistoria anterior (histórico/soft-link)

Revision ID: 0052
Revises: 0051
Create Date: 2026-07-18

Schema: transporte_regulado (existente)
Tabela modificada:
  - veiculo_vistoria: adiciona data_validade + renovada_de
RLS: mantém tenant-scoped
"""

from alembic import op
import sqlalchemy as sa


revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade():
    # Adiciona coluna data_validade (quando a vistoria vence)
    op.add_column(
        "veiculo_vistoria",
        sa.Column("data_validade", sa.Date(), nullable=True),
        schema="transporte_regulado",
    )

    # Adiciona coluna renovada_de (FK para vistoria anterior, se houver renovação)
    op.add_column(
        "veiculo_vistoria",
        sa.Column("renovada_de", sa.Integer(), nullable=True),
        schema="transporte_regulado",
    )

    # FK para renovada_de: veiculo_vistoria → veiculo_vistoria.id (mesmo schema)
    op.execute(
        "ALTER TABLE transporte_regulado.veiculo_vistoria ADD CONSTRAINT "
        "fk_veiculo_vistoria_renovada_de FOREIGN KEY(renovada_de) "
        "REFERENCES transporte_regulado.veiculo_vistoria(id)"
    )

    # Index: data_validade (listar vencidas)
    op.create_index(
        "ix_veiculo_vistoria_data_validade",
        "veiculo_vistoria",
        ["tenant_id", "data_validade"],
        schema="transporte_regulado",
    )

    # Index: renovada_de (histórico)
    op.create_index(
        "ix_veiculo_vistoria_renovada_de",
        "veiculo_vistoria",
        ["renovada_de"],
        schema="transporte_regulado",
    )


def downgrade():
    op.drop_index(
        "ix_veiculo_vistoria_renovada_de",
        schema="transporte_regulado",
    )
    op.drop_index(
        "ix_veiculo_vistoria_data_validade",
        schema="transporte_regulado",
    )
    op.execute(
        "ALTER TABLE transporte_regulado.veiculo_vistoria "
        "DROP CONSTRAINT fk_veiculo_vistoria_renovada_de"
    )
    op.drop_column("veiculo_vistoria", "renovada_de", schema="transporte_regulado")
    op.drop_column("veiculo_vistoria", "data_validade", schema="transporte_regulado")
