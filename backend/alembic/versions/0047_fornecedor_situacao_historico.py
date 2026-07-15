"""Pagamentos — histórico de situação cadastral do fornecedor (append-only).

Cada mudança de situacao_cadastral/motivo do fornecedor grava uma linha aqui;
o "estado atual" continua desnormalizado em pagamentos.fornecedor (projeção
rápida). Tabela tenant-scoped com RLS, sem soft-delete (log imutável).

Revision ID: 0047
Revises: 0046
Create Date: 2026-07-14
"""
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: str | Sequence[str] | None = "0046"
branch_labels = None
depends_on = None
S = "pagamentos"


def _enable_rls(t: str) -> None:
    op.execute(f"ALTER TABLE {S}.{t} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.{t} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation_select ON {S}.{t} FOR SELECT "
               f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)")
    op.execute(f"CREATE POLICY tenant_isolation_modify ON {S}.{t} FOR ALL "
               f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int) "
               f"WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)")


def upgrade() -> None:
    op.create_table(
        "fornecedor_situacao_historico",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_fornecedor", sa.Integer(), sa.ForeignKey(f"{S}.fornecedor.id"), nullable=False),
        sa.Column("situacao", sa.String(10), nullable=False),
        sa.Column("motivo", sa.String(255), nullable=True),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("situacao IN ('REGULAR','PENDENTE','IRREGULAR')", name="ck_fornsit_situacao"),
        schema=S,
    )
    op.create_index("ix_fornsit_tenant_fornecedor", "fornecedor_situacao_historico",
                    ["tenant_id", "id_fornecedor"], schema=S)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.fornecedor_situacao_historico TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.fornecedor_situacao_historico_id_seq TO aprimora_app")
    _enable_rls("fornecedor_situacao_historico")


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {S}.fornecedor_situacao_historico")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {S}.fornecedor_situacao_historico")
    op.drop_index("ix_fornsit_tenant_fornecedor", table_name="fornecedor_situacao_historico", schema=S)
    op.drop_table("fornecedor_situacao_historico", schema=S)
