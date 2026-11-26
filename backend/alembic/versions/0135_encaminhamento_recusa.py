"""Protocolo — encaminhamento pode ser recusado por quem o receberia.

Revision ID: 0135
Revises: 0134
Create Date: 2026-10-13

Até aqui um encaminhamento pendente só tinha duas saídas: o destino recebe, ou
a origem cancela. Quem recebia um processo que não era da sua competência não
tinha como devolvê-lo — recebia e encaminhava de volta, e a linha do tempo
registrava uma passagem que nunca houve.

`protocolos.encaminhamento` ganha os quatro campos da recusa:

- `recusado` — o encaminhamento foi recusado pelo destino;
- `data_hora_recusa`, `id_usuario_recusa`, `motivo_recusa` — quando, quem e por
  quê. O motivo é obrigatório no serviço (`acoes_processo.recusar_encaminhamento`).

A recusa também marca `cancelado = true`: todo predicado de "encaminhamento
pendente" do sistema já é `recebido = false AND cancelado = false`, então o
processo deixa de estar em trânsito sem que nenhuma consulta existente precise
conhecer a coluna nova. `recusado` distingue QUEM desfez — é o que alimenta a
caixa "Recusados" da unidade de origem.

O CHECK garante a relação entre as duas colunas e que recusa tem motivo.

`ADD COLUMN` em tabela existente herda RLS e grants. `protocolos.encaminhamento`
é tabela legada: o `ALTER` roda com o papel dono, como as demais migrations que
mexem em `protocolos.*`. Backfill: `recusado` nasce `false` em toda linha.
"""
from __future__ import annotations

from alembic import op

revision = "0135"
down_revision = "0134"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE protocolos.encaminhamento
            ADD COLUMN recusado boolean NOT NULL DEFAULT false,
            ADD COLUMN data_hora_recusa timestamp without time zone,
            ADD COLUMN id_usuario_recusa integer REFERENCES utils.usuario(id),
            ADD COLUMN motivo_recusa text
    """)
    op.execute("""
        ALTER TABLE protocolos.encaminhamento
            ADD CONSTRAINT ck_encaminhamento_recusa CHECK (
                NOT recusado
                OR (cancelado AND NOT recebido
                    AND motivo_recusa IS NOT NULL AND data_hora_recusa IS NOT NULL)
            )
    """)
    # A caixa "Recusados" procura o ÚLTIMO encaminhamento de cada processo da
    # unidade de origem; recusa é rara, então o índice parcial fica pequeno.
    op.execute("""
        CREATE INDEX ix_encaminhamento_recusado
            ON protocolos.encaminhamento (tenant_id, id_unidade_origem, id_processo)
            WHERE recusado AND excluido = false
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS protocolos.ix_encaminhamento_recusado")
    op.execute(
        "ALTER TABLE protocolos.encaminhamento DROP CONSTRAINT IF EXISTS ck_encaminhamento_recusa"
    )
    op.execute("""
        ALTER TABLE protocolos.encaminhamento
            DROP COLUMN IF EXISTS motivo_recusa,
            DROP COLUMN IF EXISTS id_usuario_recusa,
            DROP COLUMN IF EXISTS data_hora_recusa,
            DROP COLUMN IF EXISTS recusado
    """)
