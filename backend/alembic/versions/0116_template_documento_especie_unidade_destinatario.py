"""Modelos: espécie documental + setor + destinatário/nº doc (F10, benchmark SUiTE).

Revision ID: 0116
Revises: 0115
Create Date: 2026-09-18

`protocolos.template_documento`:
- REMOVE `categoria` (texto livre) — substituída por `id_especie_documental`
  (FK pro catálogo real, `protocolos.especie_documental`, já existente e com
  CRUD próprio em `/protocolo/especies-documentais`). Só 3 templates de
  demonstração tinham `categoria` preenchida no tenant piloto (Despacho,
  Memorando, Ofício) — não há de-para automático confiável de texto livre
  para o catálogo estruturado, então a categorização se perde e precisa ser
  refeita manualmente. Aceito: é biblioteca administrada, não dado do
  cidadão.
- ADICIONA `id_unidade_trabalho` (nullable) — quem ADMINISTRA o template,
  mesmo padrão de `Marcador.id_unidade_trabalho` (F5, migration 0114):
  administração é setorial, visibilidade continua por tenant inteiro. Não é
  mecanismo de precedência/cascata — cascata "unidade sobrepõe tenant" foi
  cogitada e descartada por ser a opção mais cara (spec §8 Q1) para um
  ganho que o `id_unidade_trabalho` sozinho já entrega (saber de quem é).

`protocolos.minuta`:
- ADICIONA `destinatario` (nullable) — texto livre digitado ao redigir,
  alimenta o placeholder novo `{{destinatario.nome}}` (SUiTE `TO-CAPACITY`).
  Não tem de onde derivar automaticamente (processo não tem campo
  "destinatário do documento" — `manifestante` é quem REQUER, direção
  oposta), então é entrada manual, como título.

Ambas ADD/DROP COLUMN em tabela LEGADA (`protocolos.*`) — herda RLS/grants,
sem boilerplate.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0116"
down_revision: str | Sequence[str] | None = "0115"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "template_documento",
        sa.Column(
            "id_especie_documental", sa.Integer(),
            sa.ForeignKey("protocolos.especie_documental.id"), nullable=True,
        ),
        schema="protocolos",
    )
    op.add_column(
        "template_documento",
        sa.Column(
            "id_unidade_trabalho", sa.Integer(),
            sa.ForeignKey("utils.unidade_trabalho.id"), nullable=True,
        ),
        schema="protocolos",
    )
    op.drop_column("template_documento", "categoria", schema="protocolos")

    op.add_column(
        "minuta",
        sa.Column("destinatario", sa.String(300), nullable=True),
        schema="protocolos",
    )


def downgrade() -> None:
    op.drop_column("minuta", "destinatario", schema="protocolos")

    op.add_column(
        "template_documento",
        sa.Column("categoria", sa.String(80), nullable=True),
        schema="protocolos",
    )
    op.drop_column("template_documento", "id_unidade_trabalho", schema="protocolos")
    op.drop_column("template_documento", "id_especie_documental", schema="protocolos")
