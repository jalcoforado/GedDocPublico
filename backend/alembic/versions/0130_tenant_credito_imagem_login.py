"""aprimora_py.tenant.imagem_login_credito — crédito da foto da tela de login

Revision ID: 0130
Revises: 0129
Create Date: 2026-10-08 14:00:00.000000

A foto do painel do login (``imagem_login_url``, 0129) pode ter licença que
exige atribuição — a de Itaitinga é CC BY-SA 3.0, do Wikimedia Commons. O
crédito é dado da imagem, e não texto fixo da tela: cada município tem a sua
foto e o seu autor. Sem valor, a tela não mostra linha de crédito.

**Sem ``GRANT UPDATE`` para ``aprimora_app``**, pelo mesmo motivo das duas
colunas da 0129: quem define a imagem e o crédito é a plataforma.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0130"
down_revision: str | Sequence[str] | None = "0129"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE aprimora_py.tenant ADD COLUMN imagem_login_credito VARCHAR(200) NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE aprimora_py.tenant DROP COLUMN imagem_login_credito")
