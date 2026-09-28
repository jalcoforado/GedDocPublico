"""Frota — `frota.veiculo_posicao` (telemetria: série de posições GPS).

Revision ID: 0123
Revises: 0122
Create Date: 2026-09-28

Primeira fatia da telemetria de frota (backlog §2.3): guarda as posições
recebidas por veículo, para ingestão em lote e consulta por período. Mesmo
padrão de RLS/GRANTs/policies das demais tabelas de `frota` (ver 0040).

- `data_hora` é o instante da leitura no rastreador (UTC, sem fuso, como o
  resto do schema); `criado_em` é o instante da gravação.
- Índice único `(tenant_id, id_veiculo, data_hora)`: o reenvio de um lote pelo
  rastreador (retry após timeout) não duplica pontos — o serviço grava com
  `ON CONFLICT DO NOTHING` sobre ele. É também o índice da consulta por período.
- CHECKs de faixa em latitude/longitude/velocidade: o schema Pydantic já barra,
  mas a série é alimentada por máquina e o banco é a última linha.
- Sem soft-delete: é série temporal de leitura de sensor, não cadastro. Nada
  apaga posição hoje; retenção é pendência registrada no backlog.
- Grant só para `aprimora_app`: nenhuma task Celery escreve aqui.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0123"
down_revision: str | Sequence[str] | None = "0122"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "veiculo_posicao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "id_veiculo",
            sa.Integer(),
            sa.ForeignKey("frota.veiculo.id"),
            nullable=False,
        ),
        sa.Column("data_hora", sa.DateTime(), nullable=False),
        sa.Column("latitude", sa.Numeric(10, 8), nullable=False),
        sa.Column("longitude", sa.Numeric(11, 8), nullable=False),
        sa.Column("velocidade", sa.Numeric(5, 2), nullable=True),
        sa.Column("ignicao_ligada", sa.Boolean(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90", name="ck_veiculo_posicao_latitude"
        ),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180", name="ck_veiculo_posicao_longitude"
        ),
        sa.CheckConstraint(
            "velocidade IS NULL OR velocidade >= 0",
            name="ck_veiculo_posicao_velocidade",
        ),
        schema="frota",
    )

    op.create_index(
        "ux_veiculo_posicao_tenant_veiculo_data_hora",
        "veiculo_posicao",
        ["tenant_id", "id_veiculo", "data_hora"],
        unique=True,
        schema="frota",
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON frota.veiculo_posicao TO aprimora_app"
    )
    op.execute("GRANT USAGE, SELECT ON frota.veiculo_posicao_id_seq TO aprimora_app")

    op.execute("ALTER TABLE frota.veiculo_posicao ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE frota.veiculo_posicao FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON frota.veiculo_posicao
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON frota.veiculo_posicao
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_modify ON frota.veiculo_posicao")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON frota.veiculo_posicao")
    op.execute("ALTER TABLE frota.veiculo_posicao NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE frota.veiculo_posicao DISABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON frota.veiculo_posicao_id_seq FROM aprimora_app")
    op.execute("REVOKE ALL ON frota.veiculo_posicao FROM aprimora_app")
    op.drop_index(
        "ux_veiculo_posicao_tenant_veiculo_data_hora",
        table_name="veiculo_posicao",
        schema="frota",
    )
    op.drop_table("veiculo_posicao", schema="frota")
