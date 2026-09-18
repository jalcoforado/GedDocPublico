"""Preferência de notificação por evento (F9, benchmark SUiTE).

Revision ID: 0115
Revises: 0114
Create Date: 2026-09-18

Substitui `notificacao_preferencia` (1 linha por usuário, 3 flags globais)
por `notificacao_preferencia_evento` (N linhas por usuário, uma por EVENTO —
`aprimora_py.notificacao.tipo` — com os mesmos 3 flags). O catálogo de
eventos conhecidos vive em código
(`services/notificacoes.py::EVENTOS_NOTIFICACAO`), não em tabela — mesmo
padrão de `MODULO_TRANSACOES` (`cli/seed_bootstrap.py`).

Escopo desta fatia: o catálogo real de eventos que hoje notificam usuário
INTERNO (`utils.usuario`, os únicos com preferência que faz sentido) é
`{"sla_estourado"}` — os outros tipos de notificação do sistema
(recadastramento.*, denuncia_decidida) vão para o REGULADO/denunciante
externo, que não tem `id_usuario` nem linha de preferência. A migração
preserva exatamente o comportamento de quem já configurou: a linha antiga
vira UMA linha nova com `evento='sla_estourado'`, mesmos 3 valores.

Reversível: downgrade recria a tabela antiga e prensa de volta só as linhas
`evento='sla_estourado'` (as únicas que a tabela antiga já continha).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0115"
down_revision: str | Sequence[str] | None = "0114"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "aprimora_py"
GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"


def upgrade() -> None:
    op.create_table(
        "notificacao_preferencia_evento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey(f"{S}.tenant.id"), nullable=False),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=False),
        sa.Column("evento", sa.String(60), nullable=False),
        sa.Column("canal_in_app", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("canal_email", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("canal_whatsapp", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        schema=S,
    )
    op.create_index(
        "uq_notif_pref_evento_tenant_usuario_evento",
        "notificacao_preferencia_evento",
        ["tenant_id", "id_usuario", "evento"],
        schema=S,
        unique=True,
    )

    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.notificacao_preferencia_evento TO aprimora_app"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON {S}.notificacao_preferencia_evento_id_seq TO aprimora_app"
    )
    op.execute(f"ALTER TABLE {S}.notificacao_preferencia_evento ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.notificacao_preferencia_evento FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_select ON {S}.notificacao_preferencia_evento
            FOR SELECT USING (tenant_id = {GUC})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_modify ON {S}.notificacao_preferencia_evento
            FOR ALL USING (tenant_id = {GUC}) WITH CHECK (tenant_id = {GUC})
        """
    )

    # Backfill: cada linha antiga -> uma linha nova com evento='sla_estourado'.
    op.execute(
        f"""
        INSERT INTO {S}.notificacao_preferencia_evento
            (tenant_id, id_usuario, evento, canal_in_app, canal_email,
             canal_whatsapp, criado_em, atualizado_em)
        SELECT tenant_id, id_usuario, 'sla_estourado', canal_in_app, canal_email,
               canal_whatsapp, criado_em, atualizado_em
        FROM {S}.notificacao_preferencia
        """
    )

    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {S}.notificacao_preferencia")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {S}.notificacao_preferencia")
    op.drop_index(
        "uq_notificacao_preferencia_tenant_usuario",
        table_name="notificacao_preferencia",
        schema=S,
    )
    op.drop_table("notificacao_preferencia", schema=S)


def downgrade() -> None:
    op.create_table(
        "notificacao_preferencia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey(f"{S}.tenant.id"), nullable=False),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=False),
        sa.Column("canal_in_app", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("canal_email", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("canal_whatsapp", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        schema=S,
    )
    op.create_index(
        "uq_notificacao_preferencia_tenant_usuario",
        "notificacao_preferencia",
        ["tenant_id", "id_usuario"],
        schema=S,
        unique=True,
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.notificacao_preferencia TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.notificacao_preferencia_id_seq TO aprimora_app")
    op.execute(f"ALTER TABLE {S}.notificacao_preferencia ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.notificacao_preferencia FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_select ON {S}.notificacao_preferencia
            FOR SELECT USING (tenant_id = {GUC})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_modify ON {S}.notificacao_preferencia
            FOR ALL USING (tenant_id = {GUC}) WITH CHECK (tenant_id = {GUC})
        """
    )

    op.execute(
        f"""
        INSERT INTO {S}.notificacao_preferencia
            (tenant_id, id_usuario, canal_in_app, canal_email, canal_whatsapp,
             criado_em, atualizado_em)
        SELECT tenant_id, id_usuario, canal_in_app, canal_email, canal_whatsapp,
               criado_em, atualizado_em
        FROM {S}.notificacao_preferencia_evento
        WHERE evento = 'sla_estourado'
        """
    )

    op.execute(
        f"DROP POLICY IF EXISTS tenant_isolation_modify ON {S}.notificacao_preferencia_evento"
    )
    op.execute(
        f"DROP POLICY IF EXISTS tenant_isolation_select ON {S}.notificacao_preferencia_evento"
    )
    op.drop_index(
        "uq_notif_pref_evento_tenant_usuario_evento",
        table_name="notificacao_preferencia_evento",
        schema=S,
    )
    op.drop_table("notificacao_preferencia_evento", schema=S)
