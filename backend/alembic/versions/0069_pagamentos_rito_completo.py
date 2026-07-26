"""Pagamentos v2.0 Onda A4 — rito completo (16 status) + perfis (seção 4/13).

Revision ID: 0069
Revises: 0068
Create Date: 2026-07-26

Alinha a máquina de estados do pedido à Especificação v2.0 seção 13 (16 status)
e a segregação de funções à seção 4:
- debito.status passa a admitir EM_VALIDACAO, DEVOLVIDO, VALIDADO,
  ENVIADO_SECRETARIO, AGUARDANDO_AUTORIZACAO, ENVIADO_TESOURARIA,
  EM_PROCESSAMENTO, CONCILIADO, ESTORNADO (mantém os já existentes).
- debito_historico.acao ganha VALIDADO, ENCAMINHADO, CONCILIADO.
- Novas permissões: pagamento_validar (validador setorial),
  pagamento_encaminhar (secretário/ordenador), pagamento_auditar (controle interno).

Backfill dos dados existentes para o novo rito:
- AGUARDANDO_APROVACAO → EM_VALIDACAO ; APROVADO → ENVIADO_SECRETARIO
- histórico: ação APROVADO → VALIDADO (mantém a segregação validador≠autorizador).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0069"
down_revision: str | Sequence[str] | None = "0068"
branch_labels = None
depends_on = None
S = "pagamentos"

STATUS_16 = ("RASCUNHO", "EM_VALIDACAO", "DEVOLVIDO", "VALIDADO", "ENVIADO_SECRETARIO",
             "AGUARDANDO_AUTORIZACAO", "AUTORIZADO", "ENVIADO_TESOURARIA", "EM_PROCESSAMENTO",
             "PAGO_PARCIAL", "PAGO", "CONCILIADO", "REJEITADO", "SUSPENSO", "CANCELADO", "ESTORNADO")
STATUS_9 = ("RASCUNHO", "AGUARDANDO_APROVACAO", "APROVADO", "AUTORIZADO",
            "PAGO_PARCIAL", "PAGO", "REJEITADO", "CANCELADO", "SUSPENSO")
ACAO_NOVA = ("CRIADO", "ENVIADO", "APROVADO", "VALIDADO", "ENCAMINHADO", "DEVOLVIDO", "REJEITADO",
             "AUTORIZADO", "LIBERADO", "LIBERACAO_REVOGADA", "PAGAMENTO", "ESTORNO", "CANCELADO",
             "LIQUIDADO", "SUSPENSO", "REATIVADO", "CONCILIADO")
ACAO_ANTIGA = ("CRIADO", "ENVIADO", "APROVADO", "DEVOLVIDO", "REJEITADO", "AUTORIZADO", "LIBERADO",
               "LIBERACAO_REVOGADA", "PAGAMENTO", "ESTORNO", "CANCELADO", "LIQUIDADO",
               "SUSPENSO", "REATIVADO")

TRANSACOES = (
    ("Validar Pagamento", "pagamento_validar"),
    ("Encaminhar Pagamento", "pagamento_encaminhar"),
    ("Auditar Pagamento", "pagamento_auditar"),
)

# downgrade: mapeia os status novos para o conjunto antigo mais próximo.
_BACK = {
    "EM_VALIDACAO": "AGUARDANDO_APROVACAO", "DEVOLVIDO": "RASCUNHO", "VALIDADO": "APROVADO",
    "ENVIADO_SECRETARIO": "APROVADO", "AGUARDANDO_AUTORIZACAO": "APROVADO",
    "ENVIADO_TESOURARIA": "AUTORIZADO", "EM_PROCESSAMENTO": "AUTORIZADO",
    "CONCILIADO": "PAGO", "ESTORNADO": "AUTORIZADO",
}


def _in(vals) -> str:
    return ", ".join(f"'{v}'" for v in vals)


def _recheck(table: str, col: str, name: str, vals) -> None:
    op.drop_constraint(name, table, schema=S, type_="check")
    op.create_check_constraint(name, table, f"{col} IN ({_in(vals)})", schema=S)


def upgrade() -> None:
    # 1) remove os CHECKs antigos para poder reescrever os status existentes.
    op.drop_constraint("ck_debito_status", "debito", schema=S, type_="check")
    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")

    # 2) backfill dos dados existentes para o novo rito.
    op.execute(f"UPDATE {S}.debito SET status='EM_VALIDACAO' WHERE status='AGUARDANDO_APROVACAO'")
    op.execute(f"UPDATE {S}.debito SET status='ENVIADO_SECRETARIO' WHERE status='APROVADO'")
    op.execute(f"UPDATE {S}.debito_historico SET acao='VALIDADO' WHERE acao='APROVADO'")

    # 3) cria os CHECKs já com os 16 status / novas ações.
    op.create_check_constraint("ck_debito_status", "debito", f"status IN ({_in(STATUS_16)})", schema=S)
    op.create_check_constraint("ck_debhist_acao", "debito_historico",
                               f"acao IN ({_in(ACAO_NOVA)})", schema=S)

    # 4) novas permissões (idempotente, padrão 0045/0048).
    for nome, codigo in TRANSACOES:
        op.execute(
            f"""INSERT INTO utils.transacao (transacao, codigo)
                SELECT '{nome}', '{codigo}'
                WHERE NOT EXISTS (SELECT 1 FROM utils.transacao WHERE codigo = '{codigo}')""")


def downgrade() -> None:
    for _, codigo in TRANSACOES:
        op.execute(f"DELETE FROM utils.grupo_transacao WHERE id_transacao IN "
                   f"(SELECT id FROM utils.transacao WHERE codigo='{codigo}')")
        op.execute(f"DELETE FROM utils.sistema_transacao WHERE id_transacao IN "
                   f"(SELECT id FROM utils.transacao WHERE codigo='{codigo}')")
        op.execute(f"DELETE FROM utils.transacao WHERE codigo='{codigo}'")

    op.execute(f"UPDATE {S}.debito_historico SET acao='APROVADO' WHERE acao='VALIDADO'")
    op.execute(f"DELETE FROM {S}.debito_historico WHERE acao IN ('ENCAMINHADO','CONCILIADO')")
    for novo, antigo in _BACK.items():
        op.execute(f"UPDATE {S}.debito SET status='{antigo}' WHERE status='{novo}'")

    _recheck("debito", "status", "ck_debito_status", STATUS_9)
    _recheck("debito_historico", "acao", "ck_debhist_acao", ACAO_ANTIGA)
