"""Abertura de protocolo por serviço — vínculo processo↔servico (PR 4b).

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-29

Adiciona `protocolos.processo.id_servico` (FK nullable → protocolos.servico) para
rastrear protocolos abertos a partir de um serviço da Carta de Serviços. Soft-link:
processos não originados de serviço (a maioria) ficam com `id_servico = NULL`.

`protocolos.processo` já tem RLS (0006) e GRANTs por schema — a coluna nova herda;
sem novas policies e sem nova transação de permissão (fluxo público/cidadão).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | Sequence[str] | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "processo",
        sa.Column(
            "id_servico",
            sa.Integer(),
            sa.ForeignKey("protocolos.servico.id"),
            nullable=True,
        ),
        schema="protocolos",
    )
    op.create_index(
        "ix_processo_tenant_servico",
        "processo",
        ["tenant_id", "id_servico"],
        schema="protocolos",
    )


def downgrade() -> None:
    op.drop_index("ix_processo_tenant_servico", table_name="processo", schema="protocolos")
    op.drop_column("processo", "id_servico", schema="protocolos")
