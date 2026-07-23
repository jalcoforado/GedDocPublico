"""Protocolo P1: espécie documental + canal de entrada + data de recepção.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-26

Habilita a distinção entre **abertura de processo interno** (servidor abre
por demanda) e **protocolo de balcão** (documento físico chega na portaria).

Mudanças:
1. Cria `protocolos.especie_documental` — catálogo tenant-scoped (Ofício,
   Requerimento, Memorando, Declaração, Petição, ...).
2. Adiciona em `protocolos.processo`:
   - `id_especie_documental` (FK nullable — processo interno pode não ter)
   - `canal_entrada` VARCHAR(20) nullable — `balcao | portal | email | api | interno`
   - `data_recepcao` TIMESTAMP nullable — quando o documento físico chegou
     (pode ser diferente de `data_hora_abertura`, ex: chega sexta à noite,
     protocolado segunda)
3. Seed de 10 espécies comuns no tenant id=1 (Sobral).

RLS + GRANTs idênticos ao padrão das demais.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SEED_ESPECIES = [
    ("OFICIO", "Ofício"),
    ("REQUERIMENTO", "Requerimento"),
    ("MEMORANDO", "Memorando"),
    ("DECLARACAO", "Declaração"),
    ("PETICAO", "Petição"),
    ("CARTA", "Carta"),
    ("RELATORIO", "Relatório"),
    ("EDITAL", "Edital"),
    ("CERTIDAO", "Certidão"),
    ("OUTROS", "Outros"),
]


def upgrade() -> None:
    op.create_table(
        "especie_documental",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column("flag", sa.String(length=40), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("descricao", sa.String(length=500), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("tenant_id", "flag", name="uq_especie_documental_tenant_flag"),
        schema="protocolos",
    )
    op.create_index(
        "ix_especie_documental_tenant_ativo",
        "especie_documental",
        ["tenant_id", "ativo"],
        schema="protocolos",
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "protocolos.especie_documental TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON protocolos.especie_documental_id_seq TO aprimora_app"
    )

    op.execute("ALTER TABLE protocolos.especie_documental ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE protocolos.especie_documental FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON protocolos.especie_documental
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON protocolos.especie_documental
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )

    # Seed Sobral (tenant_id=1) com espécies padrão.
    for flag, nome in SEED_ESPECIES:
        op.execute(
            sa.text(
                "INSERT INTO protocolos.especie_documental "
                "(tenant_id, flag, nome, ativo, excluido) "
                "VALUES (1, :flag, :nome, TRUE, FALSE)"
            ).bindparams(flag=flag, nome=nome)
        )

    # Colunas em protocolos.processo
    op.add_column(
        "processo",
        sa.Column(
            "id_especie_documental",
            sa.Integer(),
            sa.ForeignKey("protocolos.especie_documental.id"),
            nullable=True,
        ),
        schema="protocolos",
    )
    op.add_column(
        "processo",
        sa.Column("canal_entrada", sa.String(length=20), nullable=True),
        schema="protocolos",
    )
    op.add_column(
        "processo",
        sa.Column("data_recepcao", sa.DateTime(), nullable=True),
        schema="protocolos",
    )

    # Backfill: processos existentes ficam como canal_entrada='interno'
    # (mais provável — foram abertos via UI Python "Novo processo").
    op.execute(
        "UPDATE protocolos.processo SET canal_entrada = 'interno' "
        "WHERE canal_entrada IS NULL"
    )

    op.create_index(
        "ix_processo_canal_entrada",
        "processo",
        ["tenant_id", "canal_entrada", "data_hora_abertura"],
        schema="protocolos",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_processo_canal_entrada", table_name="processo", schema="protocolos"
    )
    op.drop_column("processo", "data_recepcao", schema="protocolos")
    op.drop_column("processo", "canal_entrada", schema="protocolos")
    op.drop_column("processo", "id_especie_documental", schema="protocolos")

    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON protocolos.especie_documental"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON protocolos.especie_documental"
    )
    op.drop_index(
        "ix_especie_documental_tenant_ativo",
        table_name="especie_documental",
        schema="protocolos",
    )
    op.drop_table("especie_documental", schema="protocolos")
