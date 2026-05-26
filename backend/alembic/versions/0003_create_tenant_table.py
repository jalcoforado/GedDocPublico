"""Cria aprimora_py.tenant + seed Sobral (tenant_id=1)

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-23

Primeira pedra do multi-tenant. Tabela `aprimora_py.tenant` é a fonte da
verdade de quem é cada prefeitura. Seed cria `id=1, slug='sobral'` — todas
as tabelas de negócio na migration 0004 farão backfill para esse id.

A coluna `slug` (UNIQUE) será usada na Fase 12 como subdomínio
(`sobral.aprimora.app`). Campos `cor_primaria` e `logo_url` ficam prontos
para a Fase 15 (white-label) — adicionados agora pra evitar migration
nova só para 2 colunas.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("cnpj", sa.String(length=20), nullable=True),
        sa.Column(
            "id_cidade",
            sa.Integer(),
            sa.ForeignKey("utils.cidade.id"),
            nullable=True,
        ),
        sa.Column(
            "ativo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "plano",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'basico'"),
        ),
        sa.Column("cor_primaria", sa.String(length=7), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("slug", name="uq_tenant_slug"),
        schema="aprimora_py",
    )

    op.execute(
        """
        INSERT INTO aprimora_py.tenant (id, slug, nome)
        VALUES (1, 'sobral', 'Prefeitura Municipal de Sobral')
        """
    )

    # Ajusta sequence para não colidir com inserts futuros do tenant 1.
    op.execute(
        "SELECT setval('aprimora_py.tenant_id_seq', "
        "(SELECT COALESCE(MAX(id), 1) FROM aprimora_py.tenant))"
    )


def downgrade() -> None:
    op.drop_table("tenant", schema="aprimora_py")
