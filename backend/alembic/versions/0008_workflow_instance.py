"""Workflow instance + transição log — Fase 20a (engine de transições).

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-23

Duas tabelas novas:

- `workflow_instance`: uma execução concreta de um workflow_definition,
  ligada a um processo (1-1 enquanto a instance estiver ativa; processos
  podem ter múltiplas instances ao longo da vida, mas só uma ativa por vez).
  Aponta para a versão EXATA do workflow_definition (id), não para o slug —
  garante que evoluções do DSL não impactam instâncias em execução.

- `workflow_transicao_log`: auditoria append-only de cada transição
  executada. Guarda estado_de, estado_para, label, usuario, timestamp e um
  snapshot do contexto avaliado (JSONB) — útil para debug/auditoria.

Ambas com RLS habilitado igual ao padrão da migration 0006.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ===== workflow_instance =====
    op.create_table(
        "workflow_instance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "id_workflow_definition",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.workflow_definition.id"),
            nullable=False,
        ),
        sa.Column(
            "id_processo",
            sa.Integer(),
            sa.ForeignKey("protocolos.processo.id"),
            nullable=False,
        ),
        sa.Column("estado_atual", sa.String(length=50), nullable=False),
        sa.Column(
            "ativa",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "iniciada_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("finalizada_em", sa.DateTime(), nullable=True),
        sa.Column(
            "id_usuario_inicio",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=True,
        ),
        schema="aprimora_py",
    )

    # 1 instance ATIVA por processo (regra de negócio). Index parcial.
    op.execute(
        """
        CREATE UNIQUE INDEX ix_workflow_instance_processo_ativa
        ON aprimora_py.workflow_instance (id_processo)
        WHERE ativa IS TRUE
        """
    )

    op.create_index(
        "ix_workflow_instance_tenant_processo",
        "workflow_instance",
        ["tenant_id", "id_processo"],
        schema="aprimora_py",
    )

    # ===== workflow_transicao_log =====
    op.create_table(
        "workflow_transicao_log",
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
        sa.Column("estado_de", sa.String(length=50), nullable=False),
        sa.Column("estado_para", sa.String(length=50), nullable=False),
        sa.Column("transicao_label", sa.String(length=120), nullable=False),
        sa.Column(
            "id_usuario",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=True,
        ),
        sa.Column("contexto_snapshot", JSONB(), nullable=True),
        sa.Column(
            "executada_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="aprimora_py",
    )

    op.create_index(
        "ix_wf_log_instance",
        "workflow_transicao_log",
        ["id_workflow_instance", "executada_em"],
        schema="aprimora_py",
    )

    # GRANTs + RLS para ambas as tabelas
    for tab in ("workflow_instance", "workflow_transicao_log"):
        fq = f"aprimora_py.{tab}"
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {fq} TO aprimora_app"
        )
        op.execute(
            f"GRANT USAGE, SELECT ON aprimora_py.{tab}_id_seq TO aprimora_app"
        )
        op.execute(f"ALTER TABLE {fq} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {fq} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_select ON {fq}
                FOR SELECT
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_modify ON {fq}
                FOR ALL
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            """
        )


def downgrade() -> None:
    for tab in ("workflow_transicao_log", "workflow_instance"):
        fq = f"aprimora_py.{tab}"
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {fq}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {fq}")

    op.drop_index(
        "ix_wf_log_instance",
        table_name="workflow_transicao_log",
        schema="aprimora_py",
    )
    op.drop_table("workflow_transicao_log", schema="aprimora_py")

    op.drop_index(
        "ix_workflow_instance_tenant_processo",
        table_name="workflow_instance",
        schema="aprimora_py",
    )
    op.execute("DROP INDEX IF EXISTS aprimora_py.ix_workflow_instance_processo_ativa")
    op.drop_table("workflow_instance", schema="aprimora_py")
