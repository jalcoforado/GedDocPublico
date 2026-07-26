"""Pagamentos v2.0 Onda A5 — histórico de troca de fonte da conta (RF-CTA-06).

Revision ID: 0070
Revises: 0069
Create Date: 2026-07-26

RF-CTA-06: a alteração da fonte vinculada a uma conta só por usuário autorizado,
mediante justificativa, data de vigência e preservação do histórico. Tabela
append-only `conta_fonte_historico` no schema `pagamentos`, com RLS + GRANTs.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0070"
down_revision: str | Sequence[str] | None = "0069"
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


def _grant(t: str) -> None:
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.{t} TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.{t}_id_seq TO aprimora_app")


def upgrade() -> None:
    op.create_table(
        "conta_fonte_historico",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_conta", sa.Integer(), sa.ForeignKey(f"{S}.conta_bancaria.id"), nullable=False),
        sa.Column("id_fonte_anterior", sa.Integer(), sa.ForeignKey(f"{S}.fonte_recursos.id"), nullable=True),
        sa.Column("id_fonte_nova", sa.Integer(), sa.ForeignKey(f"{S}.fonte_recursos.id"), nullable=False),
        sa.Column("justificativa", sa.String(255), nullable=False),
        sa.Column("vigencia", sa.Date(), nullable=False),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        schema=S,
    )
    op.create_index("ix_contafontehist_tenant_conta", "conta_fonte_historico",
                    ["tenant_id", "id_conta"], schema=S)
    _enable_rls("conta_fonte_historico")
    _grant("conta_fonte_historico")


def downgrade() -> None:
    op.execute(f"DROP TABLE {S}.conta_fonte_historico CASCADE")
