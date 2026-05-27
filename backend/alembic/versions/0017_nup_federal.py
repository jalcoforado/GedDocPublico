"""Protocolo P2: NUP federal (Decreto 8.539/2015).

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-27

NUP = Número Único de Protocolo, padrão federal exigido pra integração com
sistemas da União. Formato: `NNNNN.NNNNNN/AAAA-DD`
  - NNNNN (5 dígitos): código do órgão atribuído pelo SIORG/MP
  - NNNNNN (6 dígitos): sequencial por (órgão, ano)
  - AAAA (4 dígitos): ano da abertura
  - DD (2 dígitos): dígitos verificadores Mod-11

Adoção é **opt-in por tenant** via flag `usar_nup_federal`. Quando ativa,
processos novos recebem NUP além do `numero_processo` legado (formato
proprietário `P000011/2026` mantido pra compat com PHP).

Mudanças:
1. `aprimora_py.tenant`: novas colunas `codigo_orgao_nup` (5 dígitos) +
   `usar_nup_federal` (boolean, default FALSE).
2. `aprimora_py.nup_sequencia`: contador atômico por (tenant, órgão, ano).
   UPSERT garante concorrência segura sem precisar de SELECT FOR UPDATE.
3. `protocolos.processo`: `nup` (VARCHAR 25 formatado) +
   `numero_sequencial_orgao` (INT — usado pra reconstrução/auditoria).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # === Tenant: campos de configuração NUP ==================================
    op.add_column(
        "tenant",
        sa.Column("codigo_orgao_nup", sa.String(length=5), nullable=True),
        schema="aprimora_py",
    )
    op.add_column(
        "tenant",
        sa.Column(
            "usar_nup_federal",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        schema="aprimora_py",
    )
    op.create_check_constraint(
        "ck_tenant_codigo_orgao_nup_5_digitos",
        "tenant",
        "codigo_orgao_nup IS NULL OR codigo_orgao_nup ~ '^[0-9]{5}$'",
        schema="aprimora_py",
    )

    # === Tabela de sequência (counter atômico) ===============================
    op.create_table(
        "nup_sequencia",
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column("codigo_orgao", sa.String(length=5), nullable=False),
        sa.Column("ano", sa.Integer(), nullable=False),
        sa.Column(
            "ultimo_sequencial",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id", "codigo_orgao", "ano", name="pk_nup_sequencia"
        ),
        schema="aprimora_py",
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON aprimora_py.nup_sequencia TO aprimora_app"
    )
    # Esta tabela é catálogo de sequência — RLS isolando por tenant é o padrão.
    op.execute("ALTER TABLE aprimora_py.nup_sequencia ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aprimora_py.nup_sequencia FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON aprimora_py.nup_sequencia
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON aprimora_py.nup_sequencia
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )

    # === Processo: NUP + sequencial órgão ====================================
    op.add_column(
        "processo",
        sa.Column("nup", sa.String(length=25), nullable=True),
        schema="protocolos",
    )
    op.add_column(
        "processo",
        sa.Column("numero_sequencial_orgao", sa.Integer(), nullable=True),
        schema="protocolos",
    )
    op.create_index(
        "ix_processo_nup",
        "processo",
        ["tenant_id", "nup"],
        unique=False,
        schema="protocolos",
    )
    # NUP único quando preenchido (índice parcial)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_processo_nup_global ON protocolos.processo (nup)
            WHERE nup IS NOT NULL AND excluido IS FALSE
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS protocolos.uq_processo_nup_global")
    op.drop_index("ix_processo_nup", table_name="processo", schema="protocolos")
    op.drop_column("processo", "numero_sequencial_orgao", schema="protocolos")
    op.drop_column("processo", "nup", schema="protocolos")

    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON aprimora_py.nup_sequencia"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON aprimora_py.nup_sequencia"
    )
    op.drop_table("nup_sequencia", schema="aprimora_py")

    op.drop_constraint(
        "ck_tenant_codigo_orgao_nup_5_digitos",
        "tenant",
        type_="check",
        schema="aprimora_py",
    )
    op.drop_column("tenant", "usar_nup_federal", schema="aprimora_py")
    op.drop_column("tenant", "codigo_orgao_nup", schema="aprimora_py")
