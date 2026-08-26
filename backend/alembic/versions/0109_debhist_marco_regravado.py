"""Pagamentos F3 (Task 2) — amplia ck_debhist_acao para MARCO_REGRAVADO.

Revision ID: 0109
Revises: 0108
Create Date: 2026-08-25

`atualizar_debito` (F3) passa a gravar `MARCO_REGRAVADO` em
`pagamentos.debito_historico.acao` quando uma edição material troca
`data_liquidacao` de um débito que já tem posição na fila cronológica — e o
CHECK ali (`ck_debhist_acao`, de 0069/0086/0087/0106) não a contemplava.

Cabe nos `VARCHAR(30)` que a 0106 já alargou — sem alteração de coluna aqui.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0109"
down_revision: str | Sequence[str] | None = "0108"
branch_labels = None
depends_on = None
S = "pagamentos"

ACAO_ANTERIOR = (
    "CRIADO", "ENVIADO", "APROVADO", "VALIDADO", "ENCAMINHADO", "DEVOLVIDO",
    "REJEITADO", "AUTORIZADO", "LIBERADO", "LIBERACAO_REVOGADA", "PAGAMENTO",
    "ESTORNO", "CANCELADO", "LIQUIDADO", "SUSPENSO", "REATIVADO", "CONCILIADO",
    "AUTORIZADO_GESTOR", "REJEITADO_GESTOR", "AJUSTE_SOLICITADO",
    "AJUSTE_RESPONDIDO", "INDEFERIDO",
    "ENVIADO_TESOURARIA", "REVOGADO", "PAGO", "PROCESSANDO", "ESTORNADO",
    "REENVIADO", "APROVACOES_INVALIDADAS",
)
ACOES_NOVAS = ("MARCO_REGRAVADO",)


def _in(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


def upgrade() -> None:
    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")
    op.create_check_constraint(
        "ck_debhist_acao", "debito_historico",
        f"acao IN ({_in(ACAO_ANTERIOR + ACOES_NOVAS)})", schema=S,
    )


def downgrade() -> None:
    op.execute(
        f"DELETE FROM {S}.debito_historico WHERE acao IN ({_in(ACOES_NOVAS)})"
    )
    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")
    op.create_check_constraint(
        "ck_debhist_acao", "debito_historico",
        f"acao IN ({_in(ACAO_ANTERIOR)})", schema=S,
    )
