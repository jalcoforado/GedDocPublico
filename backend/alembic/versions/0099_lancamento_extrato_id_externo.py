"""Pagamentos C2.2 — dedupe de lançamento de extrato por id_externo (FITID).

Revision ID: 0099
Revises: 0098
Create Date: 2026-08-24

O importador de extrato hoje só protege por `(conta, hash)` do arquivo
inteiro (RN da C1): reimportar o mesmo arquivo dá 409, mas dois arquivos
com período sobreposto (ex.: extrato mensal baixado de novo com mais dias)
duplicam todo lançamento repetido, porque nada identifica a linha
individualmente.

O OFX resolve isso com `FITID` — id único do banco POR CONTA (o mesmo
FITID em contas diferentes não é o mesmo lançamento). Esta migration:

- adiciona `lancamento_extrato.id_externo` (nullable — CSV segue sem id,
  dedupe por linha só se aplica a formato que tenha FITID);
- adiciona `lancamento_extrato.id_conta`, porque o dedupe por FITID
  precisa da chave `(tenant_id, id_conta, id_externo)`, e a linha hoje só
  sabe o `id_extrato` — a conta é indireta, via `extrato.id_conta`. Repetir
  a FK aqui evita um JOIN em todo INSERT de importação;
- faz o backfill de `id_conta` a partir de `extrato` antes de tornar a
  coluna NOT NULL — toda linha existente pertence a um extrato com conta
  definida, então o backfill é total e o `SET NOT NULL` não quebra;
- cria o índice único parcial `uq_lancamento_extrato_id_externo` em
  `(tenant_id, id_conta, id_externo) WHERE id_externo IS NOT NULL` — parcial
  porque CSV grava `id_externo IS NULL` em toda linha, e um índice único
  sem o `WHERE` trataria todo NULL como colisão (não é bem assim em
  Postgres — NULL nunca colide num UNIQUE — mas o `WHERE` deixa a intenção
  explícita e menor o índice).

`ADD COLUMN` herda RLS/grants da tabela (padrão do projeto) — não repetido
aqui.

## Downgrade

Dropa o índice único e as duas colunas, nessa ordem (o índice depende de
`id_conta`). Sem guarda de "não pode encolher dado real" porque não há
truncamento: as colunas somem inteiras, não um tamanho menor.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0099"
down_revision: str | Sequence[str] | None = "0098"
branch_labels = None
depends_on = None

S = "pagamentos"
T = "lancamento_extrato"


def upgrade() -> None:
    op.add_column(T, sa.Column("id_externo", sa.String(length=64), nullable=True), schema=S)
    op.add_column(T, sa.Column(
        "id_conta", sa.Integer(),
        sa.ForeignKey(f"{S}.conta_bancaria.id"), nullable=True), schema=S)

    op.execute(f"""
        UPDATE {S}.{T} le
        SET id_conta = e.id_conta
        FROM {S}.extrato e
        WHERE le.id_extrato = e.id AND le.tenant_id = e.tenant_id
    """)

    op.alter_column(T, "id_conta", existing_type=sa.Integer(), nullable=False, schema=S)

    op.create_index(
        "uq_lancamento_extrato_id_externo", T,
        ["tenant_id", "id_conta", "id_externo"],
        unique=True, schema=S,
        postgresql_where=sa.text("id_externo IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_lancamento_extrato_id_externo", table_name=T, schema=S)
    op.drop_column(T, "id_conta", schema=S)
    op.drop_column(T, "id_externo", schema=S)
