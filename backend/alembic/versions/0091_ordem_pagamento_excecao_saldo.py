"""RN-15 vira coluna: `ordem_pagamento.excecao_saldo` + justificativa.

Revision ID: 0091
Revises: 0090
Create Date: 2026-08-13

A exceção de saldo insuficiente (RN-15) só existia como texto concatenado numa
justificativa de `debito_historico`, e o relatório de exceções a consultava com
`LIKE '%EXCEÇÃO DE SALDO (RN-15)%'`. Isso funciona e **quebra em silêncio** no
dia em que alguém reescrever a frase: o relatório passa a devolver zero linhas,
que é indistinguível de "não houve exceção" — o pior modo de falha num
relatório de compliance.

O backfill percorre o mesmo padrão de texto para não perder o histórico. Ele é
best-effort por natureza: alcança o que casa com a frase de hoje. Linha antiga
com frase diferente (não há nenhuma conhecida) continuaria só no texto — e é
por isso que o marcador segue sendo gravado pela aplicação, em vez de
substituído pela coluna.

`ADD COLUMN` herda RLS e grants da tabela; não repetir (ver CLAUDE.md).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0091"
down_revision: str | Sequence[str] | None = "0090"
branch_labels = None
depends_on = None

MARCADOR = "EXCEÇÃO DE SALDO (RN-15)"


def upgrade() -> None:
    op.add_column(
        "ordem_pagamento",
        sa.Column(
            "excecao_saldo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="pagamentos",
    )
    op.add_column(
        "ordem_pagamento",
        sa.Column("justificativa_excecao", sa.Text(), nullable=True),
        schema="pagamentos",
    )

    # Backfill. A ligação ordem→histórico é o número da OP, que a justificativa
    # carrega no prefixo ("OP 000123 — EXCEÇÃO DE SALDO (RN-15): <texto>").
    # `split_part` corta no marcador e devolve o texto da exceção; o `TRIM` tira
    # o ": " que sobra.
    op.execute(
        """
        UPDATE pagamentos.ordem_pagamento AS op
           SET excecao_saldo = true,
               justificativa_excecao = TRIM(BOTH ': ' FROM sub.texto)
          FROM (
              SELECT DISTINCT ON (h.justificativa)
                     h.tenant_id,
                     split_part(h.justificativa, 'OP ', 2) AS resto,
                     split_part(h.justificativa, 'EXCEÇÃO DE SALDO (RN-15)', 2) AS texto
                FROM pagamentos.debito_historico h
               WHERE h.justificativa LIKE '%EXCEÇÃO DE SALDO (RN-15)%'
          ) AS sub
         WHERE op.tenant_id = sub.tenant_id
           AND sub.resto LIKE op.numero || '%'
        """
    )

    # O default fica no lugar: linha nova sem exceção nasce `false`, e a
    # aplicação só precisa dizer algo quando HOUVE exceção.


def downgrade() -> None:
    op.drop_column("ordem_pagamento", "justificativa_excecao", schema="pagamentos")
    op.drop_column("ordem_pagamento", "excecao_saldo", schema="pagamentos")
