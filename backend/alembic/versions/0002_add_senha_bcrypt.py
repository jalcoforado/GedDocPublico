"""Adiciona coluna senha_bcrypt em utils.usuario e utils.usuario_externo

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-23

Substitui o antigo schema-phase9-bcrypt.sql.

Coluna PARALELA — `utils.usuario.senha` (MD5) permanece intacta durante a
coexistência com o PHP. Só o Python lê/escreve `senha_bcrypt`. Pós-cutover,
quando o PHP for desligado, a coluna `senha` pode ser dropada (ver CUTOVER.md
passo 8).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column("senha_bcrypt", sa.String(length=255), nullable=True),
        schema="utils",
    )
    op.add_column(
        "usuario_externo",
        sa.Column("senha_bcrypt", sa.String(length=255), nullable=True),
        schema="utils",
    )


def downgrade() -> None:
    op.drop_column("usuario_externo", "senha_bcrypt", schema="utils")
    op.drop_column("usuario", "senha_bcrypt", schema="utils")
