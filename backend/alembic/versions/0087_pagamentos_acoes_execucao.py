"""Pagamentos F1 — alinha o histórico aos eventos da execução financeira.

Revision ID: 0087
Revises: 0086
Create Date: 2026-08-07

Os serviços de tesouraria registram nomes de evento distintos dos estados
derivados do débito. A restrição criada antes da separação em três dimensões
não contemplava esses eventos e fazia a transação falhar no commit.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0087"
down_revision: str | Sequence[str] | None = "0086"
branch_labels = None
depends_on = None
S = "pagamentos"

ACAO_ANTIGA = (
    "CRIADO", "ENVIADO", "APROVADO", "VALIDADO", "ENCAMINHADO", "DEVOLVIDO",
    "REJEITADO", "AUTORIZADO", "LIBERADO", "LIBERACAO_REVOGADA", "PAGAMENTO",
    "ESTORNO", "CANCELADO", "LIQUIDADO", "SUSPENSO", "REATIVADO", "CONCILIADO",
    "AUTORIZADO_GESTOR", "REJEITADO_GESTOR", "AJUSTE_SOLICITADO",
    "AJUSTE_RESPONDIDO", "INDEFERIDO",
)
ACOES_EXECUCAO = (
    "ENVIADO_TESOURARIA", "REVOGADO", "PAGO", "PROCESSANDO", "ESTORNADO",
)


def _in(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


def upgrade() -> None:
    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")
    op.create_check_constraint(
        "ck_debhist_acao", "debito_historico",
        f"acao IN ({_in(ACAO_ANTIGA + ACOES_EXECUCAO)})", schema=S,
    )


def downgrade() -> None:
    op.execute(
        f"DELETE FROM {S}.debito_historico WHERE acao IN ({_in(ACOES_EXECUCAO)})"
    )
    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")
    op.create_check_constraint(
        "ck_debhist_acao", "debito_historico",
        f"acao IN ({_in(ACAO_ANTIGA)})", schema=S,
    )
