"""Notificacao preferencias por usuário — Fase 17b.

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-26

Cria `aprimora_py.notificacao_preferencia` (1 linha por usuário do tenant).
Defaults sensatos: in_app=true, email=true, whatsapp=false. Se a row não
existe pro usuário, o motor de notificações assume defaults.

A constraint UNIQUE em (tenant_id, id_usuario) é o que torna a tabela
"slot por usuário". Não tem cascade: deletar usuário deixa órfão; OK
porque tabela é pequena e gestão fica em rotina de limpeza posterior.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notificacao_preferencia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "id_usuario",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=False,
        ),
        sa.Column(
            "canal_in_app",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "canal_email",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "canal_whatsapp",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
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
        "uq_notificacao_preferencia_tenant_usuario",
        "notificacao_preferencia",
        ["tenant_id", "id_usuario"],
        schema="aprimora_py",
        unique=True,
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "aprimora_py.notificacao_preferencia TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON aprimora_py.notificacao_preferencia_id_seq TO aprimora_app"
    )

    op.execute(
        "ALTER TABLE aprimora_py.notificacao_preferencia ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE aprimora_py.notificacao_preferencia FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON aprimora_py.notificacao_preferencia
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON aprimora_py.notificacao_preferencia
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON aprimora_py.notificacao_preferencia"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON aprimora_py.notificacao_preferencia"
    )
    op.drop_index(
        "uq_notificacao_preferencia_tenant_usuario",
        table_name="notificacao_preferencia",
        schema="aprimora_py",
    )
    op.drop_table("notificacao_preferencia", schema="aprimora_py")
