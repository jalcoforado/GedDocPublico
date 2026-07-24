"""Transporte Regulado PR-2 — `empresa` (empresas reguladas).

Revision ID: 0042
Revises: 0041
Create Date: 2026-06-08

Cria `transporte_regulado.empresa` — cadastro tenant-scoped de empresas/operadoras
reguladas (táxi, mototáxi, transporte escolar etc.), no mesmo padrão de RLS/GRANTs/
policies de `transporte_regulado.permissionario` (0041). O schema e a transação
`transporte_regulado` já existem (0041); esta migration NÃO os recria nem os remove.

- `cnpj` único por tenant **entre empresas não excluídas** (índice parcial),
  validado também no serviço de domínio (409). Soft-delete via `excluido`.
- `situacao` default `pendente`; validada na aplicação (sem CHECK de enum).
- CHECK de coerência das datas da autorização (validade >= início), tolerante a NULL.
- `id_representante_permissionario` opcional → FK para `transporte_regulado.permissionario`;
  a coerência de tenant é garantida no serviço (mesmo tenant, não excluído).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042"
down_revision: str | Sequence[str] | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "empresa",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column("razao_social", sa.String(length=200), nullable=False),
        sa.Column("nome_fantasia", sa.String(length=200), nullable=True),
        sa.Column("cnpj", sa.String(length=14), nullable=False),
        sa.Column("inscricao_municipal", sa.String(length=30), nullable=True),
        sa.Column("inscricao_estadual", sa.String(length=30), nullable=True),
        sa.Column("telefone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("cep", sa.String(length=9), nullable=True),
        sa.Column("logradouro", sa.String(length=200), nullable=True),
        sa.Column("numero", sa.String(length=20), nullable=True),
        sa.Column("complemento", sa.String(length=100), nullable=True),
        sa.Column("bairro", sa.String(length=100), nullable=True),
        sa.Column("municipio", sa.String(length=100), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("tipo_servico", sa.String(length=30), nullable=False),
        sa.Column("numero_autorizacao", sa.String(length=40), nullable=True),
        sa.Column("data_inicio_autorizacao", sa.Date(), nullable=True),
        sa.Column("data_validade_autorizacao", sa.Date(), nullable=True),
        sa.Column(
            "id_representante_permissionario",
            sa.Integer(),
            sa.ForeignKey("transporte_regulado.permissionario.id"),
            nullable=True,
        ),
        sa.Column(
            "situacao",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pendente'"),
        ),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
        sa.CheckConstraint(
            "data_validade_autorizacao IS NULL OR data_inicio_autorizacao IS NULL "
            "OR data_validade_autorizacao >= data_inicio_autorizacao",
            name="ck_empresa_datas_autorizacao_coerentes",
        ),
        schema="transporte_regulado",
    )

    # CNPJ único por tenant SÓ entre não excluídas (permite re-cadastrar após soft-delete).
    op.create_index(
        "uq_empresa_tenant_cnpj",
        "empresa",
        ["tenant_id", "cnpj"],
        unique=True,
        schema="transporte_regulado",
        postgresql_where=sa.text("excluido = false"),
    )
    op.create_index(
        "ix_empresa_tenant_excluido",
        "empresa",
        ["tenant_id", "excluido"],
        schema="transporte_regulado",
    )
    op.create_index(
        "ix_empresa_tenant_situacao",
        "empresa",
        ["tenant_id", "situacao"],
        schema="transporte_regulado",
    )
    op.create_index(
        "ix_empresa_representante",
        "empresa",
        ["id_representante_permissionario"],
        schema="transporte_regulado",
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON transporte_regulado.empresa TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON transporte_regulado.empresa_id_seq TO aprimora_app"
    )

    op.execute("ALTER TABLE transporte_regulado.empresa ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE transporte_regulado.empresa FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON transporte_regulado.empresa
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON transporte_regulado.empresa
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON transporte_regulado.empresa"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON transporte_regulado.empresa"
    )
    op.drop_index(
        "ix_empresa_representante",
        table_name="empresa",
        schema="transporte_regulado",
    )
    op.drop_index(
        "ix_empresa_tenant_situacao",
        table_name="empresa",
        schema="transporte_regulado",
    )
    op.drop_index(
        "ix_empresa_tenant_excluido",
        table_name="empresa",
        schema="transporte_regulado",
    )
    op.drop_index(
        "uq_empresa_tenant_cnpj",
        table_name="empresa",
        schema="transporte_regulado",
    )
    op.drop_table("empresa", schema="transporte_regulado")
