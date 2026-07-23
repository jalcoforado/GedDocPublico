"""Frota — `frota.veiculo_manutencao` (manutenções preventivas/corretivas).

Revision ID: 0037
Revises: 0036
Create Date: 2026-06-07

Cria `frota.veiculo_manutencao` no schema `frota` (existente desde 0031), no
mesmo padrão de RLS/GRANTs/policies das demais tabelas de frota.

Controle simples de manutenção (SEM ordem de serviço complexa): cada veículo
pode ter N manutenções (preventiva/corretiva) com ciclo de status
aberta → em_andamento → concluida (ou cancelada). Efeitos na `situacao` do
veículo são guardados no serviço (abrir põe em 'manutencao' se estava
'disponivel'; concluir/cancelar devolve a 'disponivel' só se estava em
'manutencao' — nunca sobrescreve 'em_uso').

- `tipo` (preventiva/corretiva) e `status` (aberta/em_andamento/concluida/
  cancelada) são String, validados na aplicação (sem CHECK de enum — mesmo
  padrão de `situacao` em `frota.veiculo`).
- custos em Numeric(12,2); CHECKs de defesa em profundidade (km/custos >= 0).
- Soft-delete via `excluido`. Reaproveita a permissão `frota`.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: str | Sequence[str] | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "veiculo_manutencao",
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
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column(
            "data_abertura", sa.Date(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("data_prevista", sa.Date(), nullable=True),
        sa.Column("data_conclusao", sa.Date(), nullable=True),
        sa.Column("km_atual", sa.Integer(), nullable=True),
        sa.Column("fornecedor", sa.String(length=150), nullable=True),
        sa.Column("custo_estimado", sa.Numeric(12, 2), nullable=True),
        sa.Column("custo_final", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'aberta'"),
        ),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
        sa.CheckConstraint(
            "km_atual IS NULL OR km_atual >= 0", name="ck_manutencao_km_nao_negativa"
        ),
        sa.CheckConstraint(
            "custo_estimado IS NULL OR custo_estimado >= 0",
            name="ck_manutencao_custo_estimado_nao_negativo",
        ),
        sa.CheckConstraint(
            "custo_final IS NULL OR custo_final >= 0",
            name="ck_manutencao_custo_final_nao_negativo",
        ),
        schema="frota",
    )

    op.create_index(
        "ix_veiculo_manutencao_tenant_veiculo",
        "veiculo_manutencao",
        ["tenant_id", "id_veiculo"],
        schema="frota",
    )
    op.create_index(
        "ix_veiculo_manutencao_tenant_status",
        "veiculo_manutencao",
        ["tenant_id", "status"],
        schema="frota",
    )
    op.create_index(
        "ix_veiculo_manutencao_tenant_excluido",
        "veiculo_manutencao",
        ["tenant_id", "excluido"],
        schema="frota",
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON frota.veiculo_manutencao TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON frota.veiculo_manutencao_id_seq TO aprimora_app"
    )

    op.execute("ALTER TABLE frota.veiculo_manutencao ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE frota.veiculo_manutencao FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON frota.veiculo_manutencao
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON frota.veiculo_manutencao
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON frota.veiculo_manutencao"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON frota.veiculo_manutencao"
    )
    op.drop_index(
        "ix_veiculo_manutencao_tenant_excluido",
        table_name="veiculo_manutencao",
        schema="frota",
    )
    op.drop_index(
        "ix_veiculo_manutencao_tenant_status",
        table_name="veiculo_manutencao",
        schema="frota",
    )
    op.drop_index(
        "ix_veiculo_manutencao_tenant_veiculo",
        table_name="veiculo_manutencao",
        schema="frota",
    )
    op.drop_table("veiculo_manutencao", schema="frota")
