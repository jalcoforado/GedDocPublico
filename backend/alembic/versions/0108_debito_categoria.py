"""Pagamentos F3 (Task 2) — categoria em pagamentos.debito.

Revision ID: 0108
Revises: 0107
Create Date: 2026-08-25

`pagamentos.debito` ganha `categoria` (mesmo domínio de `contrato.categoria`:
BENS/LOCACOES/SERVICOS/OBRAS), NULLABLE. É a categoria informada na
solicitação para o débito SEM contrato — spec §4.4: "Débito sem contrato
carrega a categoria em posicao_cronologica.categoria, informada na
solicitação". A persistência aqui é o que sobrevive entre a solicitação e a
liquidação, quando `services/pagamentos_cronologia.py::registrar_na_fila`
grava a linha definitiva em `posicao_cronologica`.

Nullable porque débito COM contrato usa a categoria do contrato
(`categoria_do_debito`) e nunca preenche esta coluna — e porque não há
backfill possível para os débitos legados sem contrato.

`ADD COLUMN` em tabela existente herda RLS/grants da tabela — não repete o
boilerplate (a tabela `debito` já tem RLS+policies+grants desde a migration
de origem do módulo)."""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0108"
down_revision: str | Sequence[str] | None = "0107"
branch_labels = None
depends_on = None

S = "pagamentos"

CATEGORIAS = ("BENS", "LOCACOES", "SERVICOS", "OBRAS")


def upgrade() -> None:
    op.add_column(
        "debito", sa.Column("categoria", sa.String(20), nullable=True), schema=S,
    )
    op.create_check_constraint(
        "ck_debito_categoria", "debito",
        "categoria IS NULL OR categoria IN ('" + "','".join(CATEGORIAS) + "')",
        schema=S,
    )


def downgrade() -> None:
    op.drop_constraint("ck_debito_categoria", "debito", schema=S, type_="check")
    op.drop_column("debito", "categoria", schema=S)
