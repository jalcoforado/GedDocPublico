"""Protocolo P6: Apensamento + Desentranhamento + Volumes.

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-27

Três features documentais clássicas do setor público:

1. **Apensamento** — anexa um processo (filho) a outro (pai), pra tramitarem
   juntos. `Processo.id_processo_pai` já existia no schema; faltava o
   histórico/auditoria da operação. Nova tabela `processo_apensamento`
   registra apensação + desapensação com motivo e usuário.

2. **Desentranhamento** — remove um anexo de processo já formado, gerando
   termo formal. Anexo continua existindo no banco (não deleta); marca
   `desentranhado_em` em `anexo_processo` + motivo + autoridade.

3. **Volumes** — processo grande vira N volumes físicos numerados.
   Nova tabela `processo_volume` com numeração unique por (tenant, processo).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # === Apensamento (log) ====================================================
    op.create_table(
        "processo_apensamento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "id_processo_apensado",
            sa.Integer(),
            sa.ForeignKey("protocolos.processo.id"),
            nullable=False,
            comment="Processo filho (que está sendo apensado a outro)",
        ),
        sa.Column(
            "id_processo_principal",
            sa.Integer(),
            sa.ForeignKey("protocolos.processo.id"),
            nullable=False,
            comment="Processo pai (recebe o apensamento)",
        ),
        sa.Column(
            "id_usuario",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=False,
        ),
        sa.Column("motivo", sa.String(length=1000), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Quando desapensado:
        sa.Column("desapensado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "id_usuario_desapensamento",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=True,
        ),
        sa.Column("motivo_desapensamento", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "id_processo_apensado <> id_processo_principal",
            name="ck_apensamento_distintos",
        ),
        schema="protocolos",
    )
    op.create_index(
        "ix_apensamento_apensado",
        "processo_apensamento",
        ["tenant_id", "id_processo_apensado"],
        schema="protocolos",
    )
    op.create_index(
        "ix_apensamento_principal",
        "processo_apensamento",
        ["tenant_id", "id_processo_principal"],
        schema="protocolos",
    )
    # Apenas 1 apensamento ATIVO por processo filho — garantido por unique parcial.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_apensamento_filho_ativo
            ON protocolos.processo_apensamento (id_processo_apensado)
            WHERE desapensado_em IS NULL
        """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON protocolos.processo_apensamento TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON protocolos.processo_apensamento_id_seq TO aprimora_app"
    )
    op.execute(
        "ALTER TABLE protocolos.processo_apensamento ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE protocolos.processo_apensamento FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON protocolos.processo_apensamento
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON protocolos.processo_apensamento
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )

    # === Desentranhamento — flags em anexo_processo ==========================
    op.add_column(
        "anexo_processo",
        sa.Column("desentranhado_em", sa.DateTime(), nullable=True),
        schema="protocolos",
    )
    op.add_column(
        "anexo_processo",
        sa.Column(
            "id_usuario_desentranhamento",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=True,
        ),
        schema="protocolos",
    )
    op.add_column(
        "anexo_processo",
        sa.Column("motivo_desentranhamento", sa.String(length=1000), nullable=True),
        schema="protocolos",
    )
    op.add_column(
        "anexo_processo",
        sa.Column("autoridade_desentranhamento", sa.String(length=300), nullable=True),
        schema="protocolos",
    )

    # === Volumes ============================================================
    op.create_table(
        "processo_volume",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "id_processo",
            sa.Integer(),
            sa.ForeignKey("protocolos.processo.id"),
            nullable=False,
        ),
        sa.Column("numero", sa.Integer(), nullable=False, comment="Volume N (1, 2, 3…)"),
        sa.Column("pagina_inicial", sa.Integer(), nullable=True),
        sa.Column("pagina_final", sa.Integer(), nullable=True),
        sa.Column("observacao", sa.String(length=500), nullable=True),
        sa.Column(
            "id_usuario",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=False,
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "id_processo", "numero", name="uq_volume_processo_numero"
        ),
        sa.CheckConstraint("numero >= 1", name="ck_volume_numero_positivo"),
        sa.CheckConstraint(
            "(pagina_inicial IS NULL OR pagina_inicial >= 1) "
            "AND (pagina_final IS NULL OR pagina_final >= pagina_inicial)",
            name="ck_volume_paginas_validas",
        ),
        schema="protocolos",
    )
    op.create_index(
        "ix_volume_processo",
        "processo_volume",
        ["tenant_id", "id_processo", "numero"],
        schema="protocolos",
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON protocolos.processo_volume TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON protocolos.processo_volume_id_seq TO aprimora_app"
    )
    op.execute("ALTER TABLE protocolos.processo_volume ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE protocolos.processo_volume FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON protocolos.processo_volume
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON protocolos.processo_volume
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_modify ON protocolos.processo_volume")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON protocolos.processo_volume")
    op.drop_index("ix_volume_processo", table_name="processo_volume", schema="protocolos")
    op.drop_table("processo_volume", schema="protocolos")

    op.drop_column("anexo_processo", "autoridade_desentranhamento", schema="protocolos")
    op.drop_column("anexo_processo", "motivo_desentranhamento", schema="protocolos")
    op.drop_column("anexo_processo", "id_usuario_desentranhamento", schema="protocolos")
    op.drop_column("anexo_processo", "desentranhado_em", schema="protocolos")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_modify ON protocolos.processo_apensamento")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON protocolos.processo_apensamento")
    op.execute("DROP INDEX IF EXISTS protocolos.uq_apensamento_filho_ativo")
    op.drop_index(
        "ix_apensamento_principal", table_name="processo_apensamento", schema="protocolos"
    )
    op.drop_index(
        "ix_apensamento_apensado", table_name="processo_apensamento", schema="protocolos"
    )
    op.drop_table("processo_apensamento", schema="protocolos")
