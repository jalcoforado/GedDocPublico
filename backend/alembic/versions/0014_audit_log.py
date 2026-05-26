"""Audit log — Fase 24.

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-26

Tabela `aprimora_py.audit_log` para rastrear QUEM fez O QUÊ. Append-only
(sem UPDATE/DELETE) — auditoria precisa ser imutável. Não vamos confiar
em triggers PG (legacy do PHP setava `SET LOCAL` pra capturar usuario);
o motor Python passa `id_usuario` explicitamente no `Acao`.

Convenção pra `acao`:
  <entidade>.<verbo>      ex: processo.encaminhado, processo.arquivado,
                              workflow_instance.transicionada,
                              usuario.criado, anexo.uploaded

`entidade` + `id_entidade` apontam pro registro afetado. `payload` é um
JSONB livre com dados relevantes pra reconstrução (estados antes/depois,
parâmetros, etc).

`request_id` é o ID gerado pelo `RequestLoggingMiddleware` (Fase 33) — liga
auditoria DB ao log JSON do request. Útil pra investigar incidentes.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
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
            nullable=True,
        ),
        sa.Column("acao", sa.String(length=80), nullable=False),
        sa.Column("entidade", sa.String(length=60), nullable=False),
        sa.Column("id_entidade", sa.BigInteger(), nullable=True),
        sa.Column(
            "payload",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="aprimora_py",
    )

    op.create_index(
        "ix_audit_log_tenant_criado",
        "audit_log",
        ["tenant_id", "criado_em"],
        schema="aprimora_py",
    )
    op.create_index(
        "ix_audit_log_entidade",
        "audit_log",
        ["tenant_id", "entidade", "id_entidade", "criado_em"],
        schema="aprimora_py",
    )
    op.create_index(
        "ix_audit_log_usuario",
        "audit_log",
        ["tenant_id", "id_usuario", "criado_em"],
        schema="aprimora_py",
    )

    op.execute(
        "GRANT SELECT, INSERT ON aprimora_py.audit_log TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON aprimora_py.audit_log_id_seq TO aprimora_app"
    )

    op.execute("ALTER TABLE aprimora_py.audit_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aprimora_py.audit_log FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON aprimora_py.audit_log
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_insert ON aprimora_py.audit_log
            FOR INSERT
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_insert ON aprimora_py.audit_log"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON aprimora_py.audit_log"
    )
    op.drop_index(
        "ix_audit_log_usuario", table_name="audit_log", schema="aprimora_py"
    )
    op.drop_index(
        "ix_audit_log_entidade", table_name="audit_log", schema="aprimora_py"
    )
    op.drop_index(
        "ix_audit_log_tenant_criado", table_name="audit_log", schema="aprimora_py"
    )
    op.drop_table("audit_log", schema="aprimora_py")
