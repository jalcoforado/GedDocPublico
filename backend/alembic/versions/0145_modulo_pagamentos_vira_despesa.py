"""O módulo `pagamentos` passa a se chamar "Despesa" na tela.

Revision ID: 0145
Revises: 0144
Create Date: 2026-11-24

Decisão do Jorge em 2026-11-24: "a Financeira passa a ser chamada de Despesa,
não precisa mudar internamente".

Esta migration troca UM dado: `aprimora_py.modulo.nome`, que é o rótulo que o
launcher (`/modulos`) e o seletor de módulo mostram. O `slug` continua
`pagamentos`, e com ele continuam intactos a URL `/m/pagamentos`, as tabelas
do schema `pagamentos`, as transações `pagamento_*`, a API e os `link_url` já
gravados em `notificacao`.

**Por que o slug não muda**, mesmo sendo a parte visível na barra de endereço:
a regex de `nginx/default.conf` só cresce (token removido faz a URL antiga cair
no fallback legado, matando o próprio 308 que a mantém viva), `notificacao.
link_url` é registro histórico permanente, e `permanent: true` é cache de
navegador — destino errado em produção não se conserta com redeploy. Trocar o
slug é uma fatia própria, com inventário de `href`; trocar o rótulo é esta
migration de uma linha.

Idempotente e reversível: o `WHERE slug` não depende de id.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0145"
down_revision: str | Sequence[str] | None = "0144"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE aprimora_py.modulo SET nome = 'Despesa' WHERE slug = 'pagamentos'")


def downgrade() -> None:
    op.execute("UPDATE aprimora_py.modulo SET nome = 'Pagamentos' WHERE slug = 'pagamentos'")
