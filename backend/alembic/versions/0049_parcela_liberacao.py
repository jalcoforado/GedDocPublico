"""Pagamentos — liberação de pagamento (parcela LIBERADA) + guards do rito completo.

ALTER `pagamentos.parcela`: widen CHECK de status (+'LIBERADA') e 3 colunas novas
(data_liberacao, id_usuario_liberacao, data_prevista_pagamento). ALTER
`pagamentos.debito_historico`: widen CHECK de acao (+'LIBERADO','LIBERACAO_REVOGADA').
Sem tabela nova — RLS já cobre (migration 0048).

Revision ID: 0049
Revises: 0048
Create Date: 2026-07-16
"""
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0049"
down_revision: str | Sequence[str] | None = "0048"
branch_labels = None
depends_on = None
S = "pagamentos"


def upgrade() -> None:
    op.add_column("parcela", sa.Column("data_liberacao", sa.Date(), nullable=True), schema=S)
    op.add_column("parcela", sa.Column(
        "id_usuario_liberacao", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True), schema=S)
    op.add_column("parcela", sa.Column("data_prevista_pagamento", sa.Date(), nullable=True), schema=S)

    op.drop_constraint("ck_parcela_status", "parcela", schema=S, type_="check")
    op.create_check_constraint(
        "ck_parcela_status", "parcela",
        "status IN ('A_PAGAR','LIBERADA','PAGA','CANCELADA')", schema=S)

    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")
    op.create_check_constraint(
        "ck_debhist_acao", "debito_historico",
        "acao IN ('CRIADO','ENVIADO','APROVADO','DEVOLVIDO','REJEITADO',"
        "'AUTORIZADO','LIBERADO','LIBERACAO_REVOGADA','PAGAMENTO','ESTORNO','CANCELADO')",
        schema=S)


def downgrade() -> None:
    # Reversão dev-friendly: parcelas LIBERADAS voltam a A_PAGAR (limpando os campos
    # novos) antes de o CHECK antigo ser reaplicado; histórico é append-only, mas as
    # ações novas (LIBERADO/LIBERACAO_REVOGADA) não existem no CHECK antigo — as
    # linhas correspondentes são removidas (aceitável em downgrade de ambiente dev;
    # não há downgrade em produção para esta migration).
    op.execute(
        f"UPDATE {S}.parcela SET status='A_PAGAR', data_liberacao=NULL, "
        f"id_usuario_liberacao=NULL, data_prevista_pagamento=NULL WHERE status='LIBERADA'"
    )
    op.execute(
        f"DELETE FROM {S}.debito_historico WHERE acao IN ('LIBERADO','LIBERACAO_REVOGADA')"
    )

    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")
    op.create_check_constraint(
        "ck_debhist_acao", "debito_historico",
        "acao IN ('CRIADO','ENVIADO','APROVADO','DEVOLVIDO','REJEITADO',"
        "'AUTORIZADO','PAGAMENTO','ESTORNO','CANCELADO')", schema=S)

    op.drop_constraint("ck_parcela_status", "parcela", schema=S, type_="check")
    op.create_check_constraint(
        "ck_parcela_status", "parcela", "status IN ('A_PAGAR','PAGA','CANCELADA')", schema=S)

    op.drop_column("parcela", "data_prevista_pagamento", schema=S)
    op.drop_column("parcela", "id_usuario_liberacao", schema=S)
    op.drop_column("parcela", "data_liberacao", schema=S)
