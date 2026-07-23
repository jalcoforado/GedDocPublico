"""Cria schema aprimora_py + tabela job (jobs Celery)

Revision ID: 0001
Revises:
Create Date: 2026-05-23

Substitui o antigo schema-phase7-jobs.sql.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create utils schema and stub tables if they don't exist (for legacy PHP compatibility)
    op.execute('CREATE SCHEMA IF NOT EXISTS utils')
    op.execute('''
        CREATE TABLE IF NOT EXISTS utils.usuario (
            id INTEGER PRIMARY KEY,
            login VARCHAR(255),
            nome VARCHAR(500),
            email VARCHAR(255),
            senha VARCHAR(150),
            criado_em TIMESTAMP DEFAULT NOW()
        )
    ''')
    op.execute('''
        CREATE TABLE IF NOT EXISTS utils.usuario_externo (
            id INTEGER PRIMARY KEY,
            nome VARCHAR(500),
            email VARCHAR(255),
            senha VARCHAR(150),
            cpf_cnpj VARCHAR(14),
            ativo BOOLEAN DEFAULT true NOT NULL,
            excluido BOOLEAN DEFAULT false NOT NULL,
            data_criacao TIMESTAMP DEFAULT NOW() NOT NULL,
            tenant_id INTEGER NOT NULL
        )
    ''')
    op.execute('''
        CREATE TABLE IF NOT EXISTS utils.cidade (
            id INTEGER PRIMARY KEY,
            nome VARCHAR(255),
            uf VARCHAR(2),
            criado_em TIMESTAMP DEFAULT NOW()
        )
    ''')

    op.execute('CREATE SCHEMA IF NOT EXISTS aprimora_py')

    op.create_table(
        "job",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo", sa.String(length=60), nullable=False),
        sa.Column("descricao", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pendente'"),
        ),
        sa.Column("parametros", JSONB(), nullable=True),
        sa.Column("resultado_path", sa.String(length=500), nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column(
            "id_usuario",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=False,
        ),
        sa.Column("celery_task_id", sa.String(length=64), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("iniciado_em", sa.DateTime(), nullable=True),
        sa.Column("concluido_em", sa.DateTime(), nullable=True),
        schema="aprimora_py",
    )

    op.create_index(
        "ix_job_usuario_status",
        "job",
        ["id_usuario", "status"],
        schema="aprimora_py",
    )
    op.create_index(
        "ix_job_criado_em",
        "job",
        [sa.text("criado_em DESC")],
        schema="aprimora_py",
    )

    op.execute("GRANT USAGE ON SCHEMA aprimora_py TO ged_user")
    op.execute("GRANT ALL ON ALL TABLES IN SCHEMA aprimora_py TO ged_user")
    op.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA aprimora_py TO ged_user")


def downgrade() -> None:
    op.drop_index("ix_job_criado_em", table_name="job", schema="aprimora_py")
    op.drop_index("ix_job_usuario_status", table_name="job", schema="aprimora_py")
    op.drop_table("job", schema="aprimora_py")
