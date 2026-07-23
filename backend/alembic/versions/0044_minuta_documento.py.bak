"""Minuta de documento — editor interno + templates + Google Docs (fundação).

Revision ID: 0044
Revises: 0043
Create Date: 2026-07-09

Cria as tabelas de fundação da feature "redigir documento na hora de anexar":

- `protocolos.template_documento` — modelos de documento (HTML + placeholders), por tenant.
- `protocolos.minuta` — documento editável/versionado vinculado a um processo.
- `protocolos.minuta_historico` — snapshots append-only por "Salvar rascunho".
- `aprimora_py.google_credencial` — credenciais OAuth do Google (por usuário), tokens cifrados.

Todas tenant-scoped com GRANTs a `aprimora_app` + RLS (policies
`tenant_isolation_select`/`tenant_isolation_modify`) no mesmo padrão de
`transporte_regulado.veiculo` (0043). Adiciona também
`aprimora_py.tenant.google_docs_habilitado` (opt-in por tenant, default FALSE).
Os schemas `protocolos` e `aprimora_py` já existem; esta migration NÃO os recria.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0044"
down_revision: str | Sequence[str] | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_rls(qualified_table: str) -> None:
    """Habilita RLS + policies de isolamento por tenant (padrão 0043)."""
    op.execute(f"ALTER TABLE {qualified_table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {qualified_table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_select ON {qualified_table}
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_modify ON {qualified_table}
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def _drop_rls(qualified_table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {qualified_table}")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {qualified_table}")


def upgrade() -> None:
    # ------------------------------------------------------------------ tenant toggle
    op.add_column(
        "tenant",
        sa.Column(
            "google_docs_habilitado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        schema="aprimora_py",
    )

    # --------------------------------------------------------- template_documento
    op.create_table(
        "template_documento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("descricao", sa.String(length=300), nullable=True),
        sa.Column("categoria", sa.String(length=80), nullable=True),
        sa.Column("corpo_html", sa.Text(), nullable=False),
        sa.Column("placeholders_utilizados", JSONB(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
        sa.Column(
            "id_usuario_criacao",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=True,
        ),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        schema="protocolos",
    )
    op.create_index(
        "uq_template_documento_tenant_nome",
        "template_documento",
        ["tenant_id", "nome"],
        unique=True,
        schema="protocolos",
        postgresql_where=sa.text("excluido = false"),
    )
    op.create_index(
        "ix_template_documento_tenant_excluido",
        "template_documento",
        ["tenant_id", "excluido"],
        schema="protocolos",
    )
    op.create_index(
        "ix_template_documento_tenant_categoria",
        "template_documento",
        ["tenant_id", "categoria"],
        schema="protocolos",
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON protocolos.template_documento TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON protocolos.template_documento_id_seq TO aprimora_app"
    )
    _enable_rls("protocolos.template_documento")

    # -------------------------------------------------------------------- minuta
    op.create_table(
        "minuta",
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
        sa.Column(
            "id_template_origem",
            sa.Integer(),
            sa.ForeignKey("protocolos.template_documento.id"),
            nullable=True,
        ),
        sa.Column("titulo", sa.String(length=255), nullable=False),
        sa.Column(
            "origem",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'interno'"),
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'rascunho'"),
        ),
        sa.Column("versao", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("corpo_html", sa.Text(), nullable=True),
        sa.Column("google_doc_id", sa.String(length=120), nullable=True),
        sa.Column("google_doc_url", sa.String(length=500), nullable=True),
        sa.Column(
            "id_usuario_google",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=True,
        ),
        sa.Column(
            "id_anexo_final",
            sa.Integer(),
            sa.ForeignKey("protocolos.anexo.id"),
            nullable=True,
        ),
        sa.Column(
            "id_usuario_criacao",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=False,
        ),
        sa.Column(
            "id_usuario_finalizacao",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=True,
        ),
        sa.Column("finalizada_em", sa.DateTime(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
        sa.CheckConstraint(
            "origem IN ('interno', 'google')", name="ck_minuta_origem_valida"
        ),
        sa.CheckConstraint(
            "status IN ('rascunho', 'finalizada', 'cancelada')",
            name="ck_minuta_status_valido",
        ),
        sa.CheckConstraint(
            "(status = 'finalizada') = (id_anexo_final IS NOT NULL)",
            name="ck_minuta_finalizada_tem_anexo",
        ),
        sa.CheckConstraint(
            "origem = 'google' OR google_doc_id IS NULL",
            name="ck_minuta_google_doc_id_coerente",
        ),
        schema="protocolos",
    )
    op.create_index(
        "ix_minuta_tenant_processo",
        "minuta",
        ["tenant_id", "id_processo"],
        schema="protocolos",
    )
    op.create_index(
        "ix_minuta_tenant_status",
        "minuta",
        ["tenant_id", "status"],
        schema="protocolos",
    )
    op.create_index(
        "ix_minuta_tenant_excluido",
        "minuta",
        ["tenant_id", "excluido"],
        schema="protocolos",
    )
    op.create_index(
        "ix_minuta_anexo_final",
        "minuta",
        ["id_anexo_final"],
        schema="protocolos",
        postgresql_where=sa.text("id_anexo_final IS NOT NULL"),
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON protocolos.minuta TO aprimora_app"
    )
    op.execute("GRANT USAGE, SELECT ON protocolos.minuta_id_seq TO aprimora_app")
    _enable_rls("protocolos.minuta")

    # --------------------------------------------------------- minuta_historico
    op.create_table(
        "minuta_historico",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "id_minuta",
            sa.Integer(),
            sa.ForeignKey("protocolos.minuta.id"),
            nullable=False,
        ),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("corpo_html", sa.Text(), nullable=False),
        sa.Column(
            "id_usuario",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=False,
        ),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        schema="protocolos",
    )
    op.create_index(
        "uq_minuta_historico_minuta_versao",
        "minuta_historico",
        ["id_minuta", "versao"],
        unique=True,
        schema="protocolos",
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON protocolos.minuta_historico TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON protocolos.minuta_historico_id_seq TO aprimora_app"
    )
    _enable_rls("protocolos.minuta_historico")

    # --------------------------------------------------------- google_credencial
    op.create_table(
        "google_credencial",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "id_usuario",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=False,
        ),
        sa.Column("access_token_cifrado", sa.Text(), nullable=False),
        sa.Column("refresh_token_cifrado", sa.Text(), nullable=False),
        sa.Column("escopo", sa.String(length=255), nullable=False),
        sa.Column("expira_em", sa.DateTime(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "revogado", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
        schema="aprimora_py",
    )
    op.create_index(
        "uq_google_credencial_tenant_usuario",
        "google_credencial",
        ["tenant_id", "id_usuario"],
        unique=True,
        schema="aprimora_py",
        postgresql_where=sa.text("revogado = false"),
    )
    op.create_index(
        "ix_google_credencial_tenant_usuario",
        "google_credencial",
        ["tenant_id", "id_usuario"],
        schema="aprimora_py",
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON aprimora_py.google_credencial TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON aprimora_py.google_credencial_id_seq TO aprimora_app"
    )
    _enable_rls("aprimora_py.google_credencial")

    # ------------------------------------------------ permissão de admin de templates
    # Transação global (sem tenant_id) para gerir a biblioteca de templates, no
    # mesmo padrão idempotente de `dashboard` (0028). Super-usuário bypassa; grupos
    # não-SU recebem pela UI de grupos → transações. As MINUTAS em si reusam a
    # transação `processo` (atualizar), sem nova concessão.
    op.execute(
        """
        INSERT INTO utils.transacao (transacao, codigo)
        SELECT 'Templates de documento', 'minuta_template'
        WHERE NOT EXISTS (
            SELECT 1 FROM utils.transacao WHERE codigo = 'minuta_template'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM utils.grupo_transacao
        WHERE id_transacao IN (
            SELECT id FROM utils.transacao WHERE codigo = 'minuta_template'
        )
        """
    )
    op.execute(
        """
        DELETE FROM utils.sistema_transacao
        WHERE id_transacao IN (
            SELECT id FROM utils.transacao WHERE codigo = 'minuta_template'
        )
        """
    )
    op.execute("DELETE FROM utils.transacao WHERE codigo = 'minuta_template'")

    _drop_rls("aprimora_py.google_credencial")
    op.drop_index(
        "ix_google_credencial_tenant_usuario",
        table_name="google_credencial",
        schema="aprimora_py",
    )
    op.drop_index(
        "uq_google_credencial_tenant_usuario",
        table_name="google_credencial",
        schema="aprimora_py",
    )
    op.drop_table("google_credencial", schema="aprimora_py")

    _drop_rls("protocolos.minuta_historico")
    op.drop_index(
        "uq_minuta_historico_minuta_versao",
        table_name="minuta_historico",
        schema="protocolos",
    )
    op.drop_table("minuta_historico", schema="protocolos")

    _drop_rls("protocolos.minuta")
    op.drop_index("ix_minuta_anexo_final", table_name="minuta", schema="protocolos")
    op.drop_index("ix_minuta_tenant_excluido", table_name="minuta", schema="protocolos")
    op.drop_index("ix_minuta_tenant_status", table_name="minuta", schema="protocolos")
    op.drop_index("ix_minuta_tenant_processo", table_name="minuta", schema="protocolos")
    op.drop_table("minuta", schema="protocolos")

    _drop_rls("protocolos.template_documento")
    op.drop_index(
        "ix_template_documento_tenant_categoria",
        table_name="template_documento",
        schema="protocolos",
    )
    op.drop_index(
        "ix_template_documento_tenant_excluido",
        table_name="template_documento",
        schema="protocolos",
    )
    op.drop_index(
        "uq_template_documento_tenant_nome",
        table_name="template_documento",
        schema="protocolos",
    )
    op.drop_table("template_documento", schema="protocolos")

    op.drop_column("tenant", "google_docs_habilitado", schema="aprimora_py")
