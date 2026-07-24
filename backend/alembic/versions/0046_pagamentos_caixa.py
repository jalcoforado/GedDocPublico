"""Pagamentos R1 — caixa: rename credor→fornecedor, saldo_inicial, movimentacao_conta.

Revision ID: 0046
Revises: 0045
Create Date: 2026-07-14
"""
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: str | Sequence[str] | None = "0045"
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
    # 1) rename credor -> fornecedor (policies/GRANTs seguem o OID; renomeia seq/índices/constraints/coluna FK)
    op.execute(f"ALTER TABLE {S}.credor RENAME TO fornecedor")
    op.execute(f"ALTER SEQUENCE {S}.credor_id_seq RENAME TO fornecedor_id_seq")
    op.execute(f"ALTER INDEX {S}.uq_credor_tenant_doc RENAME TO uq_fornecedor_tenant_doc")
    op.execute(f"ALTER INDEX {S}.ix_credor_tenant_excluido RENAME TO ix_fornecedor_tenant_excluido")
    op.execute(f"ALTER TABLE {S}.fornecedor RENAME CONSTRAINT ck_credor_tipo_pessoa TO ck_fornecedor_tipo_pessoa")
    op.execute(f"ALTER TABLE {S}.fornecedor RENAME CONSTRAINT ck_credor_situacao TO ck_fornecedor_situacao")
    # contrato.id_credor -> id_fornecedor
    op.execute(f"ALTER TABLE {S}.contrato RENAME COLUMN id_credor TO id_fornecedor")
    op.execute(f"ALTER INDEX {S}.ix_contrato_credor RENAME TO ix_contrato_fornecedor")

    # 2) conta_bancaria.saldo_inicial
    op.add_column("conta_bancaria",
                  sa.Column("saldo_inicial", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
                  schema=S)

    # 3) movimentacao_conta
    op.create_table(
        "movimentacao_conta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_conta", sa.Integer(), sa.ForeignKey(f"{S}.conta_bancaria.id"), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("origem", sa.String(20), nullable=False),
        sa.Column("id_debito", sa.Integer(), nullable=True),      # FK criada no R2 (tabela debito ainda não existe)
        sa.Column("id_parcela", sa.Integer(), nullable=True),     # idem
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("descricao", sa.String(255), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.CheckConstraint("tipo IN ('ENTRADA','SAIDA')", name="ck_movconta_tipo"),
        sa.CheckConstraint("origem IN ('APORTE','RECEITA','AJUSTE','PAGAMENTO','ESTORNO')", name="ck_movconta_origem"),
        sa.CheckConstraint("valor > 0", name="ck_movconta_valor_positivo"),
        schema=S,
    )
    op.create_index("ix_movconta_tenant_conta", "movimentacao_conta", ["tenant_id", "id_conta"], schema=S)
    op.create_index("ix_movconta_tenant_excluido", "movimentacao_conta", ["tenant_id", "excluido"], schema=S)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.movimentacao_conta TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.movimentacao_conta_id_seq TO aprimora_app")
    _enable_rls("movimentacao_conta")


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {S}.movimentacao_conta")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {S}.movimentacao_conta")
    op.drop_index("ix_movconta_tenant_excluido", table_name="movimentacao_conta", schema=S)
    op.drop_index("ix_movconta_tenant_conta", table_name="movimentacao_conta", schema=S)
    op.drop_table("movimentacao_conta", schema=S)
    op.drop_column("conta_bancaria", "saldo_inicial", schema=S)
    op.execute(f"ALTER INDEX {S}.ix_contrato_fornecedor RENAME TO ix_contrato_credor")
    op.execute(f"ALTER TABLE {S}.contrato RENAME COLUMN id_fornecedor TO id_credor")
    op.execute(f"ALTER TABLE {S}.fornecedor RENAME CONSTRAINT ck_fornecedor_situacao TO ck_credor_situacao")
    op.execute(f"ALTER TABLE {S}.fornecedor RENAME CONSTRAINT ck_fornecedor_tipo_pessoa TO ck_credor_tipo_pessoa")
    op.execute(f"ALTER INDEX {S}.ix_fornecedor_tenant_excluido RENAME TO ix_credor_tenant_excluido")
    op.execute(f"ALTER INDEX {S}.uq_fornecedor_tenant_doc RENAME TO uq_credor_tenant_doc")
    op.execute(f"ALTER SEQUENCE {S}.fornecedor_id_seq RENAME TO credor_id_seq")
    op.execute(f"ALTER TABLE {S}.fornecedor RENAME TO credor")
