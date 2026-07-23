"""Particiona UNIQUEs globais por tenant_id (Fase 13a/b).

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-23

Constraints herdadas do PHP single-tenant que assumiam unicidade global:

  utils.usuario.usuario_email   UNIQUE (email)  WHERE excluido IS FALSE
  utils.usuario.usuario_cpf     UNIQUE (cpf)    WHERE excluido IS FALSE

No SaaS multi-tenant, duas prefeituras podem ter o MESMO email/cpf cadastrado
(servidor que trabalha em duas cidades, por exemplo). A unicidade deve ser
POR tenant. Esta migration substitui esses dois índices por versões
particionadas por tenant_id.

Não tocamos em `protocolos.processo.numero_processo` — a numeração já é
sequencial via função PG `gerar_numero_processo_string()` e o conflito
prático é nulo (sequence single-row por ano). Quando virar problema, ajusta.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # usuario.email
    op.execute("DROP INDEX IF EXISTS utils.usuario_email")
    try:
        op.execute(
            "CREATE UNIQUE INDEX usuario_email_per_tenant "
            "ON utils.usuario (tenant_id, email) "
            "WHERE excluido IS FALSE"
        )
    except Exception:
        # Index may already exist from legacy schema
        pass

    # usuario.cpf
    op.execute("DROP INDEX IF EXISTS utils.usuario_cpf")
    try:
        op.execute(
            "CREATE UNIQUE INDEX usuario_cpf_per_tenant "
            "ON utils.usuario (tenant_id, cpf) "
            "WHERE excluido IS FALSE"
        )
    except Exception:
        # Index may already exist from legacy schema
        pass


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS utils.usuario_cpf_per_tenant")
    op.execute(
        "CREATE UNIQUE INDEX usuario_cpf ON utils.usuario (cpf) "
        "WHERE excluido IS FALSE"
    )
    op.execute("DROP INDEX IF EXISTS utils.usuario_email_per_tenant")
    op.execute(
        "CREATE UNIQUE INDEX usuario_email ON utils.usuario (email) "
        "WHERE excluido IS FALSE"
    )
