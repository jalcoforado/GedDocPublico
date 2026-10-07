"""transporte_regulado.ponto — latitude/longitude para o mapa dos pontos

Revision ID: 0127
Revises: 0126
Create Date: 2026-10-07 14:00:00.000000

O ponto tinha só endereço em texto, então não havia como desenhá-lo num mapa.
As duas colunas são opcionais (ponto antigo segue válido sem elas) e usam a
mesma precisão de ``frota.veiculo_posicao`` (0123). O CHECK de par garante que
não exista ponto com só uma das coordenadas — meio ponto não se desenha.

Sem boilerplate de RLS/GRANT: ``ADD COLUMN`` herda as policies e os grants de
tabela de ``transporte_regulado.ponto``.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0127"
down_revision: str | Sequence[str] | None = "0126"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE transporte_regulado.ponto
            ADD COLUMN latitude NUMERIC(10, 8) NULL,
            ADD COLUMN longitude NUMERIC(11, 8) NULL,
            ADD CONSTRAINT ck_ponto_latitude
                CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
            ADD CONSTRAINT ck_ponto_longitude
                CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
            ADD CONSTRAINT ck_ponto_coordenadas_em_par
                CHECK ((latitude IS NULL) = (longitude IS NULL))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE transporte_regulado.ponto
            DROP CONSTRAINT ck_ponto_coordenadas_em_par,
            DROP CONSTRAINT ck_ponto_longitude,
            DROP CONSTRAINT ck_ponto_latitude,
            DROP COLUMN longitude,
            DROP COLUMN latitude
        """
    )
