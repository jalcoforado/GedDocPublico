"""SEC-1 — flag must_change_password em utils.usuario (Commit 1).

Revision ID: 0030
Revises: 0029
Create Date: 2026-06-05

Adiciona `utils.usuario.must_change_password` (BOOLEAN NOT NULL DEFAULT false)
para suportar a obrigação de troca de senha no primeiro acesso (SEC-1).

Decisões travadas no escopo (docs/archive/sec-pr1-must-change-password-escopo-implementavel.md):
- D-COLUNA-LOCAL: a flag mora em `utils.usuario`, não em tabela separada.
- D-BACKFILL: usuários EXISTENTES nascem com false — não são forçados a trocar
  senha retroativamente. Apenas novos usuários provisionados após o Commit X
  (provisionamento) virão com true.

Este commit é PURAMENTE de schema/modelo. Não introduz guard, whitelist,
interceptor, alteração de login, frontend, RUNBOOK ou comportamento funcional.
Aprimora-py + PHP legado seguem operando idênticos até o próximo commit.

Idempotência: bloco DO $$ checa information_schema antes de adicionar — a
tabela `utils.usuario` é compartilhada com o PHP legacy; defendemos contra o
caso de o legado já ter adicionado a coluna por outro caminho (improvável,
mas barato).

Downgrade: remove a coluna. Coluna é 100% nova do Python (PHP não a usa),
então a remoção é segura — diferente de `telefone` (0013), que veio do legado.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0030"
down_revision: str | Sequence[str] | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Adiciona coluna NOT NULL com server_default false.
    # NOT NULL + DEFAULT preenche linhas existentes automaticamente no
    # mesmo statement — o ALTER TABLE do PostgreSQL não precisa varrer
    # a tabela em 11+ (default rápido via pg_attribute.atthasdef).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'utils'
                  AND table_name = 'usuario'
                  AND column_name = 'must_change_password'
            ) THEN
                ALTER TABLE utils.usuario
                    ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT false;
            END IF;
        END$$;
        """
    )

    # 2. Backfill explícito (defesa em profundidade).
    # NOT NULL + DEFAULT já garante; este UPDATE é redundante e custa O(0) se
    # a coluna foi criada por este mesmo migration (todas as linhas já são
    # false), mas protege o caso teórico de a coluna ter sido criada nullable
    # antes por outro caminho.
    op.execute(
        """
        UPDATE utils.usuario
           SET must_change_password = false
         WHERE must_change_password IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("usuario", "must_change_password", schema="utils")
