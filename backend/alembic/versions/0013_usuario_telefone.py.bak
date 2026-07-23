"""Adiciona telefone em utils.usuario — Fase 16 (WhatsApp).

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-26

Campo nullable porque a maioria dos usuários atuais não tem celular
cadastrado. Sem telefone, o canal whatsapp simplesmente é pulado pelo
motor de notificações (`enviar()` em services/notificacoes.py).

Formato sugerido E.164 (`+5588999998888`) — validação no app/serializer,
não na coluna, porque legados podem ter formatos diversos a importar
depois.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Idempotente: o legado PHP já pode ter criado essa coluna; checamos no
    # information_schema antes de adicionar. Não removemos no downgrade
    # exatamente pelo mesmo motivo — o legado depende.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'utils'
                  AND table_name = 'usuario'
                  AND column_name = 'telefone'
            ) THEN
                ALTER TABLE utils.usuario ADD COLUMN telefone VARCHAR(20);
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    # No-op intencional — coluna pode ser compartilhada com o PHP legado.
    pass
