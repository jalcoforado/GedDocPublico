"""Frota PR-6 — `frota.veiculo_documento` (documentos do veículo + alertas).

Revision ID: 0036
Revises: 0035
Create Date: 2026-06-07

Cria `frota.veiculo_documento` no schema `frota` (existente desde 0031), no mesmo
padrão de RLS/GRANTs/policies de `frota.veiculo`/`frota.solicitacao_veiculo`.

Controle simples (apenas metadados — SEM upload/anexos): cada veículo pode ter
N documentos administrativos (CRLV, seguro, licenciamento, autorização, vistoria,
outro) com data de vencimento. Alertas de vencido/a vencer são calculados na
aplicação a partir de `data_vencimento`.

- `status` (ativo/vencido/substituido/cancelado), default `ativo`; guardado na
  aplicação (String(20) comporta os valores, sem CHECK de enum — mesmo padrão de
  `situacao` em `frota.veiculo`).
- CHECK `data_emissao IS NULL OR data_emissao <= data_vencimento` como defesa em
  profundidade (também validado no schema/serviço).
- Soft-delete via `excluido`. Reaproveita a permissão `frota` (NÃO semeia
  transação nova).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: str | Sequence[str] | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "veiculo_documento",
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
        sa.Column("tipo_documento", sa.String(length=30), nullable=False),
        sa.Column("numero", sa.String(length=60), nullable=True),
        sa.Column("orgao_emissor", sa.String(length=120), nullable=True),
        sa.Column("data_emissao", sa.Date(), nullable=True),
        sa.Column("data_vencimento", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'ativo'"),
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
            "data_emissao IS NULL OR data_emissao <= data_vencimento",
            name="ck_veiculo_documento_datas_coerentes",
        ),
        schema="frota",
    )

    # Listagem por veículo (tenant + veículo) e varredura de alertas por data de
    # vencimento (tenant + vencimento).
    op.create_index(
        "ix_veiculo_documento_tenant_veiculo",
        "veiculo_documento",
        ["tenant_id", "id_veiculo"],
        schema="frota",
    )
    op.create_index(
        "ix_veiculo_documento_tenant_vencimento",
        "veiculo_documento",
        ["tenant_id", "data_vencimento"],
        schema="frota",
    )
    op.create_index(
        "ix_veiculo_documento_tenant_excluido",
        "veiculo_documento",
        ["tenant_id", "excluido"],
        schema="frota",
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON frota.veiculo_documento TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON frota.veiculo_documento_id_seq TO aprimora_app"
    )

    op.execute("ALTER TABLE frota.veiculo_documento ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE frota.veiculo_documento FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON frota.veiculo_documento
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON frota.veiculo_documento
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON frota.veiculo_documento"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON frota.veiculo_documento"
    )
    op.drop_index(
        "ix_veiculo_documento_tenant_excluido",
        table_name="veiculo_documento",
        schema="frota",
    )
    op.drop_index(
        "ix_veiculo_documento_tenant_vencimento",
        table_name="veiculo_documento",
        schema="frota",
    )
    op.drop_index(
        "ix_veiculo_documento_tenant_veiculo",
        table_name="veiculo_documento",
        schema="frota",
    )
    op.drop_table("veiculo_documento", schema="frota")
