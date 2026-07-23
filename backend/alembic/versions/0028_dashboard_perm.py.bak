"""Permissão de dashboard executivo (PR 5a).

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-30

Semeia a transação `dashboard` em `utils.transacao` de forma idempotente,
no mesmo padrão de `configuracao` (0023) e `servico` (0024). Não cria
tabela, não altera nenhuma tabela de domínio.

Super-usuário continua bypassando a checagem (caminho `is_super_usuario`
em `services/permissoes.py`); grupos não-SU recebem a permissão pela UI
de grupos → transações.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0028"
down_revision: str | Sequence[str] | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `utils.transacao` não tem índice único em codigo — usar WHERE NOT EXISTS
    # em vez de ON CONFLICT (mesmo padrão de 0023).
    op.execute(
        """
        INSERT INTO utils.transacao (transacao, codigo)
        SELECT 'Dashboard executivo', 'dashboard'
        WHERE NOT EXISTS (
            SELECT 1 FROM utils.transacao WHERE codigo = 'dashboard'
        )
        """
    )


def downgrade() -> None:
    # FK-safe: remove concessões antes da transação para evitar violação de
    # integridade referencial em `grupo_transacao` / `sistema_transacao`.
    op.execute(
        """
        DELETE FROM utils.grupo_transacao
        WHERE id_transacao IN (
            SELECT id FROM utils.transacao WHERE codigo = 'dashboard'
        )
        """
    )
    op.execute(
        """
        DELETE FROM utils.sistema_transacao
        WHERE id_transacao IN (
            SELECT id FROM utils.transacao WHERE codigo = 'dashboard'
        )
        """
    )
    op.execute("DELETE FROM utils.transacao WHERE codigo = 'dashboard'")
