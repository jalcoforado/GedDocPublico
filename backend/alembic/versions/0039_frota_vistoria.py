"""Frota — `frota.veiculo_vistoria` (vistoria/checklist interno).

Revision ID: 0039
Revises: 0038
Create Date: 2026-06-08

Cria `frota.veiculo_vistoria` no schema `frota`, no mesmo padrão de
RLS/GRANTs/policies das demais tabelas de frota.

Checklist simples de campos fixos (Opção A): cada veículo tem N vistorias
(saída/retorno/periódica) com um `resultado` (aprovada/reprovada/com_ressalvas)
e itens booleanos de conferência. NÃO altera a `situacao` do veículo, mesmo em
resultado 'reprovada' (decisão deste módulo — documentada).

- `tipo`/`resultado` são String validados na aplicação (sem CHECK de enum).
- itens de checklist são Boolean NOT NULL default FALSE.
- Soft-delete via `excluido`. Reaproveita a permissão `frota`.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
down_revision: str | Sequence[str] | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ITENS = (
    "pneus_ok",
    "luzes_ok",
    "freios_ok",
    "documentacao_ok",
    "limpeza_ok",
    "equipamentos_ok",
)


def upgrade() -> None:
    op.create_table(
        "veiculo_vistoria",
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
            "data_vistoria", sa.Date(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("resultado", sa.String(length=20), nullable=False),
        *[
            sa.Column(
                item, sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
            )
            for item in _ITENS
        ],
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
        schema="frota",
    )

    op.create_index(
        "ix_veiculo_vistoria_tenant_veiculo",
        "veiculo_vistoria",
        ["tenant_id", "id_veiculo"],
        schema="frota",
    )
    op.create_index(
        "ix_veiculo_vistoria_tenant_data",
        "veiculo_vistoria",
        ["tenant_id", "data_vistoria"],
        schema="frota",
    )
    op.create_index(
        "ix_veiculo_vistoria_tenant_excluido",
        "veiculo_vistoria",
        ["tenant_id", "excluido"],
        schema="frota",
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON frota.veiculo_vistoria TO aprimora_app"
    )
    op.execute("GRANT USAGE, SELECT ON frota.veiculo_vistoria_id_seq TO aprimora_app")

    op.execute("ALTER TABLE frota.veiculo_vistoria ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE frota.veiculo_vistoria FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON frota.veiculo_vistoria
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON frota.veiculo_vistoria
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON frota.veiculo_vistoria"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON frota.veiculo_vistoria"
    )
    op.drop_index(
        "ix_veiculo_vistoria_tenant_excluido",
        table_name="veiculo_vistoria",
        schema="frota",
    )
    op.drop_index(
        "ix_veiculo_vistoria_tenant_data", table_name="veiculo_vistoria", schema="frota"
    )
    op.drop_index(
        "ix_veiculo_vistoria_tenant_veiculo",
        table_name="veiculo_vistoria",
        schema="frota",
    )
    op.drop_table("veiculo_vistoria", schema="frota")
