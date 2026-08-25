"""Pagamentos F2.1 — pedido_ajuste, debito_versao, anexo_debito + backfill.

Revision ID: 0105
Revises: 0104
Create Date: 2026-08-25

Três tabelas novas do módulo de pagamentos:

- `pagamentos.pedido_ajuste` — o pedido formal de ajuste que uma etapa
  (GESTOR/VALIDACAO/AUTORIDADE) abre sobre um débito antes de decidir. É a
  peça que faltava para o fluxo `AJUSTE_*` ter rastro: hoje
  `situacao_tramitacao='AJUSTE_GESTOR'` só existe no débito, sem registro de
  quem pediu o quê.
- `pagamentos.debito_versao` — snapshot append-only dos campos materiais do
  débito, congelado sempre que uma resposta de ajuste os altera. `versao` é
  a versão ANTERIOR à mudança (a versão corrente vive em `debito.versao`).
- `pagamentos.anexo_debito` — vínculo (soft-delete) entre um débito e um
  anexo de `protocolos.anexo`, versionado por `versao_debito` e opcionalmente
  amarrado ao pedido de ajuste que o motivou.

Mais 7 colunas em `pagamentos.debito_historico` (todas nullable, sem
backfill de linha antiga: a trilha existente não tinha essas dimensões) para
o histórico passar a registrar também a versão do débito e as três
transições de situação (tramitação/fila/pagamento) lado a lado, em vez de só
`status_anterior`/`status_novo` do campo legado.

RLS/grants: mesmo boilerplate `_rls` da 0102 (GUC `app.tenant_id`,
`current_setting` com o segundo argumento `true`, ENABLE + FORCE). Sem a
policy extra `OR IS NULL` da 0103 — essas três tabelas não têm o caso de uso
que motivou aquela exceção. `ADD COLUMN` em `debito_historico` herda a RLS
já existente da tabela — não repetir.

Backfill sintético (spec F2 §4.5, Ruling 1): todo débito hoje em
`AJUSTE_GESTOR`/`AJUSTE_VALIDACAO`/`AJUSTE_AUTORIDADE` nasceu ANTES da F2,
então não tem `pedido_ajuste` correspondente. Sem isso a Task 3 (consulta de
pendências por etapa) trataria esses débitos como órfãos — pendentes de algo
que ninguém nunca pediu. O backfill cria, para cada um, um pedido sintético
em situação `ABERTO`, best-effort no ator/motivo via o último
`debito_historico` relevante (`AJUSTE_SOLICITADO`/`DEVOLVIDO`/`SUSPENSO`) e
com o texto de aviso "Pedido sintético criado pela migration 0105 (F2)."
quando não há justificativa aproveitável. Em banco limpo (CI) a tabela
`debito` está vazia nesse ponto e o INSERT ... SELECT roda e não insere
nenhuma linha — o que já prova que o SQL é válido antes de tocar produção.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0105"
down_revision: str | Sequence[str] | None = "0104"
branch_labels = None
depends_on = None

S = "pagamentos"

GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"


def _rls(tabela: str) -> None:
    op.execute(f"ALTER TABLE {S}.{tabela} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.{tabela} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_select ON {S}.{tabela} "
        f"FOR SELECT USING (tenant_id = {GUC})"
    )
    op.execute(
        f"CREATE POLICY tenant_isolation_modify ON {S}.{tabela} "
        f"FOR ALL USING (tenant_id = {GUC}) WITH CHECK (tenant_id = {GUC})"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.{tabela} TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.{tabela}_id_seq TO aprimora_app")


def upgrade() -> None:
    # ------------------------------------------------------------ pedido_ajuste
    op.create_table(
        "pedido_ajuste",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_debito", sa.Integer, sa.ForeignKey("pagamentos.debito.id"), nullable=False),
        sa.Column("versao_debito", sa.Integer, nullable=False),
        sa.Column("etapa_solicitante", sa.String(15), nullable=False),  # GESTOR | VALIDACAO | AUTORIDADE
        sa.Column("id_usuario_solicitante", sa.Integer, sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("motivo", sa.String(255), nullable=False),
        sa.Column("descricao", sa.Text, nullable=False),
        sa.Column("transacao_responsavel", sa.String(50), nullable=False),
        sa.Column("tipo", sa.String(15), nullable=False),  # MATERIAL | NAO_MATERIAL
        sa.Column("prazo", sa.Date, nullable=True),
        sa.Column("campos_relacionados", postgresql.JSONB, nullable=True),
        sa.Column("situacao", sa.String(15), nullable=False),  # ABERTO | RESPONDIDO | RESOLVIDO | CANCELADO
        sa.Column("resposta", sa.Text, nullable=True),
        sa.Column("id_usuario_resposta", sa.Integer, sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("respondido_em", sa.DateTime, nullable=True),
        sa.Column("resolvido_em", sa.DateTime, nullable=True),
        sa.Column("criado_em", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        schema=S,
    )
    op.create_index(
        "ix_pedido_ajuste_tenant_debito", "pedido_ajuste",
        ["tenant_id", "id_debito"], schema=S,
    )
    op.create_index(
        "ix_pedido_ajuste_tenant_situacao_transacao", "pedido_ajuste",
        ["tenant_id", "situacao", "transacao_responsavel"], schema=S,
    )
    _rls("pedido_ajuste")

    # ------------------------------------------------------------- debito_versao
    op.create_table(
        "debito_versao",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_debito", sa.Integer, sa.ForeignKey("pagamentos.debito.id"), nullable=False),
        sa.Column("versao", sa.Integer, nullable=False),  # a versão CONGELADA (anterior)
        sa.Column("dados", postgresql.JSONB, nullable=False),  # snapshot dos campos materiais
        sa.Column(
            "id_pedido_ajuste", sa.Integer,
            sa.ForeignKey("pagamentos.pedido_ajuste.id"), nullable=True,
        ),
        sa.Column("motivo", sa.String(255), nullable=False),
        sa.Column("id_usuario", sa.Integer, sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        schema=S,
    )
    op.create_unique_constraint(
        "uq_debito_versao_tenant_debito_versao", "debito_versao",
        ["tenant_id", "id_debito", "versao"], schema=S,
    )
    _rls("debito_versao")

    # -------------------------------------------------------------- anexo_debito
    op.create_table(
        "anexo_debito",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_debito", sa.Integer, sa.ForeignKey("pagamentos.debito.id"), nullable=False),
        sa.Column("id_anexo", sa.Integer, sa.ForeignKey("protocolos.anexo.id"), nullable=False),
        sa.Column("id_usuario", sa.Integer, sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("versao_debito", sa.Integer, nullable=False),
        sa.Column(
            "id_pedido_ajuste", sa.Integer,
            sa.ForeignKey("pagamentos.pedido_ajuste.id"), nullable=True,
        ),
        sa.Column("criado_em", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("excluido", sa.Boolean, nullable=False, server_default=sa.text("false")),
        schema=S,
    )
    op.create_index(
        "ix_anexo_debito_tenant_debito", "anexo_debito",
        ["tenant_id", "id_debito"], schema=S,
    )
    _rls("anexo_debito")

    # ------------------------------------------------------- debito_historico
    for col in (
        sa.Column("versao_debito", sa.Integer, nullable=True),
        sa.Column("situacao_tramitacao_anterior", sa.String(30), nullable=True),
        sa.Column("situacao_tramitacao_nova", sa.String(30), nullable=True),
        sa.Column("situacao_fila_anterior", sa.String(30), nullable=True),
        sa.Column("situacao_fila_nova", sa.String(30), nullable=True),
        sa.Column("situacao_pagamento_anterior", sa.String(20), nullable=True),
        sa.Column("situacao_pagamento_nova", sa.String(20), nullable=True),
    ):
        op.add_column("debito_historico", col, schema=S)

    # ------------------------------------------------------------- backfill
    op.execute("""
        INSERT INTO pagamentos.pedido_ajuste
            (tenant_id, id_debito, versao_debito, etapa_solicitante, id_usuario_solicitante,
             motivo, descricao, transacao_responsavel, tipo, situacao, criado_em)
        SELECT d.tenant_id, d.id, d.versao,
               CASE d.situacao_tramitacao
                    WHEN 'AJUSTE_GESTOR' THEN 'GESTOR'
                    WHEN 'AJUSTE_VALIDACAO' THEN 'VALIDACAO'
                    WHEN 'AJUSTE_AUTORIDADE' THEN 'AUTORIDADE' END,
               h.id_usuario,
               COALESCE(left(h.justificativa, 255), 'Ajuste solicitado antes da F2'),
               COALESCE(h.justificativa, 'Pedido sintético criado pela migration 0105 (F2).'),
               'pagamento_solicitar', 'NAO_MATERIAL', 'ABERTO', COALESCE(h.criado_em, now())
        FROM pagamentos.debito d
        LEFT JOIN LATERAL (
            SELECT id_usuario, justificativa, criado_em
            FROM pagamentos.debito_historico h
            WHERE h.id_debito = d.id AND h.tenant_id = d.tenant_id
              AND h.acao IN ('AJUSTE_SOLICITADO', 'DEVOLVIDO', 'SUSPENSO')
            ORDER BY h.criado_em DESC, h.id DESC LIMIT 1
        ) h ON true
        WHERE d.situacao_tramitacao IN ('AJUSTE_GESTOR', 'AJUSTE_VALIDACAO', 'AJUSTE_AUTORIDADE')
          AND d.excluido = false
    """)


def downgrade() -> None:
    for col in (
        "situacao_pagamento_nova",
        "situacao_pagamento_anterior",
        "situacao_fila_nova",
        "situacao_fila_anterior",
        "situacao_tramitacao_nova",
        "situacao_tramitacao_anterior",
        "versao_debito",
    ):
        op.drop_column("debito_historico", col, schema=S)

    op.drop_table("anexo_debito", schema=S)
    op.drop_table("debito_versao", schema=S)
    op.drop_table("pedido_ajuste", schema=S)
