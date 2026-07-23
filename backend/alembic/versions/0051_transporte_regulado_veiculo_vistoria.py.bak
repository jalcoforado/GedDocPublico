"""Migration 0051 — Transporte Regulado: veiculo_vistoria

Adiciona suporte a vistorias regulatórias de veículos de permissionários.
Vistoria é inspeção realizada por auditor (servidor) com resultado e parecer.

Revision ID: 0051
Revises: 0050
Create Date: 2026-07-18

Schema: transporte_regulado (existente)
Tabela nova:
  - veiculo_vistoria: inspeção de veículos com resultado (aprovado/reprovado/condicional/pendente)
RLS: tenant-scoped via veiculo.tenant_id
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade():
    # Create veiculo_vistoria table
    op.create_table(
        "veiculo_vistoria",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("id_veiculo", sa.Integer(), nullable=False),
        sa.Column("id_auditor", sa.Integer(), nullable=False),
        sa.Column(
            "resultado",
            sa.String(20),
            nullable=False,
            comment="Enum: pendente, aprovado, reprovado, condicional",
        ),
        sa.Column("parecer", sa.Text(), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("data_vistoria", sa.DateTime(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.ForeignKeyConstraint(["id_veiculo"], ["transporte_regulado.veiculo.id"]),
        sa.ForeignKeyConstraint(["id_auditor"], ["utils.usuario.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["aprimora_py.tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="transporte_regulado",
    )

    # Index: tenant + excluido (RLS helper)
    op.create_index(
        "ix_veiculo_vistoria_tenant_excluido",
        "veiculo_vistoria",
        ["tenant_id", "excluido"],
        schema="transporte_regulado",
    )

    # Index: auditor (filtro, relatórios)
    op.create_index(
        "ix_veiculo_vistoria_auditor",
        "veiculo_vistoria",
        ["id_auditor"],
        schema="transporte_regulado",
    )

    # Index: resultado (filtro)
    op.create_index(
        "ix_veiculo_vistoria_resultado",
        "veiculo_vistoria",
        ["tenant_id", "resultado"],
        schema="transporte_regulado",
    )

    # Index: data_vistoria (ordenação)
    op.create_index(
        "ix_veiculo_vistoria_data",
        "veiculo_vistoria",
        ["tenant_id", "data_vistoria"],
        schema="transporte_regulado",
    )

    # RLS: Create policies
    op.execute("CREATE POLICY veiculo_vistoria_select ON transporte_regulado.veiculo_vistoria "
               "FOR SELECT USING (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY veiculo_vistoria_insert ON transporte_regulado.veiculo_vistoria "
               "FOR INSERT WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY veiculo_vistoria_update ON transporte_regulado.veiculo_vistoria "
               "FOR UPDATE USING (tenant_id = current_setting('app.current_tenant_id')::integer) "
               "WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY veiculo_vistoria_delete ON transporte_regulado.veiculo_vistoria "
               "FOR DELETE USING (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("ALTER TABLE transporte_regulado.veiculo_vistoria ENABLE ROW LEVEL SECURITY")

    # GRANTs (role aprimora_app)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON transporte_regulado.veiculo_vistoria TO aprimora_app")


def downgrade():
    # Revoke GRANTs
    op.execute("REVOKE ALL ON transporte_regulado.veiculo_vistoria FROM aprimora_app")

    # Drop table (cascades policies + indexes)
    op.drop_table("veiculo_vistoria", schema="transporte_regulado")
