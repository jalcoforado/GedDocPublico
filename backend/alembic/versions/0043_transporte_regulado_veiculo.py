"""Transporte Regulado PR-3 — `veiculo` (veículos regulados/permissionários).

Revision ID: 0043
Revises: 0042
Create Date: 2026-06-08

Cria `transporte_regulado.veiculo` — veículos vinculados a permissionários e/ou
empresas reguladas. SEPARADO da Frota Interna: NÃO referencia `frota.veiculo`. No
mesmo padrão de RLS/GRANTs/policies de `transporte_regulado.permissionario` (0041) e
`empresa` (0042). O schema e a transação `transporte_regulado` já existem (0041);
esta migration NÃO os recria nem os remove.

- `placa` única por tenant **entre veículos não excluídos** (índice parcial);
  `renavam`/`chassi` únicos por tenant entre não excluídos **quando informados**.
- Vínculo: pelo menos um de `id_permissionario`/`id_empresa` (CHECK + serviço);
  coerência de tenant garantida no serviço.
- `situacao` default `pendente`; CHECKs de coerência de datas/anos/capacidade.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0043"
down_revision: str | Sequence[str] | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "veiculo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "id_permissionario",
            sa.Integer(),
            sa.ForeignKey("transporte_regulado.permissionario.id"),
            nullable=True,
        ),
        sa.Column(
            "id_empresa",
            sa.Integer(),
            sa.ForeignKey("transporte_regulado.empresa.id"),
            nullable=True,
        ),
        sa.Column("placa", sa.String(length=7), nullable=False),
        sa.Column("renavam", sa.String(length=11), nullable=True),
        sa.Column("chassi", sa.String(length=17), nullable=True),
        sa.Column("marca", sa.String(length=60), nullable=False),
        sa.Column("modelo", sa.String(length=60), nullable=False),
        sa.Column("ano_fabricacao", sa.Integer(), nullable=True),
        sa.Column("ano_modelo", sa.Integer(), nullable=True),
        sa.Column("cor", sa.String(length=30), nullable=True),
        sa.Column("categoria", sa.String(length=20), nullable=True),
        sa.Column("tipo_servico", sa.String(length=30), nullable=False),
        sa.Column("capacidade_passageiros", sa.Integer(), nullable=True),
        sa.Column("tipo_combustivel", sa.String(length=20), nullable=True),
        sa.Column(
            "adaptado", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
        sa.Column("numero_autorizacao", sa.String(length=40), nullable=True),
        sa.Column("data_inicio_autorizacao", sa.Date(), nullable=True),
        sa.Column("data_validade_autorizacao", sa.Date(), nullable=True),
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
            "id_permissionario IS NOT NULL OR id_empresa IS NOT NULL",
            name="ck_veiculo_vinculo_obrigatorio",
        ),
        sa.CheckConstraint(
            "data_validade_autorizacao IS NULL OR data_inicio_autorizacao IS NULL "
            "OR data_validade_autorizacao >= data_inicio_autorizacao",
            name="ck_veiculo_datas_autorizacao_coerentes",
        ),
        sa.CheckConstraint(
            "ano_fabricacao IS NULL OR ano_modelo IS NULL "
            "OR ano_modelo >= ano_fabricacao",
            name="ck_veiculo_anos_coerentes",
        ),
        sa.CheckConstraint(
            "capacidade_passageiros IS NULL OR capacidade_passageiros >= 1",
            name="ck_veiculo_capacidade_positiva",
        ),
        schema="transporte_regulado",
    )

    # placa única por tenant SÓ entre não excluídos (permite re-cadastrar após soft-delete).
    op.create_index(
        "uq_veiculo_tenant_placa",
        "veiculo",
        ["tenant_id", "placa"],
        unique=True,
        schema="transporte_regulado",
        postgresql_where=sa.text("excluido = false"),
    )
    # renavam/chassi únicos por tenant quando informados (entre não excluídos).
    op.create_index(
        "uq_veiculo_tenant_renavam",
        "veiculo",
        ["tenant_id", "renavam"],
        unique=True,
        schema="transporte_regulado",
        postgresql_where=sa.text("excluido = false AND renavam IS NOT NULL"),
    )
    op.create_index(
        "uq_veiculo_tenant_chassi",
        "veiculo",
        ["tenant_id", "chassi"],
        unique=True,
        schema="transporte_regulado",
        postgresql_where=sa.text("excluido = false AND chassi IS NOT NULL"),
    )
    op.create_index(
        "ix_veiculo_tenant_excluido",
        "veiculo",
        ["tenant_id", "excluido"],
        schema="transporte_regulado",
    )
    op.create_index(
        "ix_veiculo_tenant_situacao",
        "veiculo",
        ["tenant_id", "situacao"],
        schema="transporte_regulado",
    )
    op.create_index(
        "ix_veiculo_permissionario",
        "veiculo",
        ["id_permissionario"],
        schema="transporte_regulado",
    )
    op.create_index(
        "ix_veiculo_empresa",
        "veiculo",
        ["id_empresa"],
        schema="transporte_regulado",
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON transporte_regulado.veiculo TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON transporte_regulado.veiculo_id_seq TO aprimora_app"
    )

    op.execute("ALTER TABLE transporte_regulado.veiculo ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE transporte_regulado.veiculo FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON transporte_regulado.veiculo
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON transporte_regulado.veiculo
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON transporte_regulado.veiculo"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON transporte_regulado.veiculo"
    )
    op.drop_index(
        "ix_veiculo_empresa", table_name="veiculo", schema="transporte_regulado"
    )
    op.drop_index(
        "ix_veiculo_permissionario", table_name="veiculo", schema="transporte_regulado"
    )
    op.drop_index(
        "ix_veiculo_tenant_situacao", table_name="veiculo", schema="transporte_regulado"
    )
    op.drop_index(
        "ix_veiculo_tenant_excluido", table_name="veiculo", schema="transporte_regulado"
    )
    op.drop_index(
        "uq_veiculo_tenant_chassi", table_name="veiculo", schema="transporte_regulado"
    )
    op.drop_index(
        "uq_veiculo_tenant_renavam", table_name="veiculo", schema="transporte_regulado"
    )
    op.drop_index(
        "uq_veiculo_tenant_placa", table_name="veiculo", schema="transporte_regulado"
    )
    op.drop_table("veiculo", schema="transporte_regulado")
