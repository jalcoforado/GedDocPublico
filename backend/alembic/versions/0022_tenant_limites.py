"""Tenant — limites básicos (PR 3a, Admin SaaS).

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-29

Campos de limite **apenas armazenados** (sem enforcement neste PR): o painel
admin coleta/exibe; o bloqueio efetivo (quota de usuários/armazenamento) fica
para um PR futuro. `aprimora_py.tenant` não tem RLS — segue assim.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("limite_usuarios", sa.Integer(), nullable=True), schema="aprimora_py")
    op.add_column("tenant", sa.Column("limite_armazenamento_mb", sa.Integer(), nullable=True), schema="aprimora_py")


def downgrade() -> None:
    op.drop_column("tenant", "limite_armazenamento_mb", schema="aprimora_py")
    op.drop_column("tenant", "limite_usuarios", schema="aprimora_py")
