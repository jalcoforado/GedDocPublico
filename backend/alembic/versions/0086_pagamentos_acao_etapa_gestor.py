"""Pagamentos F1 (Tarefa 5) — amplia ck_debhist_acao para a etapa do gestor.

Revision ID: 0086
Revises: 0085
Create Date: 2026-08-07

A 0085 criou as três dimensões e o CHECK de domínio delas, mas não tocou em
`debito_historico.acao` — o CHECK ali (`ck_debhist_acao`, de 0069) continuava
com o vocabulário de quando só existia `encaminhar()`/`devolver()`/`rejeitar()`
genéricos. A Tarefa 5 grava ações mais específicas da decisão do gestor da
pasta (`AUTORIZADO_GESTOR`, `REJEITADO_GESTOR`) e do ciclo de ajuste que passa
a existir para as três etapas decisórias (`AJUSTE_SOLICITADO`,
`AJUSTE_RESPONDIDO`) — sem alargar o CHECK, o primeiro INSERT de cada uma
falha com `CheckViolationError` em runtime, não em teste de domínio.

Segue o padrão de 0049/0067/0069: `DROP CONSTRAINT` + `CREATE CONSTRAINT` com
a lista cheia (Postgres não tem `ALTER CHECK ADD VALUE`). O downgrade volta ao
vocabulário anterior E apaga as linhas com as ações novas — do contrário o
`CREATE CONSTRAINT` do downgrade quebraria com dado que já não cabe no CHECK
antigo, do mesmo jeito que 0069/0049 fazem para os casos deles.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0086"
down_revision: str | Sequence[str] | None = "0085"
branch_labels = None
depends_on = None
S = "pagamentos"

ACAO_ANTIGA = ("CRIADO", "ENVIADO", "APROVADO", "VALIDADO", "ENCAMINHADO", "DEVOLVIDO", "REJEITADO",
               "AUTORIZADO", "LIBERADO", "LIBERACAO_REVOGADA", "PAGAMENTO", "ESTORNO", "CANCELADO",
               "LIQUIDADO", "SUSPENSO", "REATIVADO", "CONCILIADO")
ACAO_NOVA = ACAO_ANTIGA + (
    "AUTORIZADO_GESTOR", "REJEITADO_GESTOR", "AJUSTE_SOLICITADO", "AJUSTE_RESPONDIDO", "INDEFERIDO",
)


def _in(vals) -> str:
    return ", ".join(f"'{v}'" for v in vals)


def upgrade() -> None:
    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")
    op.create_check_constraint("ck_debhist_acao", "debito_historico",
                               f"acao IN ({_in(ACAO_NOVA)})", schema=S)


def downgrade() -> None:
    op.execute(
        f"DELETE FROM {S}.debito_historico WHERE acao IN "
        f"('AUTORIZADO_GESTOR','REJEITADO_GESTOR','AJUSTE_SOLICITADO','AJUSTE_RESPONDIDO','INDEFERIDO')")
    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")
    op.create_check_constraint("ck_debhist_acao", "debito_historico",
                               f"acao IN ({_in(ACAO_ANTIGA)})", schema=S)
