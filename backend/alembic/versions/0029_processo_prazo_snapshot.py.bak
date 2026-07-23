"""Snapshot do prazo do serviço no processo (PR 5b).

Revision ID: 0029
Revises: 0028
Create Date: 2026-06-04

Adiciona `protocolos.processo.prazo_servico_dias_snapshot` (INT nullable)
para congelar `servico.prazo_estimado_dias` no momento da abertura.

Decisão D-SNAPSHOT (PR 5b): mudanças posteriores no prazo do serviço NÃO
afetam processos já abertos. O prazo é uma promessa publicada na Carta de
Serviços e precisa ser estável historicamente.

Backfill: processos com `id_servico IS NOT NULL` recebem o valor corrente
de `servico.prazo_estimado_dias`. Processos legados (sem `id_servico`) ou
com serviço sem prazo definido ficam com snapshot NULL.

A coluna herda RLS e GRANTs do schema `protocolos.processo` (Fase 0006);
sem novas policies, sem nova transação de permissão.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | Sequence[str] | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Adiciona coluna nullable — não bloqueia escritas concorrentes.
    op.add_column(
        "processo",
        sa.Column("prazo_servico_dias_snapshot", sa.Integer(), nullable=True),
        schema="protocolos",
    )

    # 2. Backfill: copia prazo do serviço p/ processos já abertos.
    # Defesa em profundidade: mesmo tenant_id em ambos os lados (FK já garante).
    op.execute(
        """
        UPDATE protocolos.processo p
        SET prazo_servico_dias_snapshot = s.prazo_estimado_dias
        FROM protocolos.servico s
        WHERE p.id_servico = s.id
          AND p.tenant_id = s.tenant_id
          AND p.prazo_servico_dias_snapshot IS NULL
          AND s.prazo_estimado_dias IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column(
        "processo", "prazo_servico_dias_snapshot", schema="protocolos"
    )
