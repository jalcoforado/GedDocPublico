"""Complementação documental formal (PR 4d).

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-29

Cria `protocolos.complementacao_documental` — entidade que registra solicitações
formais de complementação documental do servidor ao cidadão (com mensagem +
lista de keys de `documentos_exigidos`) e a resposta do cidadão.

Segue o padrão de RLS/policies/GRANTs da migration 0024 (`servico`).

D-CONCORRENCIA: índice único parcial garante no máximo **uma** complementação
`aberta` viva por processo. A camada de service também valida (defesa em
profundidade) e responde 409 com mensagem amigável.

Não cria nova permissão em `utils.transacao` — reusa `processo:atualizar`
(D-PERMISSAO).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0027"
down_revision: str | Sequence[str] | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "complementacao_documental",
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
            "id_usuario_solicitante",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'aberta'"),
        ),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("documentos_solicitados", JSONB(), nullable=False),
        sa.Column("motivo_cancelamento", sa.Text(), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("respondido_em", sa.DateTime(), nullable=True),
        sa.Column("cancelado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "excluido",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.CheckConstraint(
            "status IN ('aberta', 'respondida', 'cancelada')",
            name="ck_complementacao_status",
        ),
        schema="protocolos",
    )

    op.create_index(
        "ix_complementacao_processo",
        "complementacao_documental",
        ["id_processo", sa.text("criado_em DESC")],
        schema="protocolos",
    )

    # D-CONCORRENCIA — no máximo UMA complementação aberta viva por processo.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_complementacao_aberta_por_processo
            ON protocolos.complementacao_documental(id_processo)
            WHERE status = 'aberta' AND excluido = FALSE
        """
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "protocolos.complementacao_documental TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON "
        "protocolos.complementacao_documental_id_seq TO aprimora_app"
    )

    op.execute(
        "ALTER TABLE protocolos.complementacao_documental ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE protocolos.complementacao_documental FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON protocolos.complementacao_documental
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON protocolos.complementacao_documental
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )


def downgrade() -> None:
    # DROP TABLE cascateia policies e índices.
    op.drop_table("complementacao_documental", schema="protocolos")
