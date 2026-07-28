"""Modularização F1 — catálogo de módulos, junção com transação e contratação por tenant.

Revision ID: 0073
Revises: 0072
Create Date: 2026-07-28

Três tabelas em aprimora_py:
- modulo: catálogo GLOBAL do produto (sem tenant_id, sem RLS).
- modulo_transacao: junção GLOBAL módulo <-> utils.transacao. Fica do NOSSO lado
  de propósito: `utils.*` é território do PHP legado e não é estendido aqui.
- tenant_modulo: contratação por tenant. SEM RLS por decisão (spec §4.1) — é
  tabela de plataforma, escrita pelo platform admin operando SOBRE outros
  tenants; uma policy em app.tenant_id bloquearia justamente esse caso de uso.
  Mesmo padrão de aprimora_py.tenant, que também não tem RLS.

O backfill contrata os 5 módulos de produto para TODOS os tenants existentes:
ninguém perde acesso no deploy. `comum` não é contratável.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0073"
down_revision: str | Sequence[str] | None = "0072"
branch_labels = None
depends_on = None
S = "aprimora_py"

MODULOS = [
    # (slug, nome, icone, ordem, contratavel)
    ("protocolo", "Protocolo", "FileText", 1, True),
    ("pagamentos", "Pagamentos", "Wallet", 2, True),
    ("frota", "Frota", "Truck", 3, True),
    ("transporte", "Transporte Regulado", "Bus", 4, True),
    ("administracao", "Administração", "Settings", 5, True),
    ("comum", "Comum", None, 99, False),
]


def upgrade() -> None:
    op.create_table(
        "modulo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(30), nullable=False),
        sa.Column("nome", sa.String(80), nullable=False),
        sa.Column("icone", sa.String(50), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contratavel", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.UniqueConstraint("slug", name="uq_modulo_slug"),
        schema=S,
    )
    op.execute(f"GRANT SELECT ON {S}.modulo TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.modulo_id_seq TO aprimora_app")

    op.create_table(
        "modulo_transacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("id_modulo", sa.Integer(), sa.ForeignKey(f"{S}.modulo.id"), nullable=False),
        sa.Column("id_transacao", sa.Integer(), sa.ForeignKey("utils.transacao.id"), nullable=False),
        sa.UniqueConstraint("id_modulo", "id_transacao", name="uq_modulo_transacao"),
        schema=S,
    )
    op.create_index("ix_modulo_transacao_transacao", "modulo_transacao", ["id_transacao"], schema=S)
    op.execute(f"GRANT SELECT ON {S}.modulo_transacao TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.modulo_transacao_id_seq TO aprimora_app")

    op.create_table(
        "tenant_modulo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey(f"{S}.tenant.id"), nullable=False),
        sa.Column("id_modulo", sa.Integer(), sa.ForeignKey(f"{S}.modulo.id"), nullable=False),
        sa.Column("contratado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        schema=S,
    )
    op.create_index(
        "uq_tenant_modulo_vivo", "tenant_modulo", ["tenant_id", "id_modulo"],
        unique=True, postgresql_where=sa.text("excluido = false"), schema=S,
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.tenant_modulo TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.tenant_modulo_id_seq TO aprimora_app")

    modulo = sa.table(
        "modulo",
        sa.column("slug"), sa.column("nome"), sa.column("icone"),
        sa.column("ordem"), sa.column("contratavel"),
        schema=S,
    )
    op.bulk_insert(modulo, [
        {"slug": s, "nome": n, "icone": i, "ordem": o, "contratavel": c}
        for s, n, i, o, c in MODULOS
    ])

    # Backfill: todo tenant existente contrata os 5 módulos de produto.
    op.execute(f"""
        INSERT INTO {S}.tenant_modulo (tenant_id, id_modulo)
        SELECT t.id, m.id
          FROM {S}.tenant t
         CROSS JOIN {S}.modulo m
         WHERE m.contratavel = true
    """)


def downgrade() -> None:
    op.drop_table("tenant_modulo", schema=S)
    op.drop_index("ix_modulo_transacao_transacao", table_name="modulo_transacao", schema=S)
    op.drop_table("modulo_transacao", schema=S)
    op.drop_table("modulo", schema=S)
