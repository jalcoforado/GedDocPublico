"""Cancelar recebimento feito por engano (SI-61, RF-02): transação própria.

Revision ID: 0140
Revises: 0139
Create Date: 2026-11-22

O RF-02 do documento "GEDPub – Requisitos de evolução v1.0" (18/11/2026) pede
permissão específica para desfazer um "Receber" clicado por engano. Reusar
`processo` + `atualizar` daria a todo operador que tramita o poder de
reescrever onde o processo está. Idempotente por `ON CONFLICT`, como a 0090;
o vínculo com o módulo `protocolo` está em
`app/cli/seed_bootstrap.py::MODULO_TRANSACOES`.

Nenhuma coluna nova: cancelar o recebimento volta o encaminhamento para
pendente (`recebido=false`) e desativa a movimentação do recebimento, que
continua no histórico — os dois campos já existiam.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0140"
down_revision: str | Sequence[str] | None = "0139"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CODIGO = "processo_cancelar_recebimento"
ROTULO = "Cancelar recebimento de processo"


def upgrade() -> None:
    op.execute(
        "INSERT INTO utils.transacao (transacao, codigo, excluido) "
        f"VALUES ('{ROTULO}', '{CODIGO}', false) "
        "ON CONFLICT (codigo) DO NOTHING"
    )


def downgrade() -> None:
    # Mesma cautela da 0090: não arrancar permissão de usuário real.
    op.execute(f"""
        DELETE FROM utils.sistema_transacao st
         USING utils.transacao t
         WHERE st.id_transacao = t.id
           AND t.codigo = '{CODIGO}'
           AND NOT EXISTS (
               SELECT 1 FROM utils.grupo_transacao gt WHERE gt.id_transacao = t.id
           )
    """)
    op.execute(f"""
        DELETE FROM utils.transacao t
         WHERE t.codigo = '{CODIGO}'
           AND NOT EXISTS (
               SELECT 1 FROM utils.grupo_transacao gt WHERE gt.id_transacao = t.id
           )
    """)
