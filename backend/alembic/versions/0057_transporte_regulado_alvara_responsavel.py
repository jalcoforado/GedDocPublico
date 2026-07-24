"""Migration 0057 — Transporte Regulado: Responsáveis de Alvarás

Adiciona suporte a vincular usuários do sistema como responsáveis por alvarás
(gerente, operador, autorizado, etc). Um usuário pode ser responsável por
múltiplos alvarás, e um alvará pode ter múltiplos responsáveis.

Revision ID: 0057
Revises: 0056
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade():
    # Create alvara_responsavel table
    op.create_table(
        "alvara_responsavel",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("id_alvara", sa.Integer(), nullable=False),
        sa.Column("id_usuario", sa.Integer(), nullable=False),
        sa.Column("cargo_funcao", sa.String(100), nullable=True, comment="Cargo ou função (gerente, operador, etc)"),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.ForeignKeyConstraint(["id_alvara"], ["transporte_regulado.alvara.id"]),
        sa.ForeignKeyConstraint(["id_usuario"], ["utils.usuario.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["aprimora_py.tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="transporte_regulado",
    )

    # Index: tenant + excluido (RLS helper)
    op.create_index(
        "ix_alvara_responsavel_tenant_excluido",
        "alvara_responsavel",
        ["tenant_id", "excluido"],
        schema="transporte_regulado",
    )

    # Index: por alvará
    op.create_index(
        "ix_alvara_responsavel_alvara",
        "alvara_responsavel",
        ["id_alvara"],
        schema="transporte_regulado",
    )

    # Unique: (tenant, alvara, usuario) — um usuário responsável por alvará apenas uma vez
    op.create_index(
        "uq_alvara_responsavel_unico_por_alvara",
        "alvara_responsavel",
        ["tenant_id", "id_alvara", "id_usuario"],
        schema="transporte_regulado",
        unique=True,
        postgresql_where=sa.text("excluido = false"),
    )

    # RLS: Create policies
    op.execute("CREATE POLICY alvara_responsavel_select ON transporte_regulado.alvara_responsavel "
               "FOR SELECT USING (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY alvara_responsavel_insert ON transporte_regulado.alvara_responsavel "
               "FOR INSERT WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY alvara_responsavel_update ON transporte_regulado.alvara_responsavel "
               "FOR UPDATE USING (tenant_id = current_setting('app.current_tenant_id')::integer) "
               "WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY alvara_responsavel_delete ON transporte_regulado.alvara_responsavel "
               "FOR DELETE USING (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("ALTER TABLE transporte_regulado.alvara_responsavel ENABLE ROW LEVEL SECURITY")


def downgrade():
    # Drop table (cascades policies + indexes)
    op.drop_table("alvara_responsavel", schema="transporte_regulado")
