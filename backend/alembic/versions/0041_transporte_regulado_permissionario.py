"""Transporte Regulado PR-1 — fundação do schema + `permissionario`.

Revision ID: 0041
Revises: 0040
Create Date: 2026-06-08

Cria o schema dedicado `transporte_regulado` (auto-contido, paralelo a `frota`)
e a tabela `transporte_regulado.permissionario` — cadastro tenant-scoped de
permissionários do transporte regulado (táxi, mototáxi, transporte escolar etc.).
Segue o padrão de RLS/GRANTs/policies de `frota.veiculo` (0031).

- `cpf` único por tenant **entre permissionários não excluídos** (índice parcial),
  validado também no serviço de domínio (409). Soft-delete via `excluido`.
- `situacao` default `pendente`; validada na aplicação (sem CHECK de enum).
- CHECK de coerência das datas da permissão (validade >= início), tolerante a NULL.
- Semeia a transação `transporte_regulado` de forma idempotente (mesmo padrão de
  `frota` na 0031). Super-usuário bypassa; grupos não-SU recebem via UI de grupos.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: str | Sequence[str] | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS transporte_regulado")
    op.execute("GRANT USAGE ON SCHEMA transporte_regulado TO aprimora_app")

    op.create_table(
        "permissionario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("cpf", sa.String(length=11), nullable=False),
        sa.Column("rg", sa.String(length=20), nullable=True),
        sa.Column("data_nascimento", sa.Date(), nullable=True),
        sa.Column("telefone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("cnh_numero", sa.String(length=11), nullable=True),
        sa.Column("cnh_categoria", sa.String(length=5), nullable=True),
        sa.Column("cnh_validade", sa.Date(), nullable=True),
        sa.Column("tipo_servico", sa.String(length=30), nullable=False),
        sa.Column("numero_permissao", sa.String(length=40), nullable=True),
        sa.Column("data_inicio_permissao", sa.Date(), nullable=True),
        sa.Column("data_validade_permissao", sa.Date(), nullable=True),
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
            "data_validade_permissao IS NULL OR data_inicio_permissao IS NULL "
            "OR data_validade_permissao >= data_inicio_permissao",
            name="ck_permissionario_datas_permissao_coerentes",
        ),
        schema="transporte_regulado",
    )

    # CPF único por tenant SÓ entre não excluídos (permite re-cadastrar após soft-delete).
    op.create_index(
        "uq_permissionario_tenant_cpf",
        "permissionario",
        ["tenant_id", "cpf"],
        unique=True,
        schema="transporte_regulado",
        postgresql_where=sa.text("excluido = false"),
    )
    op.create_index(
        "ix_permissionario_tenant_excluido",
        "permissionario",
        ["tenant_id", "excluido"],
        schema="transporte_regulado",
    )
    op.create_index(
        "ix_permissionario_tenant_situacao",
        "permissionario",
        ["tenant_id", "situacao"],
        schema="transporte_regulado",
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON transporte_regulado.permissionario TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON transporte_regulado.permissionario_id_seq TO aprimora_app"
    )

    op.execute("ALTER TABLE transporte_regulado.permissionario ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE transporte_regulado.permissionario FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON transporte_regulado.permissionario
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON transporte_regulado.permissionario
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )

    # Permissão `transporte_regulado` — idempotente (mesmo padrão de `frota`/0031).
    op.execute(
        """
        INSERT INTO utils.transacao (transacao, codigo)
        SELECT 'Transporte Regulado', 'transporte_regulado'
        WHERE NOT EXISTS (
            SELECT 1 FROM utils.transacao WHERE codigo = 'transporte_regulado'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM utils.grupo_transacao
        WHERE id_transacao IN (
            SELECT id FROM utils.transacao WHERE codigo = 'transporte_regulado'
        )
        """
    )
    op.execute(
        """
        DELETE FROM utils.sistema_transacao
        WHERE id_transacao IN (
            SELECT id FROM utils.transacao WHERE codigo = 'transporte_regulado'
        )
        """
    )
    op.execute("DELETE FROM utils.transacao WHERE codigo = 'transporte_regulado'")

    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON transporte_regulado.permissionario"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON transporte_regulado.permissionario"
    )
    op.drop_index(
        "ix_permissionario_tenant_situacao",
        table_name="permissionario",
        schema="transporte_regulado",
    )
    op.drop_index(
        "ix_permissionario_tenant_excluido",
        table_name="permissionario",
        schema="transporte_regulado",
    )
    op.drop_index(
        "uq_permissionario_tenant_cpf",
        table_name="permissionario",
        schema="transporte_regulado",
    )
    op.drop_table("permissionario", schema="transporte_regulado")
    op.execute("DROP SCHEMA IF EXISTS transporte_regulado")
