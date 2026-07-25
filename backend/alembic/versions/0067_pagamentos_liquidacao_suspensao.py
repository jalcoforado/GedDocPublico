"""Pagamentos v2.0 Fase 2C — status SUSPENSO + ações de liquidação/suspensão.

Revision ID: 0067
Revises: 0066
Create Date: 2026-07-25

RF-VAL-02/03, RF-SOL-09, RF-TES-06, RN-01:
- debito.status ganha 'SUSPENSO' (tesouraria suspende um débito suspeito).
- debito_historico.acao ganha 'LIQUIDACAO_CONFIRMADA', 'SUSPENSO', 'REATIVADO'.
Apenas alarga os CHECKs; nada nas linhas existentes muda.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0067"
down_revision: str | Sequence[str] | None = "0066"
branch_labels = None
depends_on = None
S = "pagamentos"

_STATUS_NOVO = ("RASCUNHO', 'AGUARDANDO_APROVACAO', 'APROVADO', 'AUTORIZADO', "
                "'PAGO_PARCIAL', 'PAGO', 'REJEITADO', 'CANCELADO', 'SUSPENSO")
_STATUS_ANTIGO = ("RASCUNHO', 'AGUARDANDO_APROVACAO', 'APROVADO', 'AUTORIZADO', "
                  "'PAGO_PARCIAL', 'PAGO', 'REJEITADO', 'CANCELADO")
_ACAO_NOVA = ("CRIADO', 'ENVIADO', 'APROVADO', 'DEVOLVIDO', 'REJEITADO', "
              "'AUTORIZADO', 'LIBERADO', 'LIBERACAO_REVOGADA', 'PAGAMENTO', "
              "'ESTORNO', 'CANCELADO', 'LIQUIDADO', 'SUSPENSO', 'REATIVADO")
_ACAO_ANTIGA = ("CRIADO', 'ENVIADO', 'APROVADO', 'DEVOLVIDO', 'REJEITADO', "
                "'AUTORIZADO', 'LIBERADO', 'LIBERACAO_REVOGADA', 'PAGAMENTO', "
                "'ESTORNO', 'CANCELADO")


def upgrade() -> None:
    op.drop_constraint("ck_debito_status", "debito", schema=S, type_="check")
    op.create_check_constraint("ck_debito_status", "debito",
                               f"status IN ('{_STATUS_NOVO}')", schema=S)
    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")
    op.create_check_constraint("ck_debhist_acao", "debito_historico",
                               f"acao IN ('{_ACAO_NOVA}')", schema=S)


def downgrade() -> None:
    op.execute(f"UPDATE {S}.debito SET status='APROVADO' WHERE status='SUSPENSO'")
    op.execute(f"DELETE FROM {S}.debito_historico "
               f"WHERE acao IN ('LIQUIDADO','SUSPENSO','REATIVADO')")
    op.drop_constraint("ck_debito_status", "debito", schema=S, type_="check")
    op.create_check_constraint("ck_debito_status", "debito",
                               f"status IN ('{_STATUS_ANTIGO}')", schema=S)
    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")
    op.create_check_constraint("ck_debhist_acao", "debito_historico",
                               f"acao IN ('{_ACAO_ANTIGA}')", schema=S)
