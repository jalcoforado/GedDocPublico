"""Mapeamento tipo_processo → workflow — Fase 20b.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-23

Adiciona `aprimora_py.tipo_processo_workflow` para configurar QUAL workflow
auto-instanciar quando um processo de determinado tipo é aberto.

Schema é separado (não vira coluna em `protocolos.tipo_processo`) porque:
- mantém a tabela legado intocada (princípio "ignore PHP")
- permite múltiplas relações no futuro (talvez por assunto, não só tipo_processo)
- já vem com tenant_id próprio + RLS, sem precisar de migration tocando schema externo

Único por (tenant_id, id_tipo_processo) — cada tipo_processo tem no máximo
um workflow associado.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tipo_processo_workflow",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "id_tipo_processo",
            sa.Integer(),
            sa.ForeignKey("protocolos.tipo_processo.id"),
            nullable=False,
        ),
        # slug do workflow_definition (a engine resolve pra versao ativa)
        sa.Column("slug_workflow", sa.String(length=80), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        schema="aprimora_py",
    )

    op.create_index(
        "ix_tipo_processo_workflow_tenant_tipo",
        "tipo_processo_workflow",
        ["tenant_id", "id_tipo_processo"],
        schema="aprimora_py",
        unique=True,
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "aprimora_py.tipo_processo_workflow TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON aprimora_py.tipo_processo_workflow_id_seq TO aprimora_app"
    )

    op.execute(
        "ALTER TABLE aprimora_py.tipo_processo_workflow ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE aprimora_py.tipo_processo_workflow FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON aprimora_py.tipo_processo_workflow
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON aprimora_py.tipo_processo_workflow
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON aprimora_py.tipo_processo_workflow"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON aprimora_py.tipo_processo_workflow"
    )
    op.drop_index(
        "ix_tipo_processo_workflow_tenant_tipo",
        table_name="tipo_processo_workflow",
        schema="aprimora_py",
    )
    op.drop_table("tipo_processo_workflow", schema="aprimora_py")
