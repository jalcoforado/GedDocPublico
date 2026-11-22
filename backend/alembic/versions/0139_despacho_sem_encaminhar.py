"""Despacho sem encaminhar (SI-62): finalidade da minuta e PDF do despacho.

Revision ID: 0139
Revises: 0138
Create Date: 2026-11-22

O despacho avulso nasce como rascunho no editor de minutas e, ao ser
concluído e assinado, vira PDF anexado ao processo mais uma movimentação
DESPACHO. Duas colunas novas:

- `protocolos.minuta.finalidade` ('documento' | 'despacho'), padrão
  'documento' para tudo o que já existe. Rascunho de despacho só o autor vê,
  e não se finaliza pelo caminho comum: só por "concluir despacho".
- `protocolos.despacho.id_anexo`: o PDF assinado do despacho, para a linha do
  tempo apontar para o documento. Nulo nos despachos de encaminhar, recusar,
  cancelar e arquivar, que continuam sendo só texto.

`ADD COLUMN` herda RLS e grants das tabelas (CLAUDE.md §Migrations). As duas
são tabelas legadas: o `ALTER` roda com o papel dono, como na 0135.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0139"
down_revision: str | Sequence[str] | None = "0138"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE protocolos.minuta
            ADD COLUMN finalidade varchar(20) NOT NULL DEFAULT 'documento'
    """)
    op.execute("""
        ALTER TABLE protocolos.minuta
            ADD CONSTRAINT ck_minuta_finalidade_valida
            CHECK (finalidade IN ('documento', 'despacho'))
    """)
    op.execute("""
        ALTER TABLE protocolos.despacho
            ADD COLUMN id_anexo integer NULL
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE protocolos.despacho DROP COLUMN IF EXISTS id_anexo")
    op.execute(
        "ALTER TABLE protocolos.minuta DROP CONSTRAINT IF EXISTS ck_minuta_finalidade_valida"
    )
    op.execute("ALTER TABLE protocolos.minuta DROP COLUMN IF EXISTS finalidade")
