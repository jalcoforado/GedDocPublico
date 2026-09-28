"""frota_telemetria_posicoes

Revision ID: abebb5bcbad2
Revises: 0122
Create Date: 2026-09-24 12:35:18.360909

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'abebb5bcbad2'
down_revision: str | Sequence[str] | None = '0122'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE frota.veiculo_posicao (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES aprimora_py.tenant(id),
            id_veiculo INTEGER NOT NULL REFERENCES frota.veiculo(id),
            timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            latitude NUMERIC(10, 8) NOT NULL,
            longitude NUMERIC(11, 8) NOT NULL,
            velocidade NUMERIC(5, 2),
            ignicao_ligada BOOLEAN,
            criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_veiculo_posicao_tenant_veiculo_time ON frota.veiculo_posicao (tenant_id, id_veiculo, timestamp DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE frota.veiculo_posicao;")
