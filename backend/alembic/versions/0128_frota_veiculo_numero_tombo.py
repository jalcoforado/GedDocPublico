"""frota.veiculo.numero_tombo — número de tombo patrimonial do veículo

Revision ID: 0128
Revises: 0127
Create Date: 2026-10-07 20:00:00.000000

O tombo é a identidade do bem no patrimônio do município, e é por ele que o
veículo vai se ligar ao módulo de patrimônio quando este existir. Entra agora,
opcional, para a frota já nascer com a chave preenchida.

Único por tenant entre não excluídos — dois veículos com o mesmo tombo tornariam
a ligação futura ambígua. O índice é parcial: veículo sem tombo (o cadastro
todo, hoje) não disputa unicidade, e a exclusão devolve o número. O serviço
confere antes e responde 409; o índice é quem segura a corrida.

Sem boilerplate de RLS/GRANT: ``ADD COLUMN`` herda as policies e os grants de
tabela de ``frota.veiculo``.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0128"
down_revision: str | Sequence[str] | None = "0127"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE frota.veiculo ADD COLUMN numero_tombo VARCHAR(30) NULL")
    op.execute(
        """
        CREATE UNIQUE INDEX ux_veiculo_tenant_numero_tombo
            ON frota.veiculo (tenant_id, numero_tombo)
            WHERE numero_tombo IS NOT NULL AND excluido = false
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX frota.ux_veiculo_tenant_numero_tombo")
    op.execute("ALTER TABLE frota.veiculo DROP COLUMN numero_tombo")
