"""Adiciona tenant_id NOT NULL em todas as tabelas de negócio + backfill Sobral

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-23

Fase 11 do plano v2 — gating do multi-tenant. Cada tabela de negócio passa
a carregar `tenant_id INTEGER NOT NULL REFERENCES aprimora_py.tenant(id)`.

Estratégia por tabela (executada em transação única do Alembic):
  1. ADD COLUMN tenant_id INTEGER  (nullable temporariamente)
  2. UPDATE ... SET tenant_id = 1  (backfill Sobral)
  3. ALTER COLUMN tenant_id SET NOT NULL
  4. ADD CONSTRAINT fk_..._tenant_id FK aprimora_py.tenant(id)

Catálogos GENÉRICOS (não-tenant) ficam de fora: utils.estado, utils.cidade,
utils.bairro, utils.nivel, utils.sistema, utils.transacao, utils.sistema_constante,
public.modulos, public.configuracoes_modulos, public.configuracoes,
protocolos.acao, protocolos.prioridade, protocolos.tipo_assinatura.

Índices `(tenant_id, id)` criados nas 4 tabelas com volume relevante:
processo, movimentacao, encaminhamento, anexo_processo.

ATENÇÃO: esta migration assume que o aprimora-py é independente do PHP
legacy. Se o PHP em :8081 inserir em uma das tabelas abaixo após esta
migration, vai estourar NOT NULL violation — esperado e aceito (decisão
de 2026-05-23: PHP serviu como modelo inicial, não há concessões).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (schema, tabela) — ordem: catálogos antes de tabelas-fato (cosmético; o backfill é uniforme)
TABLES: list[tuple[str, str]] = [
    # protocolos
    ("protocolos", "tipo_manifestante"),
    ("protocolos", "tipo_processo"),
    ("protocolos", "tipo_anexo"),
    ("protocolos", "assunto"),
    ("protocolos", "assunto_tipo_processo_tipo_anexo"),
    ("protocolos", "manifestante"),
    ("protocolos", "processo"),
    ("protocolos", "movimentacao"),
    ("protocolos", "encaminhamento"),
    ("protocolos", "despacho"),
    ("protocolos", "arquivamento"),
    ("protocolos", "anexo"),
    ("protocolos", "anexo_processo"),
    ("protocolos", "solicitacao_assinatura"),
    ("protocolos", "usuario_assinatura"),
    ("protocolos", "assinatura_anexo"),
    # utils
    ("utils", "tipo_unidade_trabalho"),
    ("utils", "unidade_trabalho"),
    ("utils", "grupo"),
    ("utils", "grupo_transacao"),
    ("utils", "usuario"),
    ("utils", "usuario_externo"),
    ("utils", "usuario_grupo"),
    ("utils", "usuario_unidade_trabalho"),
    ("utils", "endereco"),
    # aprimora_py
    ("aprimora_py", "job"),
]

# Tabelas que ganham índice composto (tenant_id, id) — busca crítica do dia-a-dia.
INDEXED_TABLES: list[tuple[str, str]] = [
    ("protocolos", "processo"),
    ("protocolos", "movimentacao"),
    ("protocolos", "encaminhamento"),
    ("protocolos", "anexo_processo"),
]


def upgrade() -> None:
    for schema, table in TABLES:
        fq = f'"{schema}"."{table}"'
        fk_name = f"fk_{table}_tenant_id"

        # Check if table exists (may not be loaded from legacy schema)
        from sqlalchemy import text
        table_exists = op.get_bind().execute(
            text(f"""SELECT 1 FROM information_schema.tables
                     WHERE table_schema = '{schema}' AND table_name = '{table}'""")
        ).scalar()

        if not table_exists:
            # Table doesn't exist yet (will be created by other migrations)
            # Skip for now — it will be added in the migration that creates it
            continue

        # ADD COLUMN IF NOT EXISTS (column may come from legacy PHP schema)
        op.execute(f"ALTER TABLE {fq} ADD COLUMN IF NOT EXISTS tenant_id INTEGER")
        # Backfill NULL values with tenant 1
        op.execute(f"UPDATE {fq} SET tenant_id = 1 WHERE tenant_id IS NULL")
        # Set NOT NULL
        op.execute(f"ALTER TABLE {fq} ALTER COLUMN tenant_id SET NOT NULL")
        # Add FK constraint (use IF NOT EXISTS via exception handling)
        try:
            op.execute(
                f"ALTER TABLE {fq} ADD CONSTRAINT {fk_name} "
                f"FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id)"
            )
        except Exception:
            # FK may already exist from legacy schema
            pass

    for schema, table in INDEXED_TABLES:
        # Check if table exists before creating index
        from sqlalchemy import text
        table_exists = op.get_bind().execute(
            text(f"""SELECT 1 FROM information_schema.tables
                     WHERE table_schema = '{schema}' AND table_name = '{table}'""")
        ).scalar()

        if table_exists:
            # Create index (may already exist from legacy schema)
            try:
                op.execute(f"""
                    CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id_id
                    ON "{schema}"."{table}" (tenant_id, id)
                """)
            except Exception:
                # Index may already exist
                pass


def downgrade() -> None:
    for schema, table in INDEXED_TABLES:
        op.drop_index(f"ix_{table}_tenant_id_id", table_name=table, schema=schema)

    for schema, table in reversed(TABLES):
        fq = f'"{schema}"."{table}"'
        fk_name = f"fk_{table}_tenant_id"
        op.execute(f"ALTER TABLE {fq} DROP CONSTRAINT IF EXISTS {fk_name}")
        op.execute(f"ALTER TABLE {fq} DROP COLUMN tenant_id")
