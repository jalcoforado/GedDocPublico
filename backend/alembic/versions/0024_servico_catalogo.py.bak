"""Catálogo de Serviços / Carta de Serviços (PR 4a).

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-29

Cria `protocolos.servico` — catálogo tenant-scoped de serviços públicos
municipais. Segue o padrão de RLS/GRANTs/policies da migration 0015
(`especie_documental`). Os defaults (unidade/tipo/assunto/espécie) são FKs
nullable; a checagem de FK do Postgres NÃO filtra por tenant, então o serviço
de domínio valida same-tenant (igual `id_unidade_padrao` do PR 3b).

Também semeia a transação `servico` de forma idempotente (`WHERE NOT EXISTS`,
sem depender de índice único em `codigo`). Super-usuário bypassa; grupos não-SU
recebem a permissão pela UI de grupos → transações.

NÃO altera `provisioning_tenant` (D6): catálogo começa vazio.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0024"
down_revision: str | Sequence[str] | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "servico",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("descricao_curta", sa.String(length=300), nullable=True),
        sa.Column("descricao_detalhada", sa.Text(), nullable=True),
        sa.Column("publico_alvo", sa.String(length=255), nullable=True),
        sa.Column("instrucoes_cidadao", sa.Text(), nullable=True),
        sa.Column("documentos_exigidos", JSONB(), nullable=True),
        sa.Column("prazo_estimado_dias", sa.Integer(), nullable=True),
        sa.Column(
            "id_unidade_responsavel",
            sa.Integer(),
            sa.ForeignKey("utils.unidade_trabalho.id"),
            nullable=True,
        ),
        sa.Column(
            "id_tipo_processo_padrao",
            sa.Integer(),
            sa.ForeignKey("protocolos.tipo_processo.id"),
            nullable=True,
        ),
        sa.Column(
            "id_assunto_padrao",
            sa.Integer(),
            sa.ForeignKey("protocolos.assunto.id"),
            nullable=True,
        ),
        sa.Column(
            "id_especie_documental_padrao",
            sa.Integer(),
            sa.ForeignKey("protocolos.especie_documental.id"),
            nullable=True,
        ),
        sa.Column(
            "nivel_sigilo_padrao",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'ostensivo'"),
        ),
        sa.Column(
            "canal_entrada_permitido",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'portal'"),
        ),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("destaque", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("ordem_exibicao", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("categoria", sa.String(length=80), nullable=True),
        sa.Column("texto_confirmacao", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_servico_tenant_slug"),
        schema="protocolos",
    )
    op.create_index(
        "ix_servico_tenant_ativo_ordem",
        "servico",
        ["tenant_id", "ativo", "ordem_exibicao"],
        schema="protocolos",
    )

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON protocolos.servico TO aprimora_app")
    op.execute("GRANT USAGE, SELECT ON protocolos.servico_id_seq TO aprimora_app")

    op.execute("ALTER TABLE protocolos.servico ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE protocolos.servico FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON protocolos.servico
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON protocolos.servico
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )

    # Permissão `servico` — idempotente, sem depender de índice único em codigo.
    op.execute(
        """
        INSERT INTO utils.transacao (transacao, codigo)
        SELECT 'Catálogo de Serviços', 'servico'
        WHERE NOT EXISTS (
            SELECT 1 FROM utils.transacao WHERE codigo = 'servico'
        )
        """
    )


def downgrade() -> None:
    # Remove concessões da permissão (FK-safe) antes da transação.
    op.execute(
        """
        DELETE FROM utils.grupo_transacao
        WHERE id_transacao IN (SELECT id FROM utils.transacao WHERE codigo = 'servico')
        """
    )
    op.execute(
        """
        DELETE FROM utils.sistema_transacao
        WHERE id_transacao IN (SELECT id FROM utils.transacao WHERE codigo = 'servico')
        """
    )
    op.execute("DELETE FROM utils.transacao WHERE codigo = 'servico'")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_modify ON protocolos.servico")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON protocolos.servico")
    op.drop_index("ix_servico_tenant_ativo_ordem", table_name="servico", schema="protocolos")
    op.drop_table("servico", schema="protocolos")
