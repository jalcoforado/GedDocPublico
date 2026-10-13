"""Pagamentos — índices trigram para a busca por texto das solicitações.

Revision ID: 0134
Revises: 0133
Create Date: 2026-10-13

`GET /pagamentos/debitos/pagina` busca com `ILIKE '%termo%'` em quatro colunas:
descrição, NF e NE do débito, e nome do fornecedor
(`services/pagamentos_debitos._filtro_debitos`). Padrão que começa com `%` não
aproveita índice B-tree: a busca era varredura completa das duas tabelas.

Um índice GIN com `gin_trgm_ops` por coluna atende `ILIKE '%termo%'` a partir
de três caracteres. São quatro índices e não um composto porque o filtro é um
`OR` entre as colunas: o planejador combina os quatro por bitmap, coisa que um
índice multicoluna não permite.

A extensão `pg_trgm` vem na imagem oficial do Postgres e é "trusted" desde a
versão 13, então `CREATE EXTENSION` não exige superusuário — basta `CREATE` no
banco. Fica no schema `public`, e a classe de operadores é referida com o
schema para a migration não depender do `search_path`.

Nenhuma tabela nova: índice herda RLS e grants da tabela. Sem backfill.

O `downgrade` remove os índices e DEIXA a extensão: ela é do banco, não desta
migration, e outro objeto pode ter passado a depender dela.
"""
from __future__ import annotations

from alembic import op

revision = "0134"
down_revision = "0133"
branch_labels = None
depends_on = None

# (nome do índice, tabela, coluna)
INDICES = (
    ("ix_debito_descricao_trgm", "pagamentos.debito", "descricao"),
    ("ix_debito_numero_nf_trgm", "pagamentos.debito", "numero_nf"),
    ("ix_debito_numero_ne_trgm", "pagamentos.debito", "numero_ne"),
    ("ix_fornecedor_nome_trgm", "pagamentos.fornecedor", "nome"),
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public")
    for nome, tabela, coluna in INDICES:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {nome} ON {tabela} "
            f"USING gin ({coluna} public.gin_trgm_ops)"
        )


def downgrade() -> None:
    for nome, _tabela, _coluna in reversed(INDICES):
        op.execute(f"DROP INDEX IF EXISTS pagamentos.{nome}")
