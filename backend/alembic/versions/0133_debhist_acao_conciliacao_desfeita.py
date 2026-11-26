"""Pagamentos — conciliação pode ser desfeita (soft-delete) e o histórico aceita o ato.

Revision ID: 0133
Revises: 0132
Create Date: 2026-10-11

Duas mudanças para `pagamentos_conciliacao.desfazer_conciliacao`:

1. `pagamentos.conciliacao` ganha `excluido` e os três campos de quem desfez
   (`desfeita_em`, `id_usuario_desfez`, `motivo_desfeita`). Conciliação desfeita
   não é apagada — é a regra do projeto, e o registro do casamento errado é
   justamente o que uma auditoria vai querer ver.

   As duas unicidades da tabela (RN-14: uma conciliação por lançamento, uma por
   movimentação) eram `UNIQUE` plenas, criadas na 0072. Com soft-delete elas
   passam a ser índices únicos PARCIAIS `WHERE excluido = false`: sem isso a
   linha desfeita impediria conciliar de novo o mesmo lançamento. Os nomes são
   mantidos.

2. `ck_debhist_acao` (de 0069/.../0111/0121) ganha `CONCILIACAO_DESFEITA`, que
   é a ação gravada em `debito_historico` quando o débito volta de CONCILIADA a
   PAGA. Cabe no `VARCHAR(30)` que a 0106 já alargou.

`ADD COLUMN` herda RLS e grants da tabela (`aprimora_app` tem
SELECT/INSERT/UPDATE/DELETE em `conciliacao` desde a 0072); nenhuma tabela nova.

Backfill: `excluido` nasce `false` para todas as linhas existentes, que são
conciliações vigentes.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
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

UNICIDADES = (
    ("uq_conciliacao_lancamento", "id_lancamento"),
    ("uq_conciliacao_movimentacao", "id_movimentacao"),
)


def _in(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


def upgrade() -> None:
    # ------------------------------------------------- conciliacao: soft-delete
    op.add_column(
        "conciliacao",
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        schema=S,
    )
    op.add_column("conciliacao", sa.Column("desfeita_em", sa.DateTime(), nullable=True), schema=S)
    op.add_column(
        "conciliacao",
        sa.Column("id_usuario_desfez", sa.Integer(),
                  sa.ForeignKey("utils.usuario.id"), nullable=True),
        schema=S,
    )
    op.add_column(
        "conciliacao", sa.Column("motivo_desfeita", sa.String(255), nullable=True), schema=S)

    for nome, coluna in UNICIDADES:
        op.drop_constraint(nome, "conciliacao", schema=S, type_="unique")
        op.create_index(
            nome, "conciliacao", ["tenant_id", coluna], unique=True, schema=S,
            postgresql_where=sa.text("excluido = false"),
        )

    # ---------------------------------------------------- ck_debhist_acao +1
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

    # As conciliações desfeitas saem: com as unicidades plenas de volta, uma
    # desfeita e a vigente do mesmo lançamento não cabem juntas — e sem a
    # coluna `excluido` a desfeita voltaria a valer como conciliação.
    op.execute(f"DELETE FROM {S}.conciliacao WHERE excluido = true")
    for nome, coluna in UNICIDADES:
        op.drop_index(nome, table_name="conciliacao", schema=S)
        op.create_unique_constraint(nome, "conciliacao", ["tenant_id", coluna], schema=S)

    op.drop_column("conciliacao", "motivo_desfeita", schema=S)
    op.drop_column("conciliacao", "id_usuario_desfez", schema=S)
    op.drop_column("conciliacao", "desfeita_em", schema=S)
    op.drop_column("conciliacao", "excluido", schema=S)
