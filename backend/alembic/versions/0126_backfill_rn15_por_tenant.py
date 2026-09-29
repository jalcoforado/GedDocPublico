"""Refaz o backfill da RN-15 (0091) por tenant e com número de OP exato.

Revision ID: 0126
Revises: 0125

A 0091 marcou `ordem_pagamento.excecao_saldo` a partir do texto do histórico
("OP OP-2026-0001 — EXCEÇÃO DE SALDO (RN-15): <texto>"), mas:

- **`DISTINCT ON (h.justificativa)` sem o tenant.** Cada tenant numera as OPs a
  partir de 0001; dois tenants com a mesma justificativa geram texto IDÊNTICO no
  histórico, o `DISTINCT ON` fica com uma linha só (de um tenant qualquer) e a
  OP do outro tenant não recebe a marca — some do relatório de exceções, em
  silêncio. Foi o que o teste `test_o_backfill_alcanca_linha_antiga` pegava
  quando outro tenant de teste tinha histórico no mesmo banco.
- **`LIKE op.numero || '%'`.** Casa prefixo: a partir da OP 10000 do ano,
  `OP-2026-1000` casaria com o histórico da `OP-2026-10000`.

Migration aplicada não se edita; esta corrige para trás. Só MARCA OP que ainda
está sem a marca (`excecao_saldo = false`) — nunca apaga nem sobrescreve. Em
banco onde a 0091 rodou certo (um único tenant com histórico, como a VPS de
homologação) ela não altera linha nenhuma; OP criada depois da 0091 já nasce
com coluna e texto coerentes (`pagamentos_autorizacao.autorizar_lote`).

Downgrade é no-op: desmarcar apagaria marca legítima.
"""
from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "0126"
down_revision: str | Sequence[str] | None = "0125"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Reaplicado por tests/test_pagamentos_rn15_c13.py — mantenha o SQL aqui.
SQL_BACKFILL = r"""
UPDATE pagamentos.ordem_pagamento AS op
   SET excecao_saldo = true,
       justificativa_excecao = TRIM(BOTH ': ' FROM sub.texto)
  FROM (
      SELECT DISTINCT ON (h.tenant_id, h.justificativa)
             h.tenant_id,
             split_part(split_part(h.justificativa, 'OP ', 2), ' ', 1) AS numero,
             split_part(h.justificativa, 'EXCEÇÃO DE SALDO (RN-15)', 2) AS texto
        FROM pagamentos.debito_historico h
       WHERE h.justificativa LIKE '%EXCEÇÃO DE SALDO (RN-15)%'
       ORDER BY h.tenant_id, h.justificativa, h.id
  ) AS sub
 WHERE op.tenant_id = sub.tenant_id
   AND op.numero = sub.numero
   AND op.excecao_saldo = false
"""


def upgrade() -> None:
    op.execute(SQL_BACKFILL)


def downgrade() -> None:
    pass
