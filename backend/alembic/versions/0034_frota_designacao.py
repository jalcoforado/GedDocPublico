"""Frota PR-4 — designação de veículo/motorista em solicitação aprovada.

Revision ID: 0034
Revises: 0033
Create Date: 2026-06-07

Opção A: adiciona 5 colunas nullable de designação diretamente em
`frota.solicitacao_veiculo` (relação 1:1, sem histórico de trocas nesta etapa).
Reaproveita RLS/GRANTs/soft-delete já existentes da tabela — sem nova tabela,
sem nova policy, sem nova permissão (continua `frota`).

Não altera status da solicitação nem situação do veículo.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | Sequence[str] | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "solicitacao_veiculo",
        sa.Column(
            "id_veiculo_designado",
            sa.Integer(),
            sa.ForeignKey("frota.veiculo.id"),
            nullable=True,
        ),
        schema="frota",
    )
    op.add_column(
        "solicitacao_veiculo",
        sa.Column(
            "id_motorista_designado",
            sa.Integer(),
            sa.ForeignKey("frota.motorista.id"),
            nullable=True,
        ),
        schema="frota",
    )
    op.add_column(
        "solicitacao_veiculo",
        sa.Column(
            "id_usuario_designador",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=True,
        ),
        schema="frota",
    )
    op.add_column(
        "solicitacao_veiculo",
        sa.Column("data_designacao", sa.DateTime(), nullable=True),
        schema="frota",
    )
    op.add_column(
        "solicitacao_veiculo",
        sa.Column("observacoes_designacao", sa.Text(), nullable=True),
        schema="frota",
    )


def downgrade() -> None:
    op.drop_column("solicitacao_veiculo", "observacoes_designacao", schema="frota")
    op.drop_column("solicitacao_veiculo", "data_designacao", schema="frota")
    op.drop_column("solicitacao_veiculo", "id_usuario_designador", schema="frota")
    op.drop_column("solicitacao_veiculo", "id_motorista_designado", schema="frota")
    op.drop_column("solicitacao_veiculo", "id_veiculo_designado", schema="frota")
