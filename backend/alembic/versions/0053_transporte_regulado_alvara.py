"""Migration 0053 — Transporte Regulado: Alvarás/Autorizações

Tabela alvara para rastrear autorizações de operação de permissionários e empresas.

Campos:
  - id: PK
  - tenant_id: FK para tenant (RLS)
  - id_empresa: FK opcional para empresa
  - id_permissionario: FK opcional para permissionário
  - numero_alvara: identificador único por tenant
  - data_inicio: quando o alvará começa a valer
  - data_validade: quando expira (opcional, para suportar renovação)
  - tipo_servico: tipo de serviço autorizado
  - observacoes: campo livre
  - criado_em, atualizado_em: audit
  - excluido: soft-delete

Restrições:
  - At least one of id_empresa or id_permissionario must be non-null
  - numero_alvara unique per tenant (excluidos=false)
  - data_inicio <= data_validade (quando ambas informadas)

Revision ID: 0053
Revises: 0052
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade():
    # Create alvara table in transporte_regulado schema
    op.create_table(
        "alvara",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("id_empresa", sa.Integer(), nullable=True),
        sa.Column("id_permissionario", sa.Integer(), nullable=True),
        sa.Column("numero_alvara", sa.String(40), nullable=False),
        sa.Column("data_inicio", sa.Date(), nullable=True),
        sa.Column("data_validade", sa.Date(), nullable=True),
        sa.Column("tipo_servico", sa.String(30), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["aprimora_py.tenant.id"]),
        sa.ForeignKeyConstraint(["id_empresa"], ["transporte_regulado.empresa.id"]),
        sa.ForeignKeyConstraint(["id_permissionario"], ["transporte_regulado.permissionario.id"]),
        schema="transporte_regulado",
    )

    # Indices for common queries
    # RLS: tenant_id + excluido
    op.create_index(
        "ix_alvara_tenant_excluido",
        "alvara",
        ["tenant_id", "excluido"],
        schema="transporte_regulado",
    )

    # numero_alvara unique per tenant (non-deleted)
    op.create_index(
        "ix_alvara_numero_unico",
        "alvara",
        ["tenant_id", "numero_alvara"],
        schema="transporte_regulado",
        unique=True,
        postgresql_where=sa.text("excluido = false"),
    )

    # FK lookups
    op.create_index(
        "ix_alvara_empresa",
        "alvara",
        ["id_empresa"],
        schema="transporte_regulado",
    )
    op.create_index(
        "ix_alvara_permissionario",
        "alvara",
        ["id_permissionario"],
        schema="transporte_regulado",
    )

    # data_validade for querying expired
    op.create_index(
        "ix_alvara_data_validade",
        "alvara",
        ["tenant_id", "data_validade"],
        schema="transporte_regulado",
    )

    # RLS policy: tenant isolation on alvara
    op.execute("""
        CREATE POLICY alvara_tenant_isolation ON transporte_regulado.alvara
        USING (tenant_id = current_setting('app.current_tenant_id')::int)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::int);
    """)

    op.execute("""
        ALTER TABLE transporte_regulado.alvara ENABLE ROW LEVEL SECURITY;
    """)


def downgrade():
    op.execute("""
        ALTER TABLE transporte_regulado.alvara DISABLE ROW LEVEL SECURITY;
    """)

    op.execute("""
        DROP POLICY IF EXISTS alvara_tenant_isolation ON transporte_regulado.alvara;
    """)

    op.drop_index(
        "ix_alvara_data_validade",
        schema="transporte_regulado",
    )
    op.drop_index(
        "ix_alvara_permissionario",
        schema="transporte_regulado",
    )
    op.drop_index(
        "ix_alvara_empresa",
        schema="transporte_regulado",
    )
    op.drop_index(
        "ix_alvara_numero_unico",
        schema="transporte_regulado",
    )
    op.drop_index(
        "ix_alvara_tenant_excluido",
        schema="transporte_regulado",
    )
    op.drop_table("alvara", schema="transporte_regulado")
