"""Migration 0056 — Transporte Regulado: Documentos de Alvarás

Adiciona suporte a anexação de documentos em alvarás (contrato, comprovante de
endereço, procuração, etc.). Metadados apenas (sem upload nesta fase).

Revision ID: 0056
Revises: 0055
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade():
    # Create alvara_documento table
    op.create_table(
        "alvara_documento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("id_alvara", sa.Integer(), nullable=False),
        sa.Column(
            "tipo_documento",
            sa.String(30),
            nullable=False,
            comment="Enum: contrato, comprovante_endereco, procuracao, alvara_anterior, outro",
        ),
        sa.Column("arquivo", sa.String(255), nullable=False, comment="Filename or path"),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.ForeignKeyConstraint(["id_alvara"], ["transporte_regulado.alvara.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["aprimora_py.tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="transporte_regulado",
    )

    # Index: tenant + excluido (RLS helper)
    op.create_index(
        "ix_alvara_documento_tenant_excluido",
        "alvara_documento",
        ["tenant_id", "excluido"],
        schema="transporte_regulado",
    )

    # Index: por alvará
    op.create_index(
        "ix_alvara_documento_alvara",
        "alvara_documento",
        ["id_alvara"],
        schema="transporte_regulado",
    )

    # RLS: Create policies
    op.execute("CREATE POLICY alvara_documento_select ON transporte_regulado.alvara_documento "
               "FOR SELECT USING (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY alvara_documento_insert ON transporte_regulado.alvara_documento "
               "FOR INSERT WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY alvara_documento_update ON transporte_regulado.alvara_documento "
               "FOR UPDATE USING (tenant_id = current_setting('app.current_tenant_id')::integer) "
               "WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY alvara_documento_delete ON transporte_regulado.alvara_documento "
               "FOR DELETE USING (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("ALTER TABLE transporte_regulado.alvara_documento ENABLE ROW LEVEL SECURITY")


def downgrade():
    # Drop table (cascades policies + indexes)
    op.drop_table("alvara_documento", schema="transporte_regulado")
