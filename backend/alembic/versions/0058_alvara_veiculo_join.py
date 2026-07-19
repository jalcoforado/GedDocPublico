"""Alvará — vínculo com múltiplos veículos (join table).

Revision ID: 0058
Revises: 0057
Create Date: 2026-07-18

P4 Dimensão 1: Um alvará pode estar vinculado a múltiplos veículos
(ex: táxi amarelo com 2 táxis, mototáxi com 3 motos).

Cria tabela de junção `transporte_regulado.alvara_veiculo` com:
- Referências a alvara + veiculo
- Tenant-scoped com RLS (padrão 0043)
- Índices em (tenant_id, id_alvara) e (tenant_id, id_veiculo)
- UNIQUE (tenant_id, id_alvara, id_veiculo) evita duplicatas
- Metadados: data_vinculo, criado_em, atualizado_em
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import BIGINT

revision: str = "0058"
down_revision: str | Sequence[str] | None = "0057"


def upgrade() -> None:
    op.create_table(
        "alvara_veiculo",
        sa.Column("id", BIGINT(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("id_alvara", BIGINT(), nullable=False),
        sa.Column("id_veiculo", BIGINT(), nullable=False),
        sa.Column("data_vinculo", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.CheckConstraint("tenant_id IS NOT NULL", name="ck_alvara_veiculo_tenant_not_null"),
        sa.ForeignKeyConstraint(["id_alvara"], ["alvara.id"], name="fk_alvara_veiculo_alvara_id"),
        sa.ForeignKeyConstraint(["id_veiculo"], ["veiculo.id"], name="fk_alvara_veiculo_veiculo_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["aprimora_py.tenant.id"], name="fk_alvara_veiculo_tenant_id"),
        sa.PrimaryKeyConstraint("id", name="pk_alvara_veiculo"),
        sa.UniqueConstraint("tenant_id", "id_alvara", "id_veiculo", name="uq_alvara_veiculo_no_dup"),
        schema="transporte_regulado",
    )

    op.create_index(
        "ix_alvara_veiculo_tenant_alvara",
        "alvara_veiculo",
        ["tenant_id", "id_alvara"],
        schema="transporte_regulado",
    )
    op.create_index(
        "ix_alvara_veiculo_tenant_veiculo",
        "alvara_veiculo",
        ["tenant_id", "id_veiculo"],
        schema="transporte_regulado",
    )

    # RLS Policies (padrão tenant_isolation de 0043)
    op.execute(
        """
        ALTER TABLE transporte_regulado.alvara_veiculo ENABLE ROW LEVEL SECURITY;

        CREATE POLICY tenant_isolation_select ON transporte_regulado.alvara_veiculo
            FOR SELECT
            USING (tenant_id = CAST(current_setting('app.current_tenant_id') AS INT));

        CREATE POLICY tenant_isolation_modify ON transporte_regulado.alvara_veiculo
            FOR ALL
            USING (tenant_id = CAST(current_setting('app.current_tenant_id') AS INT))
            WITH CHECK (tenant_id = CAST(current_setting('app.current_tenant_id') AS INT));
    """
    )

    # GRANTs
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON transporte_regulado.alvara_veiculo TO aprimora_app;")
    op.execute("GRANT USAGE ON SEQUENCE transporte_regulado.alvara_veiculo_id_seq TO aprimora_app;")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_modify ON transporte_regulado.alvara_veiculo;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON transporte_regulado.alvara_veiculo;")
    op.drop_index(
        "ix_alvara_veiculo_tenant_veiculo",
        table_name="alvara_veiculo",
        schema="transporte_regulado",
    )
    op.drop_index(
        "ix_alvara_veiculo_tenant_alvara",
        table_name="alvara_veiculo",
        schema="transporte_regulado",
    )
    op.drop_table("alvara_veiculo", schema="transporte_regulado")
