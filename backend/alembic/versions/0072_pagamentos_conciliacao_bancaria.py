"""Pagamentos v2.0 Onda B — conciliação bancária (Fase 3, RF-EXT-01..10, seção 12/19).

Revision ID: 0072
Revises: 0071
Create Date: 2026-07-26

Três tabelas novas no schema `pagamentos` (RLS + GRANTs):
- extrato: arquivo de extrato importado (conta, período, hash, formato, status).
- lancamento_extrato: linhas do extrato (data, histórico, documento, favorecido,
  valor, tipo CREDITO/DEBITO, conciliado).
- conciliacao: correspondência entre um lançamento do extrato e a movimentação
  (pagamento) da conta, com tipo (EXATA/PROVAVEL/DIVERGENTE/DUPLICADA/NAO_IDENTIFICADA).

Também amplia ck_debito_status já contém CONCILIADO (0069) e ck_debhist_acao já
contém CONCILIADO (0069), então aqui só criamos as tabelas.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0072"
down_revision: str | Sequence[str] | None = "0071"
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
        "extrato",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_conta", sa.Integer(), sa.ForeignKey(f"{S}.conta_bancaria.id"), nullable=False),
        sa.Column("periodo_inicio", sa.Date(), nullable=True),
        sa.Column("periodo_fim", sa.Date(), nullable=True),
        sa.Column("nome_arquivo", sa.String(255), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("formato", sa.String(10), nullable=False),
        sa.Column("status_processamento", sa.String(20), nullable=False, server_default="IMPORTADO"),
        sa.Column("qtd_lancamentos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("importado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.CheckConstraint("status_processamento IN ('IMPORTADO','PROCESSADO','ERRO')",
                           name="ck_extrato_status"),
        sa.CheckConstraint("formato IN ('OFX','CSV','XLSX','CNAB')", name="ck_extrato_formato"),
        sa.UniqueConstraint("tenant_id", "id_conta", "hash", name="uq_extrato_conta_hash"),
        schema=S,
    )
    op.create_index("ix_extrato_tenant_conta", "extrato", ["tenant_id", "id_conta"], schema=S)
    _enable_rls("extrato")
    _grant("extrato")

    op.create_table(
        "lancamento_extrato",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_extrato", sa.Integer(), sa.ForeignKey(f"{S}.extrato.id"), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("historico", sa.String(255), nullable=False),
        sa.Column("documento", sa.String(50), nullable=True),
        sa.Column("favorecido", sa.String(150), nullable=True),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("conciliado", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("tipo IN ('CREDITO','DEBITO')", name="ck_lancamento_tipo"),
        schema=S,
    )
    op.create_index("ix_lancamento_tenant_extrato", "lancamento_extrato",
                    ["tenant_id", "id_extrato"], schema=S)
    _enable_rls("lancamento_extrato")
    _grant("lancamento_extrato")

    op.create_table(
        "conciliacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_lancamento", sa.Integer(),
                  sa.ForeignKey(f"{S}.lancamento_extrato.id"), nullable=False),
        sa.Column("id_movimentacao", sa.Integer(),
                  sa.ForeignKey(f"{S}.movimentacao_conta.id"), nullable=True),
        sa.Column("id_parcela", sa.Integer(), sa.ForeignKey(f"{S}.parcela.id"), nullable=True),
        sa.Column("tipo_correspondencia", sa.String(15), nullable=False),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "tipo_correspondencia IN ('EXATA','PROVAVEL','DIVERGENTE','DUPLICADA','NAO_IDENTIFICADA')",
            name="ck_conciliacao_tipo"),
        # RN-14: um lançamento e uma movimentação conciliam no máximo uma vez.
        sa.UniqueConstraint("tenant_id", "id_lancamento", name="uq_conciliacao_lancamento"),
        sa.UniqueConstraint("tenant_id", "id_movimentacao", name="uq_conciliacao_movimentacao"),
        schema=S,
    )
    op.create_index("ix_conciliacao_tenant", "conciliacao", ["tenant_id"], schema=S)
    _enable_rls("conciliacao")
    _grant("conciliacao")


def downgrade() -> None:
    op.execute(f"DROP TABLE {S}.conciliacao CASCADE")
    op.execute(f"DROP TABLE {S}.lancamento_extrato CASCADE")
    op.execute(f"DROP TABLE {S}.extrato CASCADE")
