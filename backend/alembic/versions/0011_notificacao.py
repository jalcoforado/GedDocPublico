"""Notificações in-app + email (stub) — Fase 17.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-25

Cria `aprimora_py.notificacao` para o motor de notificações.

- Multi-canal: in_app, email (driver futuro — hoje stub log), whatsapp (Fase 16).
- Destinatário: id_usuario (interno) ou destinatario_email livre (externo). Hoje
  só interno; cidadão via cookie usa um id_usuario_externo (futuro).
- `tipo` é uma string curta categorizando origem (sla_estourado, encaminhamento,
  assinatura_pendente, ...). Não enum no banco pra evitar migration toda vez
  que aparecer um tipo novo — convenção em string.
- `payload` JSONB pra carregar contexto (ex: id_alerta, id_processo, estado, ...).
- `lido_em` e `enviado_em` separados: lido = usuário viu no app; enviado = canal
  externo (email/whatsapp) processou o envio.
- RLS + GRANTs idênticos ao padrão das outras tabelas tenant.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notificacao",
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
            nullable=True,
        ),
        sa.Column("destinatario_email", sa.String(length=200), nullable=True),
        sa.Column("canal", sa.String(length=20), nullable=False),  # in_app | email | whatsapp
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("link_url", sa.String(length=500), nullable=True),
        sa.Column(
            "payload",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("prioridade", sa.String(length=10), nullable=False, server_default="normal"),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("lido_em", sa.DateTime(), nullable=True),
        sa.Column("enviado_em", sa.DateTime(), nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(id_usuario IS NOT NULL) OR (destinatario_email IS NOT NULL)",
            name="notificacao_destino_chk",
        ),
        schema="aprimora_py",
    )

    # Lookup principal: notificacoes não lidas do usuário, ordenadas pela mais recente
    op.create_index(
        "ix_notificacao_usuario_canal_lido",
        "notificacao",
        ["tenant_id", "id_usuario", "canal", "lido_em"],
        schema="aprimora_py",
    )
    # Lookup por payload→alerta (ex: dedup de SLA)
    op.create_index(
        "ix_notificacao_tipo_criado",
        "notificacao",
        ["tenant_id", "tipo", "criado_em"],
        schema="aprimora_py",
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "aprimora_py.notificacao TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON aprimora_py.notificacao_id_seq TO aprimora_app"
    )

    op.execute(
        "ALTER TABLE aprimora_py.notificacao ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE aprimora_py.notificacao FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON aprimora_py.notificacao
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON aprimora_py.notificacao
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_modify ON aprimora_py.notificacao"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON aprimora_py.notificacao"
    )
    op.drop_index(
        "ix_notificacao_tipo_criado", table_name="notificacao", schema="aprimora_py"
    )
    op.drop_index(
        "ix_notificacao_usuario_canal_lido",
        table_name="notificacao",
        schema="aprimora_py",
    )
    op.drop_table("notificacao", schema="aprimora_py")
