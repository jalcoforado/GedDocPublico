"""Migration 0050 — Transporte Regulado: veiculo_documento + veiculo_avaliacao

Adiciona suporte a documentos (CRLV, CNH, inspeção, etc.) e avaliações regulatórias
de veículos permissionários. Metadados apenas (sem upload/anexos nesta fase).

Revision ID: 0050
Revises: 0049
Create Date: 2026-07-17

Schema: transporte_regulado (existente)
Tabelas novas:
  - veiculo_documento: metadados de documentos do veículo
  - veiculo_avaliacao: pareceres regulatórios
RLS: tenant-scoped via veiculo.tenant_id
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade():
    # Create veiculo_documento table
    op.create_table(
        "veiculo_documento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("id_veiculo", sa.Integer(), nullable=False),
        sa.Column(
            "tipo_documento",
            sa.String(30),
            nullable=False,
            comment="Enum: crlv, cnh_copia, inspecao, vistoria, seguro, autorizacao_especial, adaptacao, outro",
        ),
        sa.Column("numero_documento", sa.String(100), nullable=False),
        sa.Column("data_emissao", sa.Date(), nullable=True),
        sa.Column("data_validade", sa.Date(), nullable=True),
        sa.Column(
            "situacao",
            sa.String(20),
            nullable=False,
            server_default="pendente",
            comment="Enum: pendente, válido, vencido, rejeitado",
        ),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.ForeignKeyConstraint(["id_veiculo"], ["transporte_regulado.veiculo.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["aprimora_py.tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="transporte_regulado",
    )

    # Index: tenant + excluido (RLS helper)
    op.create_index(
        "ix_veiculo_documento_tenant_excluido",
        "veiculo_documento",
        ["tenant_id", "excluido"],
        schema="transporte_regulado",
    )

    # Index: situacao (filtro)
    op.create_index(
        "ix_veiculo_documento_situacao",
        "veiculo_documento",
        ["tenant_id", "situacao"],
        schema="transporte_regulado",
    )

    # Unique parcial: (tenant_id, id_veiculo, tipo_documento) where excluido=false
    op.create_index(
        "uq_veiculo_documento_tipo_por_veiculo",
        "veiculo_documento",
        ["tenant_id", "id_veiculo", "tipo_documento"],
        schema="transporte_regulado",
        unique=True,
        postgresql_where=sa.text("excluido = false"),
    )

    # Create veiculo_avaliacao table
    op.create_table(
        "veiculo_avaliacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("id_veiculo", sa.Integer(), nullable=False),
        sa.Column("id_usuario_avaliador", sa.Integer(), nullable=False),
        sa.Column(
            "resultado",
            sa.String(20),
            nullable=False,
            comment="Enum: pendente, aprovado, reprovado, condicional",
        ),
        sa.Column("parecer", sa.Text(), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("data_avaliacao", sa.DateTime(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.ForeignKeyConstraint(["id_veiculo"], ["transporte_regulado.veiculo.id"]),
        sa.ForeignKeyConstraint(["id_usuario_avaliador"], ["utils.usuario.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["aprimora_py.tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="transporte_regulado",
    )

    # Index: tenant + excluido
    op.create_index(
        "ix_veiculo_avaliacao_tenant_excluido",
        "veiculo_avaliacao",
        ["tenant_id", "excluido"],
        schema="transporte_regulado",
    )

    # Index: avaliador (filtro, relatórios)
    op.create_index(
        "ix_veiculo_avaliacao_avaliador",
        "veiculo_avaliacao",
        ["id_usuario_avaliador"],
        schema="transporte_regulado",
    )

    # RLS: Create role + policies (idem veiculo)
    op.execute("CREATE POLICY veiculo_documento_select ON transporte_regulado.veiculo_documento "
               "FOR SELECT USING (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY veiculo_documento_insert ON transporte_regulado.veiculo_documento "
               "FOR INSERT WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY veiculo_documento_update ON transporte_regulado.veiculo_documento "
               "FOR UPDATE USING (tenant_id = current_setting('app.current_tenant_id')::integer) "
               "WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY veiculo_documento_delete ON transporte_regulado.veiculo_documento "
               "FOR DELETE USING (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("ALTER TABLE transporte_regulado.veiculo_documento ENABLE ROW LEVEL SECURITY")

    op.execute("CREATE POLICY veiculo_avaliacao_select ON transporte_regulado.veiculo_avaliacao "
               "FOR SELECT USING (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY veiculo_avaliacao_insert ON transporte_regulado.veiculo_avaliacao "
               "FOR INSERT WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY veiculo_avaliacao_update ON transporte_regulado.veiculo_avaliacao "
               "FOR UPDATE USING (tenant_id = current_setting('app.current_tenant_id')::integer) "
               "WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("CREATE POLICY veiculo_avaliacao_delete ON transporte_regulado.veiculo_avaliacao "
               "FOR DELETE USING (tenant_id = current_setting('app.current_tenant_id')::integer)")
    op.execute("ALTER TABLE transporte_regulado.veiculo_avaliacao ENABLE ROW LEVEL SECURITY")

    # GRANTs (role aprimora_app)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON transporte_regulado.veiculo_documento TO aprimora_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON transporte_regulado.veiculo_avaliacao TO aprimora_app")


def downgrade():
    # Revoke GRANTs
    op.execute("REVOKE ALL ON transporte_regulado.veiculo_documento FROM aprimora_app")
    op.execute("REVOKE ALL ON transporte_regulado.veiculo_avaliacao FROM aprimora_app")

    # Drop tables (cascades policies + indexes)
    op.drop_table("veiculo_avaliacao", schema="transporte_regulado")
    op.drop_table("veiculo_documento", schema="transporte_regulado")
