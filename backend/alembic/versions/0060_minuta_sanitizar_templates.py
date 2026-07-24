"""Sanitizar conteúdo HTML de templates_documento existentes.

Revision ID: 0060
Revises: 0059
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

revision: str = "0060"
down_revision: str | Sequence[str] | None = "0059"


def upgrade() -> None:
    # Bleach as templates existentes
    # NOTA: Tabela protocolos.template_documento pode não existir em algumas envs
    # Noop se tabela não existir
    conn = op.get_bind()

    # Verificar se schema/tabela/coluna existem
    try:
        check = conn.execute(sa.text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'protocolos'
                  AND table_name = 'template_documento'
                  AND column_name = 'conteudo'
            )
        """))
        table_exists = check.scalar()
    except Exception:
        table_exists = False

    if not table_exists:
        # Tabela ou coluna não existe — noop
        return

    # Importar bleach
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

    # Fetch templates
    result = conn.execute(sa.text("""
        SELECT id, conteudo FROM protocolos.template_documento
        WHERE conteudo IS NOT NULL
    """))

    # Sanitize each
    for row in result:
        template_id, conteudo = row
        sanitized = bleach.clean(conteudo, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        if sanitized != conteudo:
            conn.execute(sa.text("""
                UPDATE protocolos.template_documento
                SET conteudo = :conteudo
                WHERE id = :id
            """), {"conteudo": sanitized, "id": template_id})


def downgrade() -> None:
    # Downgrade = noop (conteúdo sanitizado não é reversível sem backup original)
    # Manter templates sanitizados é mais seguro que "desfazer"
    pass
