"""Workflow SLA alertas — Fase 21.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-23

Cria `aprimora_py.workflow_sla_alerta` para registrar quando uma
WorkflowInstance permanece em um estado por mais tempo do que `sla_dias`
(definido no DSL).

Dedup por (id_workflow_instance, estado): a task beat só insere um novo
alerta por (instance, estado) se NÃO existir um já ATIVO (resolvido_em IS
NULL). Quando a instance sai do estado, alertas pendentes naquele estado
são auto-resolvidos pelo engine (executar_transicao).

RLS + grants para `aprimora_app` seguem o mesmo padrão das outras tabelas.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_sla_alerta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "id_workflow_instance",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.workflow_instance.id"),
            nullable=False,
        ),
        sa.Column("estado", sa.String(length=50), nullable=False),
        sa.Column("sla_dias", sa.Integer(), nullable=False),
        sa.Column("dias_no_estado", sa.Integer(), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("resolvido_em", sa.DateTime(), nullable=True),
        sa.Column("resolucao", sa.String(length=40), nullable=True),
        sa.Column("notificado_em", sa.DateTime(), nullable=True),
        schema="aprimora_py",
    )

    # Lookup rápido por tenant + estado ativo da listagem
    op.create_index(
        "ix_workflow_sla_alerta_tenant_resolvido",
        "workflow_sla_alerta",
        ["tenant_id", "resolvido_em"],
        schema="aprimora_py",
    )

    # Dedup: 1 alerta ATIVO por (instance, estado). Índice parcial — uma
    # vez resolvido (resolvido_em IS NOT NULL), permite novo alerta se
    # houver reentrada futura no mesmo estado.
    op.create_index(
        "uq_workflow_sla_alerta_instance_estado_ativo",
        "workflow_sla_alerta",
        ["id_workflow_instance", "estado"],
        schema="aprimora_py",
        unique=True,
        postgresql_where=sa.text("resolvido_em IS NULL"),
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "aprimora_py.workflow_sla_alerta TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON aprimora_py.workflow_sla_alerta_id_seq TO aprimora_app"
    )

    op.execute(
        "ALTER TABLE aprimora_py.workflow_sla_alerta ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE aprimora_py.workflow_sla_alerta FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON aprimora_py.workflow_sla_alerta
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON aprimora_py.workflow_sla_alerta
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON aprimora_py.workflow_sla_alerta"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON aprimora_py.workflow_sla_alerta"
    )
    op.drop_index(
        "uq_workflow_sla_alerta_instance_estado_ativo",
        table_name="workflow_sla_alerta",
        schema="aprimora_py",
    )
    op.drop_index(
        "ix_workflow_sla_alerta_tenant_resolvido",
        table_name="workflow_sla_alerta",
        schema="aprimora_py",
    )
    op.drop_table("workflow_sla_alerta", schema="aprimora_py")
