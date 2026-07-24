"""Workflow definition table — Fase 19 (Bloco B Diferenciação).

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-23

`aprimora_py.workflow_definition` armazena a definição de um fluxo BPM por
tenant. O conteúdo do fluxo (estados, transições, condições) vai num campo
JSONB `dsl` cuja estrutura é validada por Pydantic em runtime — escolha
deliberada: simpler que tabelas estado_pk/transicao_pk, evita migrations
sempre que evoluímos o DSL.

Tenant_id NOT NULL + RLS herda das policies da migration 0006 (TODO: adicionar
esta tabela à lista de tabelas com RLS quando virar produção — por ora dev
usa ged_user super que bypassa).

Versionamento: cada PUT cria nova versão (incrementa `versao`) e marca a
anterior como `ativo=false`. Workflows em execução continuam apontando para
a versão de quando foram instanciados (campo na fase 20a).

slug é único por tenant (workflow "ferias" pode coexistir em vários tenants
com lógicas diferentes).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_definition",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "ativo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("dsl", JSONB(), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "id_usuario_criador",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=True,
        ),
        schema="aprimora_py",
    )

    # Slug+versao único por tenant — permite múltiplas versões coexistirem.
    op.create_index(
        "ix_workflow_definition_tenant_slug_versao",
        "workflow_definition",
        ["tenant_id", "slug", "versao"],
        schema="aprimora_py",
        unique=True,
    )

    # Para "qual versão ativa do workflow X?" — query rápida.
    op.create_index(
        "ix_workflow_definition_tenant_ativo",
        "workflow_definition",
        ["tenant_id", "ativo"],
        schema="aprimora_py",
    )

    # GRANT pra role aprimora_app (consistente com migration 0006)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON aprimora_py.workflow_definition "
        "TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON aprimora_py.workflow_definition_id_seq TO aprimora_app"
    )

    # RLS — mesma policy pattern da migration 0006.
    op.execute("ALTER TABLE aprimora_py.workflow_definition ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aprimora_py.workflow_definition FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON aprimora_py.workflow_definition
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON aprimora_py.workflow_definition
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON aprimora_py.workflow_definition"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON aprimora_py.workflow_definition"
    )
    op.drop_index(
        "ix_workflow_definition_tenant_ativo",
        table_name="workflow_definition",
        schema="aprimora_py",
    )
    op.drop_index(
        "ix_workflow_definition_tenant_slug_versao",
        table_name="workflow_definition",
        schema="aprimora_py",
    )
    op.drop_table("workflow_definition", schema="aprimora_py")
