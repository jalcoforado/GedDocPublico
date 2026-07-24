"""Assinatura v2 — integridade + evidências + status (PR2a, núcleo backend).

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-28

Evolui a assinatura interna para registrar hash do documento, evidências e
status, preservando as assinaturas legadas (sem hash retroativo).

- `protocolos.assinatura_anexo`: hash do documento + algoritmo + versão + IP +
  user agent + método de autenticação + nível + status + motivo + evidências
  (JSONB) + vínculo com audit_log.
- `protocolos.usuario_assinatura`: status + motivo/data de recusa.

Backfill não-disruptivo: tudo que já existe vira `nivel='legado'`; assinaturas
já realizadas recebem `metodo='senha_md5_legado'` e `status='assinada'`.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NIVEIS = "'legado','simples','avancada'"
_STATUS_AA = "'pendente','assinada','recusada','cancelada'"
_STATUS_UA = "'pendente','realizada','recusada'"


def upgrade() -> None:
    # === assinatura_anexo =====================================================
    op.add_column("assinatura_anexo", sa.Column("documento_hash", sa.String(64), nullable=True), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("hash_algoritmo", sa.String(20), nullable=True, server_default=sa.text("'sha256'")), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("documento_versao", sa.Integer(), nullable=True, server_default=sa.text("1")), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("ip_assinatura", sa.String(64), nullable=True), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("user_agent_assinatura", sa.String(512), nullable=True), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("metodo_autenticacao", sa.String(30), nullable=True), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("nivel_assinatura", sa.String(20), nullable=False, server_default=sa.text("'simples'")), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pendente'")), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("motivo", sa.String(1000), nullable=True), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("evidencias", postgresql.JSONB(), nullable=True), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("id_audit_log", sa.BigInteger(), sa.ForeignKey("aprimora_py.audit_log.id"), nullable=True), schema="protocolos")

    # Backfill: legado, sem hash retroativo.
    op.execute(
        """
        UPDATE protocolos.assinatura_anexo
           SET nivel_assinatura = 'legado',
               status = CASE WHEN assinado THEN 'assinada' ELSE 'pendente' END,
               metodo_autenticacao = CASE WHEN assinado THEN 'senha_md5_legado' ELSE NULL END
        """
    )

    op.create_check_constraint("ck_assinatura_anexo_nivel", "assinatura_anexo", f"nivel_assinatura IN ({_NIVEIS})", schema="protocolos")
    op.create_check_constraint("ck_assinatura_anexo_status", "assinatura_anexo", f"status IN ({_STATUS_AA})", schema="protocolos")
    op.create_index("ix_assinatura_anexo_status", "assinatura_anexo", ["tenant_id", "status"], unique=False, schema="protocolos")

    # === usuario_assinatura ===================================================
    op.add_column("usuario_assinatura", sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pendente'")), schema="protocolos")
    op.add_column("usuario_assinatura", sa.Column("motivo_recusa", sa.String(1000), nullable=True), schema="protocolos")
    op.add_column("usuario_assinatura", sa.Column("dt_recusa", sa.DateTime(), nullable=True), schema="protocolos")

    op.execute(
        """
        UPDATE protocolos.usuario_assinatura
           SET status = CASE WHEN realizada THEN 'realizada' ELSE 'pendente' END
        """
    )
    op.create_check_constraint("ck_usuario_assinatura_status", "usuario_assinatura", f"status IN ({_STATUS_UA})", schema="protocolos")


def downgrade() -> None:
    op.drop_constraint("ck_usuario_assinatura_status", "usuario_assinatura", type_="check", schema="protocolos")
    op.drop_column("usuario_assinatura", "dt_recusa", schema="protocolos")
    op.drop_column("usuario_assinatura", "motivo_recusa", schema="protocolos")
    op.drop_column("usuario_assinatura", "status", schema="protocolos")

    op.drop_index("ix_assinatura_anexo_status", table_name="assinatura_anexo", schema="protocolos")
    op.drop_constraint("ck_assinatura_anexo_status", "assinatura_anexo", type_="check", schema="protocolos")
    op.drop_constraint("ck_assinatura_anexo_nivel", "assinatura_anexo", type_="check", schema="protocolos")
    op.drop_column("assinatura_anexo", "id_audit_log", schema="protocolos")
    op.drop_column("assinatura_anexo", "evidencias", schema="protocolos")
    op.drop_column("assinatura_anexo", "motivo", schema="protocolos")
    op.drop_column("assinatura_anexo", "status", schema="protocolos")
    op.drop_column("assinatura_anexo", "nivel_assinatura", schema="protocolos")
    op.drop_column("assinatura_anexo", "metodo_autenticacao", schema="protocolos")
    op.drop_column("assinatura_anexo", "user_agent_assinatura", schema="protocolos")
    op.drop_column("assinatura_anexo", "ip_assinatura", schema="protocolos")
    op.drop_column("assinatura_anexo", "documento_versao", schema="protocolos")
    op.drop_column("assinatura_anexo", "hash_algoritmo", schema="protocolos")
    op.drop_column("assinatura_anexo", "documento_hash", schema="protocolos")
