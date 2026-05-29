"""Validação pública de assinatura — token opaco/revogável (PR2e).

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-28

Adiciona à `protocolos.assinatura_anexo` o código público de validação
(opaco, alta entropia, único) e os campos de revogação manual. A revogação
automática NÃO usa coluna: é avaliada de forma lazy na consulta pública
(processo deixou de ser ostensivo, anexo desentranhado, assinatura não mais
'assinada') — ver `services/validacao_publica.py`.

`validacao_expira_em` fica reservado (nullable, sem uso na regra inicial:
token perpétuo por natureza probatória).

Backfill: gera `codigo_validacao` apenas para assinaturas v2 já efetivadas
(status='assinada' e com hash). Linhas legadas (sem hash) ficam com código
NULL e não são validáveis publicamente. Índice único é parcial
(WHERE codigo_validacao IS NOT NULL).
"""
from __future__ import annotations

import secrets
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("assinatura_anexo", sa.Column("codigo_validacao", sa.String(64), nullable=True), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("validacao_publica_revogada", sa.Boolean(), nullable=False, server_default=sa.text("false")), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("validacao_revogada_motivo", sa.String(1000), nullable=True), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("validacao_revogada_em", sa.DateTime(), nullable=True), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("validacao_revogada_por", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True), schema="protocolos")
    op.add_column("assinatura_anexo", sa.Column("validacao_expira_em", sa.DateTime(), nullable=True), schema="protocolos")

    # Índice único PARCIAL — permite múltiplos NULL (linhas legadas) e garante
    # unicidade global do token entre as assinaturas v2.
    op.create_index(
        "uq_assinatura_anexo_codigo_validacao",
        "assinatura_anexo",
        ["codigo_validacao"],
        unique=True,
        schema="protocolos",
        postgresql_where=sa.text("codigo_validacao IS NOT NULL"),
    )

    # Backfill: só assinaturas v2 efetivadas (têm hash). Gera token opaco por linha.
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id FROM protocolos.assinatura_anexo "
            "WHERE status = 'assinada' AND documento_hash IS NOT NULL "
            "AND codigo_validacao IS NULL"
        )
    ).fetchall()
    for (rid,) in rows:
        conn.execute(
            sa.text("UPDATE protocolos.assinatura_anexo SET codigo_validacao = :c WHERE id = :i"),
            {"c": secrets.token_urlsafe(16), "i": rid},
        )


def downgrade() -> None:
    op.drop_index("uq_assinatura_anexo_codigo_validacao", table_name="assinatura_anexo", schema="protocolos")
    op.drop_column("assinatura_anexo", "validacao_expira_em", schema="protocolos")
    op.drop_column("assinatura_anexo", "validacao_revogada_por", schema="protocolos")
    op.drop_column("assinatura_anexo", "validacao_revogada_em", schema="protocolos")
    op.drop_column("assinatura_anexo", "validacao_revogada_motivo", schema="protocolos")
    op.drop_column("assinatura_anexo", "validacao_publica_revogada", schema="protocolos")
    op.drop_column("assinatura_anexo", "codigo_validacao", schema="protocolos")
