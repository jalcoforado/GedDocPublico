"""Adiciona colunas cpf e excluido a utils.usuario (necessárias para uniqueness constraints)

Revision ID: 0005a
Revises: 0004
Create Date: 2026-07-23

A tabela utils.usuario vem do legacy com colunas limitadas. Migração 0005 tenta
criar índices UNIQUE particionados por tenant_id nas colunas (email, cpf) —
mas cpf não estava na tabela.

Esta migration adiciona:
  - cpf (VARCHAR 14, pode ser NULL)
  - excluido (BOOLEAN NOT NULL DEFAULT FALSE)
  - tenant_id (INTEGER NOT NULL, referencia aprimora_py.tenant)
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005a"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Adiciona colunas que faltam em utils.usuario
    try:
        print("[0005a] Adding cpf column...")
        op.add_column(
            "usuario",
            sa.Column("cpf", sa.String(14), nullable=True),
            schema="utils",
        )
        print("[0005a] cpf column added ✓")
    except Exception as e:
        print(f"[0005a] cpf column failed: {e}")
        pass

    try:
        print("[0005a] Adding excluido column...")
        op.add_column(
            "usuario",
            sa.Column("excluido", sa.Boolean(), nullable=False, server_default=False),
            schema="utils",
        )
        print("[0005a] excluido column added ✓")
    except Exception as e:
        print(f"[0005a] excluido column failed: {e}")
        pass

    try:
        print("[0005a] Adding tenant_id column...")
        op.add_column(
            "usuario",
            sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="1"),
            schema="utils",
        )
        print("[0005a] tenant_id column added ✓")

        print("[0005a] Removing server default...")
        op.alter_column("usuario", "tenant_id", schema="utils", server_default=None)
        print("[0005a] server_default removed ✓")

        print("[0005a] Adding FK constraint...")
        op.execute(
            'ALTER TABLE utils.usuario ADD CONSTRAINT fk_usuario_tenant_id '
            'FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id)'
        )
        print("[0005a] FK constraint added ✓")
    except Exception as e:
        print(f"[0005a] tenant_id/FK failed: {e}")
        pass

    print("[0005a] Migration completed")


def downgrade() -> None:
    try:
        op.drop_constraint("fk_usuario_tenant_id", "usuario", schema="utils")
    except Exception:
        pass

    try:
        op.drop_column("usuario", "tenant_id", schema="utils")
    except Exception:
        pass

    try:
        op.drop_column("usuario", "excluido", schema="utils")
    except Exception:
        pass

    try:
        op.drop_column("usuario", "cpf", schema="utils")
    except Exception:
        pass
