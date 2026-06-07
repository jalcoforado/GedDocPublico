"""Frota PR-2 — `frota.motorista` (cadastro de motoristas/condutores).

Revision ID: 0032
Revises: 0031
Create Date: 2026-06-07

Cria `frota.motorista` no schema `frota` (já existente desde 0031), no mesmo
padrão de RLS/GRANTs/policies de `frota.veiculo`.

- `cpf` único por tenant **entre motoristas não excluídos** (índice parcial),
  validado também no serviço (409). Soft-delete via `excluido`.
- Reaproveita a permissão `frota` (NÃO semeia transação nova) — granularidade
  por entidade fica para fase futura, se necessário.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | Sequence[str] | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "motorista",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("cpf", sa.String(length=11), nullable=False),
        sa.Column("matricula", sa.String(length=40), nullable=True),
        sa.Column("cnh_numero", sa.String(length=11), nullable=False),
        sa.Column("cnh_categoria", sa.String(length=5), nullable=False),
        sa.Column("cnh_validade", sa.Date(), nullable=False),
        sa.Column("telefone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column(
            "id_unidade",
            sa.Integer(),
            sa.ForeignKey("utils.unidade_trabalho.id"),
            nullable=True,
        ),
        sa.Column(
            "id_usuario",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=True,
        ),
        sa.Column(
            "situacao",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'ativo'"),
        ),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
        schema="frota",
    )

    # CPF único por tenant SÓ entre não excluídos.
    op.create_index(
        "uq_motorista_tenant_cpf",
        "motorista",
        ["tenant_id", "cpf"],
        unique=True,
        schema="frota",
        postgresql_where=sa.text("excluido = false"),
    )
    op.create_index(
        "ix_motorista_tenant_excluido",
        "motorista",
        ["tenant_id", "excluido"],
        schema="frota",
    )

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON frota.motorista TO aprimora_app")
    op.execute("GRANT USAGE, SELECT ON frota.motorista_id_seq TO aprimora_app")

    op.execute("ALTER TABLE frota.motorista ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE frota.motorista FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON frota.motorista
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON frota.motorista
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_modify ON frota.motorista")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON frota.motorista")
    op.drop_index("ix_motorista_tenant_excluido", table_name="motorista", schema="frota")
    op.drop_index("uq_motorista_tenant_cpf", table_name="motorista", schema="frota")
    op.drop_table("motorista", schema="frota")
