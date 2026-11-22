"""Desarquivar processo (SI-60, RF-01): reinício do prazo e transação própria.

Revision ID: 0139
Revises: 0138
Create Date: 2026-11-22

Duas coisas, as duas pedidas pelo RF-01 do documento "GEDPub – Requisitos de
evolução v1.0" (18/11/2026):

1. `protocolos.processo.data_reinicio_prazo` — quando o processo é
   desarquivado, o prazo do serviço volta a contar do zero a partir dali
   (decisão do PO em 22/11/2026). O prazo era sempre contado de
   `data_hora_abertura`, que não pode ser reescrita: é o registro de quando o
   processo nasceu. Nula = nunca desarquivado, e o prazo conta da abertura
   como sempre contou. `ADD COLUMN` em tabela existente herda RLS e grants.

2. A transação `processo_desarquivar`. O RF-01 pede permissão específica, e
   reaproveitar `processo` + `atualizar` daria o poder de reabrir processo
   encerrado a todo operador que tramita. Idempotente por `ON CONFLICT`, como
   a 0090; o vínculo com o módulo `protocolo` está em
   `app/cli/seed_bootstrap.py::MODULO_TRANSACOES`.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0139"
down_revision: str | Sequence[str] | None = "0138"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CODIGO = "processo_desarquivar"
ROTULO = "Desarquivar processo"


def upgrade() -> None:
    op.add_column(
        "processo",
        sa.Column("data_reinicio_prazo", sa.DateTime(), nullable=True),
        schema="protocolos",
    )
    op.execute(
        "INSERT INTO utils.transacao (transacao, codigo, excluido) "
        f"VALUES ('{ROTULO}', '{CODIGO}', false) "
        "ON CONFLICT (codigo) DO NOTHING"
    )


def downgrade() -> None:
    # Mesma cautela da 0090: não arrancar permissão de usuário real. Se algum
    # grupo já recebeu a transação, a linha fica.
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
    op.drop_column("processo", "data_reinicio_prazo", schema="protocolos")
