"""Pagamentos — amplia ck_debhist_acao para CONCILIACAO_DESFEITA.

Revision ID: 0133
Revises: 0132
Create Date: 2026-10-11

`pagamentos_conciliacao.desfazer_conciliacao` devolve o débito de CONCILIADA a
PAGA e grava `CONCILIACAO_DESFEITA` em `pagamentos.debito_historico.acao`. O
CHECK ali (`ck_debhist_acao`, de 0069/.../0111/0121) não a contemplava: sem
esta migration o desfazer morre em `CheckViolationError`.

Cabe no `VARCHAR(30)` que a 0106 já alargou (20 caracteres) — sem alteração de
coluna aqui. Nenhuma tabela nova: RLS e grants não mudam.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0133"
down_revision: str | Sequence[str] | None = "0132"
branch_labels = None
depends_on = None
S = "pagamentos"

# Lista vigente desde a 0121 (ACAO_ANTERIOR + ACOES_NOVAS de lá).
ACAO_ANTERIOR = (
    "CRIADO", "ENVIADO", "APROVADO", "VALIDADO", "ENCAMINHADO", "DEVOLVIDO",
    "REJEITADO", "AUTORIZADO", "LIBERADO", "LIBERACAO_REVOGADA", "PAGAMENTO",
    "ESTORNO", "CANCELADO", "LIQUIDADO", "SUSPENSO", "REATIVADO", "CONCILIADO",
    "AUTORIZADO_GESTOR", "REJEITADO_GESTOR", "AJUSTE_SOLICITADO",
    "AJUSTE_RESPONDIDO", "INDEFERIDO",
    "ENVIADO_TESOURARIA", "REVOGADO", "PAGO", "PROCESSANDO", "ESTORNADO",
    "REENVIADO", "APROVACOES_INVALIDADAS", "MARCO_REGRAVADO", "FILA_REAVALIADA",
    "EXCECAO_AUTORIZADA",
    "LOTE_CRIADO", "LOTE_PROGRAMADO", "LOTE_ENVIADO", "PAGAMENTO_CONFIRMADO",
    "PAGAMENTO_FALHOU", "LOTE_CANCELADO", "RETENCAO_RECOLHIDA",
)
ACOES_NOVAS = ("CONCILIACAO_DESFEITA",)


def _in(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


def upgrade() -> None:
    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")
    op.create_check_constraint(
        "ck_debhist_acao", "debito_historico",
        f"acao IN ({_in(ACAO_ANTERIOR + ACOES_NOVAS)})", schema=S,
    )


def downgrade() -> None:
    # Mesmo padrão das anteriores (0111, 0121): as linhas com a ação nova saem,
    # senão o CHECK antigo não volta.
    op.execute(
        f"DELETE FROM {S}.debito_historico WHERE acao IN ({_in(ACOES_NOVAS)})"
    )
    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")
    op.create_check_constraint(
        "ck_debhist_acao", "debito_historico",
        f"acao IN ({_in(ACAO_ANTERIOR)})", schema=S,
    )
