"""Pagamentos F3 (Task 4) — amplia ck_debhist_acao para FILA_REAVALIADA.

Revision ID: 0110
Revises: 0109
Create Date: 2026-08-26

`reavaliar_debito` (F3, Task 4) grava `FILA_REAVALIADA` em
`pagamentos.debito_historico.acao` sempre que a elegibilidade da fila
cronológica muda em decorrência de um evento externo (fornecedor, bloqueio de
saldo, saldo disponível, exceção cronológica) — e o CHECK ali
(`ck_debhist_acao`, de 0069/0086/0087/0106/0109) não a contemplava.

Cabe no `VARCHAR(30)` que a 0106 já alargou — sem alteração de coluna aqui.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0110"
down_revision: str | Sequence[str] | None = "0109"
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
    "REENVIADO", "APROVACOES_INVALIDADAS", "MARCO_REGRAVADO",
)
ACOES_NOVAS = ("FILA_REAVALIADA",)


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
