"""Documento principal do anexo (SI-62): os arquivos que acompanham um documento.

Revision ID: 0140
Revises: 0139
Create Date: 2026-11-22

`protocolos.anexo_processo.id_anexo_principal` aponta para o documento que
o arquivo acompanha. Primeiro uso: os anexos enviados junto com o despacho
sem encaminhar são filhos do PDF assinado do despacho.

Por que não a movimentação: todo anexo se liga à ÚLTIMA movimentação do
processo (`anexos._criar_anexo_from_bytes`), então um arquivo enviado dias
depois do despacho, sem o processo andar, cairia na mesma movimentação e
pareceria ser do despacho. O vínculo tem de ser explícito.

Nulo para tudo o que já existe e para anexo avulso. `ADD COLUMN` herda RLS e
grants (CLAUDE.md §Migrations); tabela legada, como a 0139.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0140"
down_revision: str | Sequence[str] | None = "0139"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE protocolos.anexo_processo
            ADD COLUMN id_anexo_principal integer NULL
            REFERENCES protocolos.anexo (id)
    """)
    op.execute("""
        CREATE INDEX ix_anexo_processo_anexo_principal
            ON protocolos.anexo_processo (tenant_id, id_anexo_principal)
            WHERE id_anexo_principal IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS protocolos.ix_anexo_processo_anexo_principal")
    op.execute(
        "ALTER TABLE protocolos.anexo_processo DROP COLUMN IF EXISTS id_anexo_principal"
    )
