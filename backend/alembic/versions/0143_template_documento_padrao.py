"""Modelo de documento padrão da prefeitura (SI-53).

Revision ID: 0143
Revises: 0142
Create Date: 2026-11-23

`protocolos.template_documento.padrao` marca o modelo que já vem selecionado
ao redigir um documento no processo. No máximo UM por prefeitura entre os não
excluídos — o índice único parcial garante isso no banco; o service desmarca o
anterior antes de marcar o novo (`services/minutas.py::_desmarcar_padrao`).

Falso para tudo o que já existe: nenhuma prefeitura muda de comportamento até
alguém marcar um modelo (pela tela ou pelo `seed_itaitinga --parte documento`).
`ADD COLUMN` herda RLS e grants (CLAUDE.md §Migrations).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0143"
down_revision: str | Sequence[str] | None = "0142"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE protocolos.template_documento
            ADD COLUMN padrao boolean NOT NULL DEFAULT false
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_template_documento_padrao_por_tenant
            ON protocolos.template_documento (tenant_id)
            WHERE padrao AND NOT excluido
    """)


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS protocolos.uq_template_documento_padrao_por_tenant"
    )
    op.execute(
        "ALTER TABLE protocolos.template_documento DROP COLUMN IF EXISTS padrao"
    )
