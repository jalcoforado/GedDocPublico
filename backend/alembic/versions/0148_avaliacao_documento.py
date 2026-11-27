"""Pedido de avaliação e decisão por documento (SI-73, RF-04 V2).

Revision ID: 0148
Revises: 0147
Create Date: 2026-11-26

Quem tramita o processo pede a um servidor do município que avalie um ou mais
documentos; o avaliador aprova ou devolve CADA um, com justificativa
obrigatória na devolução. Regras em `docs/avaliacao-de-documentos.md`.

- `protocolos.avaliacao_pedido`: quem pediu, quem avalia, orientação, prazo
  (opcional). `situacao` é `pendente` enquanto houver documento sem decisão,
  `concluida` quando todos foram decididos; volta a `pendente` no reenvio.
- `protocolos.avaliacao_documento`: um documento do pedido e a decisão dele.
  `id_anexo` é a VERSÃO EXATA avaliada (SI-72): a aprovação da versão 1 não
  vale para a versão 2. Reenviar o devolvido é uma linha nova, com a versão
  corrigida, apontando para a devolvida (`id_avaliacao_anterior`).
- Avaliar não é assinar: nada aqui toca `assinatura_anexo`.
- Índice único parcial: um documento (versão) tem no máximo UMA avaliação
  pendente, inclusive com dois pedidos ao mesmo tempo.
- CHECKs no banco: resultado só `aprovado`/`devolvido`; devolução sem
  justificativa não grava nem por fora da API.

Transação nova `documento_avaliar` (idempotente por `ON CONFLICT`, como a
0140); o vínculo com o módulo `protocolo` está em
`app/cli/seed_bootstrap.py::MODULO_TRANSACOES`.

RLS/grants: boilerplate padrão (GUC `app.tenant_id`, ENABLE + FORCE). Sem
grant ao `aprimora_worker`: nenhuma task escreve aqui.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0148"
down_revision: str | Sequence[str] | None = "0147"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "protocolos"
GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"
TABELAS = ("avaliacao_pedido", "avaliacao_documento")

CODIGO = "documento_avaliar"
ROTULO = "Avaliar documento de processo"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {S}.avaliacao_pedido (
            id serial PRIMARY KEY,
            tenant_id integer NOT NULL REFERENCES aprimora_py.tenant (id),
            id_processo integer NOT NULL REFERENCES protocolos.processo (id),
            id_usuario_solicitante integer NOT NULL REFERENCES utils.usuario (id),
            id_usuario_avaliador integer NOT NULL REFERENCES utils.usuario (id),
            orientacao varchar(2000) NULL,
            prazo date NULL,
            situacao varchar(20) NOT NULL DEFAULT 'pendente',
            criado_em timestamp NOT NULL DEFAULT NOW(),
            concluido_em timestamp NULL,
            excluido boolean NOT NULL DEFAULT false,
            CONSTRAINT ck_avaliacao_pedido_situacao
                CHECK (situacao IN ('pendente', 'concluida'))
        )
    """)
    op.execute(f"""
        CREATE TABLE {S}.avaliacao_documento (
            id serial PRIMARY KEY,
            tenant_id integer NOT NULL REFERENCES aprimora_py.tenant (id),
            id_pedido integer NOT NULL REFERENCES {S}.avaliacao_pedido (id),
            id_anexo integer NOT NULL REFERENCES protocolos.anexo (id),
            id_avaliacao_anterior integer NULL REFERENCES {S}.avaliacao_documento (id),
            resultado varchar(20) NULL,
            justificativa varchar(2000) NULL,
            id_usuario_decisao integer NULL REFERENCES utils.usuario (id),
            decidido_em timestamp NULL,
            criado_em timestamp NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_avaliacao_documento_resultado
                CHECK (resultado IS NULL OR resultado IN ('aprovado', 'devolvido')),
            CONSTRAINT ck_avaliacao_documento_devolucao_justificada
                CHECK (resultado IS DISTINCT FROM 'devolvido'
                       OR length(btrim(coalesce(justificativa, ''))) > 0)
        )
    """)
    op.execute(
        f"CREATE INDEX ix_avaliacao_pedido_processo ON {S}.avaliacao_pedido "
        "(tenant_id, id_processo)"
    )
    op.execute(
        f"CREATE INDEX ix_avaliacao_pedido_avaliador ON {S}.avaliacao_pedido "
        "(tenant_id, id_usuario_avaliador, situacao)"
    )
    op.execute(
        f"CREATE INDEX ix_avaliacao_pedido_solicitante ON {S}.avaliacao_pedido "
        "(tenant_id, id_usuario_solicitante, situacao)"
    )
    op.execute(
        f"CREATE INDEX ix_avaliacao_documento_pedido ON {S}.avaliacao_documento "
        "(tenant_id, id_pedido)"
    )
    op.execute(
        f"CREATE INDEX ix_avaliacao_documento_anexo ON {S}.avaliacao_documento "
        "(tenant_id, id_anexo)"
    )
    op.execute(
        f"CREATE UNIQUE INDEX ux_avaliacao_documento_pendente ON {S}.avaliacao_documento "
        "(tenant_id, id_anexo) WHERE resultado IS NULL"
    )
    # Um devolvido é reenviado no máximo uma vez.
    op.execute(
        f"CREATE UNIQUE INDEX ux_avaliacao_documento_reenvio ON {S}.avaliacao_documento "
        "(tenant_id, id_avaliacao_anterior) WHERE id_avaliacao_anterior IS NOT NULL"
    )

    for t in TABELAS:
        op.execute(f"ALTER TABLE {S}.{t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {S}.{t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation_select ON {S}.{t} "
            f"FOR SELECT USING (tenant_id = {GUC})"
        )
        op.execute(
            f"CREATE POLICY tenant_isolation_modify ON {S}.{t} "
            f"FOR ALL USING (tenant_id = {GUC}) WITH CHECK (tenant_id = {GUC})"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.{t} TO aprimora_app")
        op.execute(f"GRANT USAGE, SELECT ON {S}.{t}_id_seq TO aprimora_app")

    op.execute(
        "INSERT INTO utils.transacao (transacao, codigo, excluido) "
        f"VALUES ('{ROTULO}', '{CODIGO}', false) "
        "ON CONFLICT (codigo) DO NOTHING"
    )


def downgrade() -> None:
    # Mesma cautela da 0140: não arrancar permissão já dada a usuário real.
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
    for t in reversed(TABELAS):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {S}.{t}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {S}.{t}")
        op.execute(f"DROP TABLE IF EXISTS {S}.{t}")
