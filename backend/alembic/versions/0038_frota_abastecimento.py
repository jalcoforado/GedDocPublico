"""Frota — `frota.veiculo_abastecimento` (abastecimentos de veículos).

Revision ID: 0038
Revises: 0037
Create Date: 2026-06-07

Cria `frota.veiculo_abastecimento` no schema `frota`, no mesmo padrão de
RLS/GRANTs/policies das demais tabelas de frota.

Registro simples de abastecimento: cada veículo tem N abastecimentos (litros,
valor, km, posto). NÃO altera a `situacao` do veículo; apenas atualiza
`quilometragem_atual` se o `km_atual` informado for maior que o do veículo
(guardado no serviço).

- `litros > 0`, `valor_total >= 0`, `km_atual >= 0` como CHECK de defesa em
  profundidade (também validados no schema).
- Soft-delete via `excluido`. Reaproveita a permissão `frota`.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: str | Sequence[str] | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "veiculo_abastecimento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "id_veiculo",
            sa.Integer(),
            sa.ForeignKey("frota.veiculo.id"),
            nullable=False,
        ),
        sa.Column(
            "id_motorista",
            sa.Integer(),
            sa.ForeignKey("frota.motorista.id"),
            nullable=True,
        ),
        sa.Column(
            "data_abastecimento",
            sa.Date(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("km_atual", sa.Integer(), nullable=False),
        sa.Column("tipo_combustivel", sa.String(length=20), nullable=True),
        sa.Column("litros", sa.Numeric(10, 3), nullable=False),
        sa.Column("valor_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("posto", sa.String(length=150), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
        sa.CheckConstraint("litros > 0", name="ck_abastecimento_litros_positivo"),
        sa.CheckConstraint(
            "valor_total >= 0", name="ck_abastecimento_valor_nao_negativo"
        ),
        sa.CheckConstraint("km_atual >= 0", name="ck_abastecimento_km_nao_negativo"),
        schema="frota",
    )

    op.create_index(
        "ix_veiculo_abastecimento_tenant_veiculo",
        "veiculo_abastecimento",
        ["tenant_id", "id_veiculo"],
        schema="frota",
    )
    op.create_index(
        "ix_veiculo_abastecimento_tenant_data",
        "veiculo_abastecimento",
        ["tenant_id", "data_abastecimento"],
        schema="frota",
    )
    op.create_index(
        "ix_veiculo_abastecimento_tenant_excluido",
        "veiculo_abastecimento",
        ["tenant_id", "excluido"],
        schema="frota",
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON frota.veiculo_abastecimento TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON frota.veiculo_abastecimento_id_seq TO aprimora_app"
    )

    op.execute("ALTER TABLE frota.veiculo_abastecimento ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE frota.veiculo_abastecimento FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON frota.veiculo_abastecimento
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON frota.veiculo_abastecimento
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON frota.veiculo_abastecimento"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON frota.veiculo_abastecimento"
    )
    op.drop_index(
        "ix_veiculo_abastecimento_tenant_excluido",
        table_name="veiculo_abastecimento",
        schema="frota",
    )
    op.drop_index(
        "ix_veiculo_abastecimento_tenant_data",
        table_name="veiculo_abastecimento",
        schema="frota",
    )
    op.drop_index(
        "ix_veiculo_abastecimento_tenant_veiculo",
        table_name="veiculo_abastecimento",
        schema="frota",
    )
    op.drop_table("veiculo_abastecimento", schema="frota")
