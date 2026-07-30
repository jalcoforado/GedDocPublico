"""Cria as transações que os routers exigem e nenhuma migration criou.

Revision ID: 0074
Revises: 0073
Create Date: 2026-07-28

Achado durante a fatia F1 da modularização: os routers exigem 23 códigos via
require_permission, mas só 14 existem em utils.transacao. Os nove ausentes
fazem usuário NÃO super-usuário tomar 403 por ausência de cadastro — o SU
mascarava o problema porque faz bypass antes de consultar a lista.

Idempotente por ON CONFLICT: em bancos que já receberam esses códigos por
outro caminho (dump do legado, inserção manual), a migration é no-op.
O vínculo com utils.sistema_transacao NÃO é feito aqui: a linha de
utils.sistema é criada pelo seed_bootstrap, que roda depois das migrations.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0074"
down_revision: str | Sequence[str] | None = "0073"
branch_labels = None
depends_on = None

TRANSACOES = [
    ("processo", "Processos"),
    ("usuario", "Usuários"),
    ("catalogo", "Catálogos do protocolo"),
    ("assunto", "Assuntos"),
    ("manifestante", "Manifestantes"),
    ("cidade", "Cidades"),
    ("endereco", "Endereços"),
    ("workflow", "Workflows"),
    ("unidadeTrabalho", "Unidades de trabalho"),
]


def upgrade() -> None:
    for codigo, rotulo in TRANSACOES:
        op.execute(
            "INSERT INTO utils.transacao (transacao, codigo, excluido) "
            f"VALUES ('{rotulo}', '{codigo}', false) "
            "ON CONFLICT (codigo) DO NOTHING"
        )


def downgrade() -> None:
    # Remove só o que esta migration poderia ter criado, e só se ninguém
    # tiver concedido a transação a um grupo — apagar um código em uso
    # arrancaria a permissão de usuários reais.
    codigos = ", ".join(f"'{c}'" for c, _ in TRANSACOES)
    op.execute(f"""
        DELETE FROM utils.transacao t
         WHERE t.codigo IN ({codigos})
           AND NOT EXISTS (
               SELECT 1 FROM utils.grupo_transacao gt WHERE gt.id_transacao = t.id
           )
           AND NOT EXISTS (
               SELECT 1 FROM utils.sistema_transacao st WHERE st.id_transacao = t.id
           )
           AND NOT EXISTS (
               SELECT 1 FROM aprimora_py.modulo_transacao mt WHERE mt.id_transacao = t.id
           )
    """)
