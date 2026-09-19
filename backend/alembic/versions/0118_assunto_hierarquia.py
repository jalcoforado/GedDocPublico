"""Assunto hierárquico — id_assunto_pai/nivel/codigo (E2, benchmark SUiTE).

Revision ID: 0118
Revises: 0117
Create Date: 2026-09-18

`protocolos.assunto` era string plana (`assunto: String(1000)`), sem jeito de
filtrar por ramo, agregar por nível ou representar a árvore de 3 níveis que o
SUiTE mostra (padrão CONARQ: "Aquisição - Equipamentos e material permanente
- Aeronaves"). Ganha:

- `id_assunto_pai` — auto-referente (nullable), a própria árvore.
- `nivel` — profundidade (raiz = 1), calculada no service a partir do pai
  (nunca digitada à mão) — evita a inconsistência de alguém setar nivel=1
  com um pai de nivel 2.
- `codigo` — texto livre opcional (numeração estilo CONARQ), sem catálogo
  nem formato imposto.

**Escopo deliberadamente menor que o plano original.** A resposta de Jorge à
Q2 do plano (`docs/superpowers/plans/2026-09-16-aproveitamento-suite.md` §6)
pedia "herança" — catálogo global por referência, não cópia no
provisionamento — o que implica uma tabela de catálogo separada (padrão
`aprimora_py.modulo`) e decisões que essa fatia não tem: quem administra o
global e qual é o conteúdo inicial (nenhuma lista CONARQ foi definida).
Decidido em 2026-09-18: implementar aqui só a hierarquia LOCAL (autoreferente,
por tenant) — resolve a dor real (filtrar/agregar por ramo) sem represar a
fatia esperando por um catálogo que ainda não existe. Por isso NÃO há coluna
`origem`: sem fonte global para contrastar, todo registro seria sempre
'local' — coluna que nunca varia é antecipação, não hierarquia. Ela entra
quando (e se) a fatia da tabela global for escopada.

Migração sem efeito: todo assunto existente vira raiz (`nivel=1`,
`id_assunto_pai=NULL`) — uma árvore de um nível é uma lista, comportamento
idêntico ao de hoje.

ADD COLUMN em tabela LEGADA (`protocolos.*`) — herda RLS/grants, sem
boilerplate. Índice novo porque listar "filhos diretos de um ramo" — o caso
de uso que esta fatia existe para viabilizar — filtra por
`(tenant_id, id_assunto_pai)` a cada chamada.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0118"
down_revision: str | Sequence[str] | None = "0117"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assunto",
        sa.Column(
            "id_assunto_pai", sa.Integer(),
            sa.ForeignKey("protocolos.assunto.id"), nullable=True,
        ),
        schema="protocolos",
    )
    op.add_column(
        "assunto",
        sa.Column("nivel", sa.Integer(), nullable=False, server_default="1"),
        schema="protocolos",
    )
    op.add_column(
        "assunto",
        sa.Column("codigo", sa.String(50), nullable=True),
        schema="protocolos",
    )
    op.create_index(
        "ix_assunto_pai",
        "assunto",
        ["tenant_id", "id_assunto_pai"],
        schema="protocolos",
    )


def downgrade() -> None:
    op.drop_index("ix_assunto_pai", table_name="assunto", schema="protocolos")
    op.drop_column("assunto", "codigo", schema="protocolos")
    op.drop_column("assunto", "nivel", schema="protocolos")
    op.drop_column("assunto", "id_assunto_pai", schema="protocolos")
