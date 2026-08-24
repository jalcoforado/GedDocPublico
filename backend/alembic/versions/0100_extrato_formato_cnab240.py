"""Pagamentos C2.2 — formato CNAB240 no extrato (troca o placeholder CNAB).

Revision ID: 0100
Revises: 0099
Create Date: 2026-08-24

A 0072 criou `ck_extrato_formato` com `'CNAB'` como placeholder — nenhum
parser existia ainda para esse formato. A Task 2 da C2.2 implementa
`parse_cnab240` para o layout FEBRABAN de extrato e o `ImportarExtratoIn`
passa a validar o literal `"CNAB240"`. Sem esta migration o INSERT em
`pagamentos.extrato` com `formato='CNAB240'` estoura
`CheckViolationError` mesmo com o schema Pydantic e o dispatch do service já
aceitando o valor — o check da 0072 é a última barreira e ficaria
desalinhada.

Troca `'CNAB'` por `'CNAB240'` na lista permitida; não há dado histórico
para migrar porque nenhum import CNAB existiu (o formato nunca teve parser).

## Downgrade

Restaura a lista original `('OFX','CSV','XLSX','CNAB')`. Sem guarda de dado
existente: se alguma linha tiver `formato='CNAB240'` no momento do downgrade
(fluxo real desta fatia em diante), o `ALTER` falha por violar o check —
comportamento correto, não silencioso.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0100"
down_revision: str | Sequence[str] | None = "0099"
branch_labels = None
depends_on = None

S = "pagamentos"
T = "extrato"
C = "ck_extrato_formato"


def upgrade() -> None:
    op.drop_constraint(C, T, schema=S, type_="check")
    op.create_check_constraint(
        C, T, "formato IN ('OFX','CSV','XLSX','CNAB240')", schema=S)


def downgrade() -> None:
    op.drop_constraint(C, T, schema=S, type_="check")
    op.create_check_constraint(
        C, T, "formato IN ('OFX','CSV','XLSX','CNAB')", schema=S)
