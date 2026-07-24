"""Sanitizar conteúdo HTML de templates_documento existentes.

Revision ID: 0062
Revises: 0061
Create Date: 2026-07-18

Aplica bleach aos templates criados antes de PR-E (hardening).
Modifica `protocolos.template_documento.conteudo` em-place via UPDATE
com função SQL `btrim` (preserva se já limpo).

Migration idempotente: rodar 2x retorna mesmo estado.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0062"
down_revision: str | Sequence[str] | None = "0061"


def upgrade() -> None:
    # Bleach as templates existentes
    # SQL puro: não há função PostgreSQL de bleach, então fazemos in-application
    # Fetch todos os templates, sanitizar em Python, atualizar
    conn = op.get_bind()

    # Guard: a tabela protocolos.template_documento pode não existir (ex.: build
    # limpo do schema legado, onde a minuta mora em outro schema/nome). Noop se
    # tabela/coluna ausente — mesmo padrão da 0060.
    try:
        check = conn.execute(sa.text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'protocolos'
                  AND table_name = 'template_documento'
                  AND column_name = 'conteudo'
            )
        """))
        col_exists = check.scalar()
    except Exception:
        col_exists = False

    if not col_exists:
        return

    # Apenas SELECT para listar — updates feitas abaixo
    result = conn.execute(sa.text("""
        SELECT id, conteudo FROM protocolos.template_documento
        WHERE conteudo IS NOT NULL
    """))

    # Importar bleach aqui para migration
    import bleach

    ALLOWED_TAGS = {
        "p", "br", "b", "i", "u", "strong", "em", "h1", "h2", "h3",
        "ul", "ol", "li", "blockquote", "a", "span", "div",
    }
    ALLOWED_ATTRS = {
        "a": ["href", "title"],
        "span": ["class"],
        "div": ["class"],
    }

    for row in result:
        template_id, conteudo = row
        sanitized = bleach.clean(conteudo, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        if sanitized != conteudo:
            conn.execute(sa.text("""
                UPDATE protocolos.template_documento
                SET conteudo = :conteudo
                WHERE id = :id
            """), {"conteudo": sanitized, "id": template_id})

    conn.commit()


def downgrade() -> None:
    # Downgrade = noop (conteúdo sanitizado não é reversível sem backup original)
    # Manter templates sanitizados é mais seguro que "desfazer"
    pass
