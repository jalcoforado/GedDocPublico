"""Frota PR-5 — saída e retorno real do veículo.

Revision ID: 0035
Revises: 0034
Create Date: 2026-06-07

Opção A: adiciona 8 colunas operacionais nullable diretamente em
`frota.solicitacao_veiculo` (saída/retorno reais). O ciclo administrativo
(`status`) é estendido com os estados operacionais `em_uso` e `concluida` —
a coluna `status` é String(20) e já comporta os novos valores, então não há
DDL de status aqui (só novos valores aceitos pela aplicação).

Reaproveita RLS/GRANTs/soft-delete já existentes da tabela — sem nova tabela,
sem nova policy, sem nova permissão (continua `frota`).

Datas/usuários de saída/retorno são gravados server-side pelo serviço.
CHECK de coerência de quilometragem (`km_retorno >= km_saida`) como defesa em
profundidade — tolerante a NULLs (ambos nulos até o registro acontecer).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: str | Sequence[str] | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "solicitacao_veiculo",
        sa.Column("data_saida_real", sa.DateTime(), nullable=True),
        schema="frota",
    )
    op.add_column(
        "solicitacao_veiculo",
        sa.Column("data_retorno_real", sa.DateTime(), nullable=True),
        schema="frota",
    )
    op.add_column(
        "solicitacao_veiculo",
        sa.Column("km_saida", sa.Integer(), nullable=True),
        schema="frota",
    )
    op.add_column(
        "solicitacao_veiculo",
        sa.Column("km_retorno", sa.Integer(), nullable=True),
        schema="frota",
    )
    op.add_column(
        "solicitacao_veiculo",
        sa.Column("observacoes_saida", sa.Text(), nullable=True),
        schema="frota",
    )
    op.add_column(
        "solicitacao_veiculo",
        sa.Column("observacoes_retorno", sa.Text(), nullable=True),
        schema="frota",
    )
    op.add_column(
        "solicitacao_veiculo",
        sa.Column(
            "id_usuario_registro_saida",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=True,
        ),
        schema="frota",
    )
    op.add_column(
        "solicitacao_veiculo",
        sa.Column(
            "id_usuario_registro_retorno",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=True,
        ),
        schema="frota",
    )
    op.create_check_constraint(
        "ck_solicitacao_veiculo_km_retorno_gte_saida",
        "solicitacao_veiculo",
        "km_retorno IS NULL OR km_saida IS NULL OR km_retorno >= km_saida",
        schema="frota",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_solicitacao_veiculo_km_retorno_gte_saida",
        "solicitacao_veiculo",
        schema="frota",
        type_="check",
    )
    op.drop_column("solicitacao_veiculo", "id_usuario_registro_retorno", schema="frota")
    op.drop_column("solicitacao_veiculo", "id_usuario_registro_saida", schema="frota")
    op.drop_column("solicitacao_veiculo", "observacoes_retorno", schema="frota")
    op.drop_column("solicitacao_veiculo", "observacoes_saida", schema="frota")
    op.drop_column("solicitacao_veiculo", "km_retorno", schema="frota")
    op.drop_column("solicitacao_veiculo", "km_saida", schema="frota")
    op.drop_column("solicitacao_veiculo", "data_retorno_real", schema="frota")
    op.drop_column("solicitacao_veiculo", "data_saida_real", schema="frota")
