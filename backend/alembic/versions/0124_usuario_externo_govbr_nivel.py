"""usuario_externo.nivel_govbr — nível de confiabilidade da conta gov.br

Revision ID: 0124
Revises: 0122
Create Date: 2026-09-24 13:00:00.000000

Guarda o nível (``bronze``/``prata``/``ouro``) que o gov.br informou no último
login do cidadão por SSO (`services/govbr_sso.py`). Nulo quando o cidadão nunca
entrou pelo gov.br ou quando a consulta de níveis falhou — o login não depende
dele.

Sem boilerplate de RLS/GRANT: ``ADD COLUMN`` herda as policies e os grants de
tabela de ``utils.usuario_externo``, que não tem grant por coluna (ao contrário
de ``aprimora_py.tenant`` desde a 0080). O runtime municipal (``aprimora_app``)
grava a coluna no callback do SSO; ``tests/test_auth_govbr.py`` confere o
privilégio.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0124"
down_revision: str | Sequence[str] | None = "0122"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE utils.usuario_externo ADD COLUMN nivel_govbr VARCHAR(20) NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE utils.usuario_externo DROP COLUMN nivel_govbr")
