"""Pagamentos F2 (Task 4) — amplia ck_debhist_acao para reenvio + invalidação.

Revision ID: 0106
Revises: 0105
Create Date: 2026-08-25

`responder_ajuste` (F2) passa a gravar duas ações novas em
`pagamentos.debito_historico.acao`, e o CHECK ali (`ck_debhist_acao`, de
0069/0086/0087) não as contemplava:

- `REENVIADO` — a transição de tramitação do reenvio em si (via
  `_registrar_transicao`), substituindo o antigo `AJUSTE_RESPONDIDO` como
  ação de quem sai de `AJUSTE_*`.
- `APROVACOES_INVALIDADAS` — linha própria, gravada por INSERT direto (não é
  uma transição do grafo: a tramitação não muda nessa linha), quando uma
  alteração material invalida as aprovações de gestor e validador já dadas.

`APROVACOES_INVALIDADAS` tem 22 caracteres — maior que os `VARCHAR(20)` da
coluna `acao` (todo valor anterior cabia em 20). A mesma migration alarga a
coluna para `VARCHAR(30)`, com folga para ações futuras.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0106"
down_revision: str | Sequence[str] | None = "0105"
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
)
ACOES_NOVAS = ("REENVIADO", "APROVACOES_INVALIDADAS")


def _in(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


def upgrade() -> None:
    op.alter_column("debito_historico", "acao", schema=S,
                    type_=sa.String(30), existing_type=sa.String(20))
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
    op.alter_column("debito_historico", "acao", schema=S,
                    type_=sa.String(20), existing_type=sa.String(30))
