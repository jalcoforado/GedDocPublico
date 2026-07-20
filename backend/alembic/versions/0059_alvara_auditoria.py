"""Alvará — auditoria e histórico de mudanças (P4).

Revision ID: 0059
Revises: 0058
Create Date: 2026-07-19

P4 Dimensão 2: Trail completo de quem alterou o quê e quando em um alvará.
Snapshots append-only de estado (dados_antigos, dados_novos) para rastreamento
e auditoria regulatória.

Cria tabela de junção `transporte_regulado.alvara_auditoria` (append-only) com:
- Referência a alvara
- Ação (alvara.criada, alvara.renovada, alvara.documentos_atualizados, etc.)
- Snapshots JSONB (antes/depois)
- Ator (id_usuario)
- Índice em (tenant_id, id_alvara, criado_em DESC) para queries rápidas
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import BIGINT, JSONB

revision: str = "0059"
down_revision: str | Sequence[str] | None = "0058"


def upgrade() -> None:
    op.create_table(
        "alvara_auditoria",
        sa.Column("id", BIGINT(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("id_alvara", BIGINT(), nullable=False),
        sa.Column("acao", sa.Text(), nullable=False),
        sa.Column("dados_antigos", JSONB(), nullable=True),
        sa.Column("dados_novos", JSONB(), nullable=True),
        sa.Column("id_usuario", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("tenant_id IS NOT NULL", name="ck_alvara_auditoria_tenant_not_null"),
        sa.ForeignKeyConstraint(["id_alvara"], ["transporte_regulado.alvara.id"], name="fk_alvara_auditoria_alvara_id"),
        sa.ForeignKeyConstraint(["id_usuario"], ["utils.usuario.id"], name="fk_alvara_auditoria_usuario_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["aprimora_py.tenant.id"], name="fk_alvara_auditoria_tenant_id"),
        sa.PrimaryKeyConstraint("id", name="pk_alvara_auditoria"),
        schema="transporte_regulado",
    )

    op.create_index(
        "ix_alvara_auditoria_tenant_alvara_criado",
        "alvara_auditoria",
        ["tenant_id", "id_alvara", sa.desc("criado_em")],
        schema="transporte_regulado",
    )

    # RLS Policies (read-only para não vazar audit)
    op.execute(
        """
        ALTER TABLE transporte_regulado.alvara_auditoria ENABLE ROW LEVEL SECURITY;

        CREATE POLICY tenant_isolation_select ON transporte_regulado.alvara_auditoria
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int);
    """
    )

    # GRANTs (apenas SELECT para app, INSERT via trigger/service)
    op.execute("GRANT SELECT ON transporte_regulado.alvara_auditoria TO aprimora_app;")
    op.execute("GRANT USAGE ON SEQUENCE transporte_regulado.alvara_auditoria_id_seq TO aprimora_app;")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON transporte_regulado.alvara_auditoria;")
    op.drop_index(
        "ix_alvara_auditoria_tenant_alvara_criado",
        table_name="alvara_auditoria",
        schema="transporte_regulado",
    )
    op.drop_table("alvara_auditoria", schema="transporte_regulado")
