"""Cria a transação `auditoria` — item 1.0.8.

Revision ID: 0090
Revises: 0089
Create Date: 2026-08-11

`GET /api/v2/audit` era legível por qualquer autenticado do tenant. Fechar
isso exige um código de permissão, e nenhum dos 24 existentes serve: gatear a
trilha de auditoria com `usuario` ou `configuracao` a esconderia dentro de um
código que significa outra coisa, e o próximo a ler a tela de permissões
entenderia errado.

Idempotente por `ON CONFLICT`, como a 0074. O vínculo com `utils.sistema` é do
`seed_bootstrap`, que roda depois das migrations; a atribuição ao módulo
`administracao` está em `app/cli/seed_bootstrap.py::MODULO_TRANSACOES`.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0090"
down_revision: str | Sequence[str] | None = "0089"
branch_labels = None
depends_on = None

CODIGO = "auditoria"
ROTULO = "Trilha de auditoria"


def upgrade() -> None:
    op.execute(
        "INSERT INTO utils.transacao (transacao, codigo, excluido) "
        f"VALUES ('{ROTULO}', '{CODIGO}', false) "
        "ON CONFLICT (codigo) DO NOTHING"
    )


def downgrade() -> None:
    # Mesma cautela da 0074: não arrancar permissão de usuário real. Se algum
    # grupo já recebeu a transação, a linha fica.
    op.execute(f"""
        DELETE FROM utils.transacao t
         WHERE t.codigo = '{CODIGO}'
           AND NOT EXISTS (
               SELECT 1 FROM utils.grupo_transacao gt WHERE gt.id_transacao = t.id
           )
    """)
