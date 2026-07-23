"""Tenant — configuração inicial institucional + permissão `configuracao` (PR 3b).

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-29

Colunas institucionais editáveis pelo admin municipal (todas nullable).
`aprimora_py.tenant` não tem RLS — o endpoint PUT /tenants/me filtra por
`request.state.tenant_id` explicitamente. `id_unidade_padrao` é soft-ref a
`utils.unidade_trabalho.id` (sem FK rígida; validado no serviço), seguindo o
padrão de `usuario.id_unidade_trabalho`.

Também semeia a transação `configuracao` de forma idempotente. Usa
`WHERE NOT EXISTS` (não `ON CONFLICT`) porque a tabela legada `utils.transacao`
não tem índice único em `codigo`. Super-usuário bypassa a checagem; grupos
não-SU recebem a permissão pela UI de grupos → transações.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_COLUNAS = (
    ("sigla", sa.String(length=20)),
    ("email_institucional", sa.String(length=255)),
    ("telefone_institucional", sa.String(length=20)),
    ("endereco", sa.Text()),
    ("site_oficial", sa.String(length=255)),
    ("horario_atendimento", sa.String(length=255)),
    ("texto_boas_vindas_portal", sa.Text()),
    ("id_unidade_padrao", sa.Integer()),
)


def upgrade() -> None:
    for nome, tipo in _COLUNAS:
        op.add_column("tenant", sa.Column(nome, tipo, nullable=True), schema="aprimora_py")

    # Permissão `configuracao` — idempotente, sem depender de índice único em codigo.
    op.execute(
        """
        INSERT INTO utils.transacao (transacao, codigo)
        SELECT 'Configuração do tenant', 'configuracao'
        WHERE NOT EXISTS (
            SELECT 1 FROM utils.transacao WHERE codigo = 'configuracao'
        )
        """
    )


def downgrade() -> None:
    # Remove concessões da permissão (FK-safe) antes de remover a transação.
    op.execute(
        """
        DELETE FROM utils.grupo_transacao
        WHERE id_transacao IN (SELECT id FROM utils.transacao WHERE codigo = 'configuracao')
        """
    )
    op.execute(
        """
        DELETE FROM utils.sistema_transacao
        WHERE id_transacao IN (SELECT id FROM utils.transacao WHERE codigo = 'configuracao')
        """
    )
    op.execute("DELETE FROM utils.transacao WHERE codigo = 'configuracao'")

    for nome, _ in reversed(_COLUNAS):
        op.drop_column("tenant", nome, schema="aprimora_py")
