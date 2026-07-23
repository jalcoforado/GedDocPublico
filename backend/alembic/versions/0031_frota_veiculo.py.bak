"""Fundação do módulo de Frota Pública — schema `frota` + `frota.veiculo`.

Revision ID: 0031
Revises: 0030
Create Date: 2026-06-07

Cria o schema dedicado `frota` (auto-contido, paralelo a `protocolos`) e a tabela
`frota.veiculo` — cadastro tenant-scoped da frota própria do município. Segue o
padrão de RLS/GRANTs/policies da migration 0024 (`servico`).

- `placa` única por tenant **entre veículos não excluídos** (índice parcial),
  validada também no serviço de domínio (409). Soft-delete via `excluido`.
- `quilometragem_atual >= 0` garantido por CHECK no banco + `ge=0` no schema.
- Semeia a transação `frota` de forma idempotente (`WHERE NOT EXISTS`). Super-
  usuário bypassa; grupos não-SU recebem a permissão pela UI de grupos.

NÃO altera `provisioning_tenant`: a frota começa vazia em cada tenant.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | Sequence[str] | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS frota")
    op.execute("GRANT USAGE ON SCHEMA frota TO aprimora_app")

    op.create_table(
        "veiculo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column("placa", sa.String(length=8), nullable=False),
        sa.Column("renavam", sa.String(length=20), nullable=True),
        sa.Column("chassi", sa.String(length=30), nullable=True),
        sa.Column("marca", sa.String(length=60), nullable=True),
        sa.Column("modelo", sa.String(length=80), nullable=True),
        sa.Column("ano_fabricacao", sa.Integer(), nullable=True),
        sa.Column("ano_modelo", sa.Integer(), nullable=True),
        sa.Column("cor", sa.String(length=30), nullable=True),
        sa.Column("tipo_veiculo", sa.String(length=40), nullable=True),
        sa.Column("tipo_combustivel", sa.String(length=20), nullable=True),
        sa.Column(
            "situacao",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'disponivel'"),
        ),
        sa.Column(
            "id_unidade_responsavel",
            sa.Integer(),
            sa.ForeignKey("utils.unidade_trabalho.id"),
            nullable=True,
        ),
        sa.Column(
            "quilometragem_atual",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("data_aquisicao", sa.Date(), nullable=True),
        sa.Column(
            "forma_posse",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'proprio'"),
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
            "quilometragem_atual >= 0", name="ck_veiculo_km_nao_negativa"
        ),
        schema="frota",
    )

    # Placa única por tenant SÓ entre não excluídos (permite re-cadastrar placa
    # de um veículo soft-deletado).
    op.create_index(
        "uq_veiculo_tenant_placa",
        "veiculo",
        ["tenant_id", "placa"],
        unique=True,
        schema="frota",
        postgresql_where=sa.text("excluido = false"),
    )
    op.create_index(
        "ix_veiculo_tenant_excluido",
        "veiculo",
        ["tenant_id", "excluido"],
        schema="frota",
    )

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON frota.veiculo TO aprimora_app")
    op.execute("GRANT USAGE, SELECT ON frota.veiculo_id_seq TO aprimora_app")

    op.execute("ALTER TABLE frota.veiculo ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE frota.veiculo FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON frota.veiculo
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON frota.veiculo
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )

    # Permissão `frota` — idempotente, sem depender de índice único em codigo.
    op.execute(
        """
        INSERT INTO utils.transacao (transacao, codigo)
        SELECT 'Frota Pública', 'frota'
        WHERE NOT EXISTS (
            SELECT 1 FROM utils.transacao WHERE codigo = 'frota'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM utils.grupo_transacao
        WHERE id_transacao IN (SELECT id FROM utils.transacao WHERE codigo = 'frota')
        """
    )
    op.execute(
        """
        DELETE FROM utils.sistema_transacao
        WHERE id_transacao IN (SELECT id FROM utils.transacao WHERE codigo = 'frota')
        """
    )
    op.execute("DELETE FROM utils.transacao WHERE codigo = 'frota'")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_modify ON frota.veiculo")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON frota.veiculo")
    op.drop_index("ix_veiculo_tenant_excluido", table_name="veiculo", schema="frota")
    op.drop_index("uq_veiculo_tenant_placa", table_name="veiculo", schema="frota")
    op.drop_table("veiculo", schema="frota")
    op.execute("DROP SCHEMA IF EXISTS frota")
