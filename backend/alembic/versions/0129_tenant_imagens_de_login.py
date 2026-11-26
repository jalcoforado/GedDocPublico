"""aprimora_py.tenant — logo e imagem próprios da tela de login

Revision ID: 0129
Revises: 0128
Create Date: 2026-10-07 21:00:00.000000

A tela de login passa a ter a identidade do município: uma foto da cidade
ocupando metade da tela e a marca da prefeitura sobre o formulário. O
``logo_url`` que já existia é a marca QUADRADA (barra lateral, cabeçalho), e
não serve aqui — a marca de uma prefeitura costuma ser horizontal, com o nome.

- ``logo_login_url``: marca usada no login (qualquer proporção).
- ``imagem_login_url``: foto do painel esquerdo.

As duas são opcionais; sem elas o login cai no ``logo_url`` e num fundo liso na
cor do tenant.

**Sem ``GRANT UPDATE`` para ``aprimora_app``, de propósito.** Desde a 0080 o
``UPDATE`` do runtime municipal em ``aprimora_py.tenant`` é por coluna, e coluna
nova nasce sem ele. Nenhum caminho municipal grava estas duas hoje — quem as
define é a plataforma (seed/CLI, pelo papel administrativo). No dia em que a
tela de configurações do município for editá-las, a migration daquele PR
acrescenta o grant e as inclui em ``COLUNAS_MUNICIPAIS_DE_TENANT``.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0129"
down_revision: str | Sequence[str] | None = "0128"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE aprimora_py.tenant
            ADD COLUMN logo_login_url VARCHAR(500) NULL,
            ADD COLUMN imagem_login_url VARCHAR(500) NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE aprimora_py.tenant
            DROP COLUMN imagem_login_url,
            DROP COLUMN logo_login_url
        """
    )
