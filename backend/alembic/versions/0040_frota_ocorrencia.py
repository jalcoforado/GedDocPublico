"""Frota — `frota.veiculo_ocorrencia` (ocorrências internas de veículos).

Revision ID: 0040
Revises: 0039
Create Date: 2026-06-08

Cria `frota.veiculo_ocorrencia` no schema `frota`, no mesmo padrão de
RLS/GRANTs/policies das demais tabelas de frota.

Registro de ocorrências internas (avaria/multa/sinistro/documentação/uso
indevido/outro) com gravidade e ciclo de status aberta → em_tratamento →
resolvida (ou cancelada). NÃO altera a `situacao` do veículo. `data_resolucao`
é gravada server-side ao resolver.

- `tipo`/`gravidade`/`status` são String validados na aplicação (sem CHECK de
  enum). Soft-delete via `excluido`. Reaproveita a permissão `frota`.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: str | Sequence[str] | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "veiculo_ocorrencia",
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
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column(
            "data_ocorrencia", sa.Date(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column(
            "gravidade",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'media'"),
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'aberta'"),
        ),
        sa.Column("providencias", sa.Text(), nullable=True),
        sa.Column("data_resolucao", sa.Date(), nullable=True),
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
        "ix_veiculo_ocorrencia_tenant_veiculo",
        "veiculo_ocorrencia",
        ["tenant_id", "id_veiculo"],
        schema="frota",
    )
    op.create_index(
        "ix_veiculo_ocorrencia_tenant_status",
        "veiculo_ocorrencia",
        ["tenant_id", "status"],
        schema="frota",
    )
    op.create_index(
        "ix_veiculo_ocorrencia_tenant_excluido",
        "veiculo_ocorrencia",
        ["tenant_id", "excluido"],
        schema="frota",
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON frota.veiculo_ocorrencia TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON frota.veiculo_ocorrencia_id_seq TO aprimora_app"
    )

    op.execute("ALTER TABLE frota.veiculo_ocorrencia ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE frota.veiculo_ocorrencia FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON frota.veiculo_ocorrencia
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON frota.veiculo_ocorrencia
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON frota.veiculo_ocorrencia"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON frota.veiculo_ocorrencia"
    )
    op.drop_index(
        "ix_veiculo_ocorrencia_tenant_excluido",
        table_name="veiculo_ocorrencia",
        schema="frota",
    )
    op.drop_index(
        "ix_veiculo_ocorrencia_tenant_status",
        table_name="veiculo_ocorrencia",
        schema="frota",
    )
    op.drop_index(
        "ix_veiculo_ocorrencia_tenant_veiculo",
        table_name="veiculo_ocorrencia",
        schema="frota",
    )
    op.drop_table("veiculo_ocorrencia", schema="frota")
