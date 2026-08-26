"""Pagamentos F3 (Task 5) — amplia ck_debhist_acao para EXCECAO_AUTORIZADA.

Revision ID: 0111
Revises: 0110
Create Date: 2026-08-26

`registrar_excecao` (F3, Task 5) grava `EXCECAO_AUTORIZADA` em
`pagamentos.debito_historico.acao` quando a autoridade formaliza o furo de
ordem cronológica (LRF/lei de licitações) — e o CHECK ali (`ck_debhist_acao`,
de 0069/0086/0087/0106/0109/0110) não a contemplava.

Cabe no `VARCHAR(30)` que a 0106 já alargou (19 caracteres) — sem alteração
de coluna aqui.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0111"
down_revision: str | Sequence[str] | None = "0110"
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
    "REENVIADO", "APROVACOES_INVALIDADAS", "MARCO_REGRAVADO", "FILA_REAVALIADA",
)
ACOES_NOVAS = ("EXCECAO_AUTORIZADA",)


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
