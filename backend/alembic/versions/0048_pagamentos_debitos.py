"""Pagamentos R2 — débito, parcela, histórico, ordem de pagamento + RBAC.

Revision ID: 0048
Revises: 0047
Create Date: 2026-07-14
"""
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0048"
down_revision: str | Sequence[str] | None = "0047"
branch_labels = None
depends_on = None
S = "pagamentos"

TRANSACOES = [
    ("Solicitar Pagamento", "pagamento_solicitar"),
    ("Aprovar Pagamento", "pagamento_aprovar"),
    ("Autorizar Pagamento", "pagamento_autorizar"),
    ("Pagar — Tesouraria", "pagamento_pagar"),
]


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
        "debito",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_fornecedor", sa.Integer(), sa.ForeignKey(f"{S}.fornecedor.id"), nullable=False),
        sa.Column("id_natureza", sa.Integer(), sa.ForeignKey(f"{S}.natureza_despesa.id"), nullable=False),
        sa.Column("id_conta", sa.Integer(), sa.ForeignKey(f"{S}.conta_bancaria.id"), nullable=False),
        sa.Column("id_contrato", sa.Integer(), sa.ForeignKey(f"{S}.contrato.id"), nullable=True),
        sa.Column("valor_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("competencia", sa.String(7), nullable=False),  # 'YYYY-MM'
        sa.Column("numero_ne", sa.String(30), nullable=True),
        sa.Column("numero_nf", sa.String(40), nullable=True),
        sa.Column("criticidade", sa.String(10), nullable=False, server_default="MEDIA"),
        sa.Column("urgente", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("justificativa_urgencia", sa.String(255), nullable=True),
        sa.Column("descricao", sa.String(255), nullable=False),
        sa.Column("status", sa.String(25), nullable=False, server_default="RASCUNHO"),
        sa.Column("id_usuario_solicitante", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.CheckConstraint("valor_total > 0", name="ck_debito_valor_positivo"),
        sa.CheckConstraint(
            "status IN ('RASCUNHO','AGUARDANDO_APROVACAO','APROVADO','AUTORIZADO',"
            "'PAGO_PARCIAL','PAGO','REJEITADO','CANCELADO')", name="ck_debito_status"),
        sa.CheckConstraint("criticidade IN ('URGENTE','ALTA','MEDIA','BAIXA')", name="ck_debito_criticidade"),
        schema=S,
    )
    op.create_index("ix_debito_tenant_status", "debito", ["tenant_id", "status"], schema=S)
    op.create_index("ix_debito_tenant_conta", "debito", ["tenant_id", "id_conta"], schema=S)
    op.create_index("ix_debito_tenant_solicitante", "debito", ["tenant_id", "id_usuario_solicitante"], schema=S)

    op.create_table(
        "parcela",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_debito", sa.Integer(), sa.ForeignKey(f"{S}.debito.id"), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("vencimento", sa.Date(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="A_PAGAR"),
        sa.Column("data_pagamento", sa.Date(), nullable=True),
        sa.Column("forma_pagamento", sa.String(20), nullable=True),
        sa.Column("id_movimentacao", sa.Integer(), sa.ForeignKey(f"{S}.movimentacao_conta.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.CheckConstraint("valor > 0", name="ck_parcela_valor_positivo"),
        sa.CheckConstraint("status IN ('A_PAGAR','PAGA','CANCELADA')", name="ck_parcela_status"),
        sa.UniqueConstraint("id_debito", "numero", name="uq_parcela_debito_numero"),
        schema=S,
    )
    op.create_index("ix_parcela_tenant_debito", "parcela", ["tenant_id", "id_debito"], schema=S)
    op.create_index("ix_parcela_tenant_status_venc", "parcela", ["tenant_id", "status", "vencimento"], schema=S)

    op.create_table(  # append-only: sem excluido/atualizado_em
        "debito_historico",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_debito", sa.Integer(), sa.ForeignKey(f"{S}.debito.id"), nullable=False),
        sa.Column("status_anterior", sa.String(25), nullable=True),
        sa.Column("status_novo", sa.String(25), nullable=False),
        sa.Column("acao", sa.String(20), nullable=False),
        sa.Column("justificativa", sa.String(255), nullable=True),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("ip_origem", sa.String(45), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "acao IN ('CRIADO','ENVIADO','APROVADO','DEVOLVIDO','REJEITADO',"
            "'AUTORIZADO','PAGAMENTO','ESTORNO','CANCELADO')", name="ck_debhist_acao"),
        schema=S,
    )
    op.create_index("ix_debhist_tenant_debito", "debito_historico", ["tenant_id", "id_debito"], schema=S)

    op.create_table(  # append-only
        "ordem_pagamento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("numero", sa.String(20), nullable=False),
        sa.Column("id_usuario_autorizador", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=False),
        sa.Column("valor_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("ip_origem", sa.String(45), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("tenant_id", "numero", name="uq_op_tenant_numero"),
        schema=S,
    )

    op.create_table(  # N:N OP x débito
        "ordem_pagamento_debito",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_ordem", sa.Integer(), sa.ForeignKey(f"{S}.ordem_pagamento.id"), nullable=False),
        sa.Column("id_debito", sa.Integer(), sa.ForeignKey(f"{S}.debito.id"), nullable=False),
        sa.UniqueConstraint("id_ordem", "id_debito", name="uq_opdeb_ordem_debito"),
        schema=S,
    )
    op.create_index("ix_opdeb_tenant_ordem", "ordem_pagamento_debito", ["tenant_id", "id_ordem"], schema=S)

    for t in ("debito", "parcela", "debito_historico", "ordem_pagamento", "ordem_pagamento_debito"):
        _grant(t)
        _enable_rls(t)

    # FKs prometidas no R1 (movimentacao_conta.id_debito/id_parcela eram Integer soltos)
    op.create_foreign_key("fk_movconta_debito", "movimentacao_conta", "debito",
                          ["id_debito"], ["id"], source_schema=S, referent_schema=S)
    op.create_foreign_key("fk_movconta_parcela", "movimentacao_conta", "parcela",
                          ["id_parcela"], ["id"], source_schema=S, referent_schema=S)

    # RBAC (idempotente, padrão 0045)
    for nome, codigo in TRANSACOES:
        op.execute(
            f"""INSERT INTO utils.transacao (transacao, codigo)
                SELECT '{nome}', '{codigo}'
                WHERE NOT EXISTS (SELECT 1 FROM utils.transacao WHERE codigo = '{codigo}')"""
        )


def downgrade() -> None:
    for _, codigo in TRANSACOES:
        op.execute(f"DELETE FROM utils.grupo_transacao WHERE id_transacao IN "
                   f"(SELECT id FROM utils.transacao WHERE codigo='{codigo}')")
        op.execute(f"DELETE FROM utils.sistema_transacao WHERE id_transacao IN "
                   f"(SELECT id FROM utils.transacao WHERE codigo='{codigo}')")
        op.execute(f"DELETE FROM utils.transacao WHERE codigo='{codigo}'")
    op.drop_constraint("fk_movconta_parcela", "movimentacao_conta", schema=S, type_="foreignkey")
    op.drop_constraint("fk_movconta_debito", "movimentacao_conta", schema=S, type_="foreignkey")
    for t in ("ordem_pagamento_debito", "ordem_pagamento", "debito_historico", "parcela", "debito"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {S}.{t}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {S}.{t}")
        op.drop_table(t, schema=S)
