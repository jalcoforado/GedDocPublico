"""Adiciona protocolos.anexo.tamanho_bytes (F6, benchmark SUiTE)

Revision ID: 0113
Revises: 0112
Create Date: 2026-09-17

Cota de anexação por processo (services/cota_anexacao.py) soma esta coluna
em vez de reler cada arquivo do disco a cada requisição. NULL para anexo
existente antes desta migration — `cota_anexacao.usado_bytes` trata como 0,
então nenhum processo já criado passa a exceder cota por causa do backfill
ausente.

`protocolos.anexo` já tem RLS (tabela pré-existente); ADD COLUMN herda
policies e grants — não repete o boilerplate.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0113"
down_revision: str | Sequence[str] | None = "0112"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "anexo",
        sa.Column("tamanho_bytes", sa.Integer(), nullable=True),
        schema="protocolos",
    )


def downgrade() -> None:
    op.drop_column("anexo", "tamanho_bytes", schema="protocolos")
