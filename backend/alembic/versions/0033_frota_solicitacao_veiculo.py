"""Frota PR-3 — `frota.solicitacao_veiculo` (solicitação de veículo).

Revision ID: 0033
Revises: 0032
Create Date: 2026-06-07

Cria `frota.solicitacao_veiculo` no schema `frota` (existente desde 0031), no
mesmo padrão de RLS/GRANTs/policies de `frota.veiculo`/`frota.motorista`.

- `status` máquina de estados (solicitada/aprovada/rejeitada/cancelada), default
  `solicitada`; transições guardadas no serviço de domínio.
- CHECK `quilometragem`? não — aqui: `quantidade_passageiros > 0` e
  `data_retorno_prevista >= data_saida_prevista` como defesa em profundidade
  (também validados no schema/serviço).
- Reaproveita a permissão `frota` (NÃO semeia transação nova).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | Sequence[str] | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "solicitacao_veiculo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "id_usuario_solicitante",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=False,
        ),
        sa.Column(
            "id_unidade_solicitante",
            sa.Integer(),
            sa.ForeignKey("utils.unidade_trabalho.id"),
            nullable=True,
        ),
        sa.Column("finalidade", sa.String(length=255), nullable=False),
        sa.Column("destino", sa.String(length=255), nullable=False),
        sa.Column("data_saida_prevista", sa.DateTime(), nullable=False),
        sa.Column("data_retorno_prevista", sa.DateTime(), nullable=False),
        sa.Column("quantidade_passageiros", sa.Integer(), nullable=False),
        sa.Column(
            "necessita_motorista",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'solicitada'"),
        ),
        sa.Column("justificativa_rejeicao", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
        sa.CheckConstraint(
            "quantidade_passageiros > 0", name="ck_solicitacao_passageiros_positivo"
        ),
        sa.CheckConstraint(
            "data_retorno_prevista >= data_saida_prevista",
            name="ck_solicitacao_datas_coerentes",
        ),
        schema="frota",
    )

    op.create_index(
        "ix_solicitacao_tenant_status",
        "solicitacao_veiculo",
        ["tenant_id", "status"],
        schema="frota",
    )
    op.create_index(
        "ix_solicitacao_tenant_excluido",
        "solicitacao_veiculo",
        ["tenant_id", "excluido"],
        schema="frota",
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON frota.solicitacao_veiculo TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON frota.solicitacao_veiculo_id_seq TO aprimora_app"
    )

    op.execute("ALTER TABLE frota.solicitacao_veiculo ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE frota.solicitacao_veiculo FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON frota.solicitacao_veiculo
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON frota.solicitacao_veiculo
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON frota.solicitacao_veiculo"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON frota.solicitacao_veiculo"
    )
    op.drop_index(
        "ix_solicitacao_tenant_excluido",
        table_name="solicitacao_veiculo",
        schema="frota",
    )
    op.drop_index(
        "ix_solicitacao_tenant_status",
        table_name="solicitacao_veiculo",
        schema="frota",
    )
    op.drop_table("solicitacao_veiculo", schema="frota")
