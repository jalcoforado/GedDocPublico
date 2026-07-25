"""Pagamentos v2.0 Fase 2 — bloqueio de saldo + histórico diário de saldo.

Revision ID: 0064
Revises: 0063
Create Date: 2026-07-25

RF-SLD-03/07 (spec seção 10): duas tabelas novas no schema `pagamentos`:
- bloqueio_saldo: valores administrativamente bloqueados numa conta por período
  (reduzem o disponível projetado).
- saldo_historico: snapshot diário dos saldos por conta (preenchido por job).
Ambas com RLS por tenant + GRANTs à role aprimora_app (padrão 0048).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0064"
down_revision: str | Sequence[str] | None = "0063"
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
        "bloqueio_saldo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_conta", sa.Integer(), sa.ForeignKey(f"{S}.conta_bancaria.id"), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("motivo", sa.String(255), nullable=False),
        sa.Column("periodo_inicio", sa.Date(), nullable=False),
        sa.Column("periodo_fim", sa.Date(), nullable=True),  # aberto = sem término
        sa.Column("id_usuario_responsavel", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.CheckConstraint("valor > 0", name="ck_bloqueio_valor_positivo"),
        schema=S,
    )
    op.create_index("ix_bloqueio_tenant_conta", "bloqueio_saldo",
                    ["tenant_id", "id_conta", "ativo"], schema=S)

    op.create_table(
        "saldo_historico",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_conta", sa.Integer(), sa.ForeignKey(f"{S}.conta_bancaria.id"), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("saldo_bancario", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("saldo_conciliado", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("saldo_reservado", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("saldo_bloqueado", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("tenant_id", "id_conta", "data", name="uq_saldohist_conta_data"),
        schema=S,
    )
    op.create_index("ix_saldohist_tenant_conta_data", "saldo_historico",
                    ["tenant_id", "id_conta", "data"], schema=S)

    for t in ("bloqueio_saldo", "saldo_historico"):
        _grant(t)
        _enable_rls(t)


def downgrade() -> None:
    for t in ("saldo_historico", "bloqueio_saldo"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {S}.{t}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {S}.{t}")
        op.drop_table(t, schema=S)
