"""F1/F2 do plano SUiTE — responsável-pessoa em protocolos.processo.

Revision ID: 0112
Revises: 0111
Create Date: 2026-09-16

`protocolos.processo` ganha `id_usuario_responsavel`, NULLABLE, apontando para
`utils.usuario`.

Plano: `docs/superpowers/plans/2026-09-16-aproveitamento-suite.md` (fatia F2).

Por que nullable — e por que isso é o ponto, não um detalhe
-----------------------------------------------------------
Nulo NÃO é "faltou preencher": é o estado **pendente de designação**, que o
SUiTE trata como de primeira classe e que hoje não existe no nosso modelo. Um
processo que chega numa unidade e ainda não tem dono é exatamente o caso que a
fila esconde — e é o que a fatia F1 (permanência) acabou de tornar mensurável.

Por isso não há backfill e não há default: todo processo existente nasce com
NULL, o que é a verdade sobre eles (ninguém foi designado).

Não confundir com `processo.id_usuario`
---------------------------------------
Aquela coluna já existe e é **quem abriu** o processo — carimbo histórico, não
muda. Esta é **quem responde por ele agora**, e muda a cada designação.

O índice
--------
`(tenant_id, id_usuario_responsavel)` serve o filtro `escopo=meus`, que é a
consulta que a tela faz a cada abertura da lista. Parcial em `excluido = false`
seguindo a convenção do projeto para índice de busca: processo excluído nunca
aparece em lista.

`ADD COLUMN` em tabela existente herda RLS/grants — não repete o boilerplate.
Conferido em 2026-09-16: `protocolos.processo` tem `relrowsecurity` e
`relforcerowsecurity`, e o grant de `aprimora_app` é de TABELA
(INSERT/SELECT/UPDATE/DELETE), não por coluna — então a coluna nova entra
coberta. A exceção do `GRANT` por coluna vale só para `aprimora_py.tenant`
(migration 0080), que não é o caso aqui.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0112"
down_revision: str | Sequence[str] | None = "0111"
branch_labels = None
depends_on = None

S = "protocolos"


def upgrade() -> None:
    op.add_column(
        "processo",
        sa.Column("id_usuario_responsavel", sa.Integer(), nullable=True),
        schema=S,
    )
    op.create_foreign_key(
        "fk_processo_usuario_responsavel",
        "processo",
        "usuario",
        ["id_usuario_responsavel"],
        ["id"],
        source_schema=S,
        referent_schema="utils",
        # Sem ON DELETE: usuário é soft-deleted (`excluido`), nunca apagado
        # fisicamente. Se um dia for, a FK barra e isso é o comportamento certo
        # — perder o responsável em silêncio seria pior.
    )
    op.create_index(
        "ix_processo_tenant_responsavel",
        "processo",
        ["tenant_id", "id_usuario_responsavel"],
        unique=False,
        schema=S,
        postgresql_where=sa.text("excluido = false"),
    )


def downgrade() -> None:
    op.drop_index("ix_processo_tenant_responsavel", table_name="processo", schema=S)
    op.drop_constraint(
        "fk_processo_usuario_responsavel", "processo", schema=S, type_="foreignkey"
    )
    op.drop_column("processo", "id_usuario_responsavel", schema=S)
