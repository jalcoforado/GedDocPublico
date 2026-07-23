"""Checklist documental — vínculo anexo↔documento exigido (PR 4c).

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-29

Duas mudanças em um único upgrade transacional:

1. `protocolos.anexo.documento_exigido_key varchar(120) NULL` — vínculo simples
   entre um anexo enviado pelo cidadão e um item de `servico.documentos_exigidos`.
   Compatível com anexos antigos (ficam NULL).

2. Backfill estável de `protocolos.servico.documentos_exigidos`: para cada item
   sem `key`, gera `slug(nome)` (utilitário compartilhado com o runtime). Itens
   que já tenham `key` são preservados — estabilidade D-KEY. Idempotente.

`anexo` já tem RLS/GRANTs (migration 0006); a coluna nova herda. Sem nova policy
e sem nova transação de permissão.
"""
from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.utils.slug import slugify, slugify_unique

revision: str = "0026"
down_revision: str | Sequence[str] | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalizar_documentos(docs: list[dict] | None) -> list[dict] | None:
    """Adiciona `key` estável aos itens que não a tenham, garantindo unicidade
    dentro do serviço. Itens com `key` existente são preservados."""
    if not docs:
        return docs
    existentes: set[str] = {
        d["key"] for d in docs if isinstance(d, dict) and d.get("key")
    }
    saida: list[dict] = []
    mudou = False
    for item in docs:
        if not isinstance(item, dict):
            saida.append(item)
            continue
        if item.get("key"):
            saida.append(item)
            continue
        nome = item.get("nome") or "item"
        nova = slugify_unique(nome, existentes)
        existentes.add(nova)
        saida.append({**item, "key": nova})
        mudou = True
    return saida if mudou else docs


def upgrade() -> None:
    op.add_column(
        "anexo",
        sa.Column("documento_exigido_key", sa.String(length=120), nullable=True),
        schema="protocolos",
    )

    # Backfill idempotente: para serviços que tenham `documentos_exigidos` com
    # itens sem `key`, gera slug do nome (estável + único por serviço). Itens já
    # com key são preservados — D-KEY.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, documentos_exigidos FROM protocolos.servico "
            "WHERE documentos_exigidos IS NOT NULL"
        )
    ).fetchall()
    for row in rows:
        docs = row.documentos_exigidos
        if isinstance(docs, str):
            try:
                docs = json.loads(docs)
            except (TypeError, ValueError):
                continue
        novos = _normalizar_documentos(docs)
        if novos is not docs:
            bind.execute(
                sa.text(
                    "UPDATE protocolos.servico SET documentos_exigidos = :d "
                    "WHERE id = :i"
                ),
                {"d": json.dumps(novos), "i": row.id},
            )


def downgrade() -> None:
    # O backfill de `key` é mantido (dado adicional inofensivo). Só removemos a
    # coluna nova de `anexo`.
    op.drop_column("anexo", "documento_exigido_key", schema="protocolos")


__all__ = ["slugify"]  # silencia "imported but unused" se o linter reclamar
