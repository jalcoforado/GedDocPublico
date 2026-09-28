"""usuario_externo_govbr_nivel

Revision ID: 0124
Revises: abebb5bcbad2
Create Date: 2026-09-24 13:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0124'
down_revision: str | Sequence[str] | None = 'abebb5bcbad2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE utils.usuario_externo 
        ADD COLUMN nivel_govbr VARCHAR(20) NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE utils.usuario_externo 
        DROP COLUMN nivel_govbr;
        """
    )
