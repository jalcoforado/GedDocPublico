"""Tenant piloto — troca só o nome de exibição, slug "sobral" continua igual.

O slug é parte do path físico dos uploads (`/app/uploads/tenants/sobral/...`)
e de queries fixas na suíte de testes — não mexemos nele. Isto é um UPDATE de
dado, não de schema: em banco novo (CI) roda antes do seed_bootstrap criar o
tenant, então não encontra a linha e não faz nada — o seed já cria com o nome
novo. Em banco existente (dev local, VPS) renomeia a linha já provisionada.

Revision ID: 0089
Revises: 0088
Create Date: 2026-08-08
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0089"
down_revision: str | Sequence[str] | None = "0088"
branch_labels = None
depends_on = None

NOME_ANTIGO = "Prefeitura de Sobral"
NOME_NOVO = "Minha Prefeitura"


def upgrade() -> None:
    op.execute(
        f"UPDATE aprimora_py.tenant SET nome = '{NOME_NOVO}' "
        f"WHERE slug = 'sobral' AND nome = '{NOME_ANTIGO}'"
    )


def downgrade() -> None:
    op.execute(
        f"UPDATE aprimora_py.tenant SET nome = '{NOME_ANTIGO}' "
        f"WHERE slug = 'sobral' AND nome = '{NOME_NOVO}'"
    )
