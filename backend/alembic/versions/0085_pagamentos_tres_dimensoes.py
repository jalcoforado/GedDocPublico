"""Pagamentos F1 — as três dimensões de situação, unidade e versionamento.

Revision ID: 0085
Revises: 0084
Create Date: 2026-08-06

Spec: `docs/superpowers/specs/2026-08-06-pagamentos-fluxo-design.md` §4.

Só ADD COLUMN em tabela existente — **RLS e grants são herdados**, não se
repete o boilerplate. Não há tabela nova nesta fatia.

Três coisas merecem atenção de quem revisar:

1. **`id_unidade` nasce nullable e termina NOT NULL na MESMA migration.** O
   backfill roda no meio. Deixar a janela aberta entre duas migrations criaria
   um intervalo em que o código novo grava NULL e o `SET NOT NULL` da migration
   seguinte falha com dado em produção.

2. **`categoria` de contrato NÃO vira NOT NULL.** Fica nullable com default
   'SERVICOS' para linhas existentes. Obrigar o ente a classificar 100% dos
   contratos no dia do deploy trava o módulo inteiro; a tela de contratos
   alerta e o operador classifica ao longo do tempo.

3. **`status` continua existindo e continua correto.** Ele passa a ser derivado
   das três dimensões (`services/pagamentos_estados.status_legado`), e todos os
   consumidores que ainda o leem seguem funcionando. A coluna morre na F5.

O `downgrade` recalcula nada: como `status` nunca deixou de ser mantido, basta
derrubar as colunas novas. É por isso que manter a coluna legada durante F1–F4
não é só conservadorismo — é o que torna esta migration reversível de verdade.

Divergência em relação ao plano original (conferida contra o schema real antes
de escrever): `utils.grupo_transacao` tem `tenant_id NOT NULL` (com RLS
FORCE) — o INSERT...SELECT da concessão de `pagamento_gerir` precisa carregar
`gt.tenant_id`, senão a linha falha a constraint. Os demais nomes do plano
(`utils.usuario.id_unidade_trabalho`, `utils.grupo_transacao.id_grupo/
id_transacao/inserir/atualizar/excluir`, `utils.unidade_trabalho`,
`utils.transacao.transacao/codigo`) bateram com o schema real.

Achados da revisão de qualidade (corrigidos nesta versão, sem tocar nas duas
decisões do Jorge — `DELETE` da linha do id_unidade e os testes vermelhos que
a Tarefa 3 fecha):

- As três passadas de backfill de `id_unidade` filtram tenant explicitamente
  (`c.tenant_id = d.tenant_id` / `u.tenant_id = d.tenant_id`) — a FK do
  Postgres não filtra por tenant, e sem o predicado um contrato/usuário de
  outro tenant gravaria a unidade errada em silêncio.
- Pré-checagem em `DO $$...$$` antes do `SET NOT NULL` de `id_unidade`:
  tenant sem nenhuma `unidade_trabalho` ativa deixaria débito vivo sem
  unidade, e o `SET NOT NULL` cru estouraria como o container morrendo no
  start (o entrypoint roda `alembic upgrade head` com `set -e`). Agora falha
  com `RAISE EXCEPTION` dizendo quantos débitos e em quais tenants.
- `situacao_tramitacao`, `situacao_fila` e `situacao_pagamento` ganharam
  CHECK de domínio (`ck_debito_situacao_*`), com os valores exatos de
  `TRAMITACAO`/`FILA`/`PAGAMENTO` de `app.services.pagamentos_estados` —
  `status` e `categoria` já tinham a mesma rede nesta migration.
- A cópia de concessão `pagamento_encaminhar` → `pagamento_gerir` agora exige
  `gt.excluido = false`: sem isso, uma concessão revogada seria copiada ATIVA.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

import sqlalchemy as sa
from alembic import op

from app.services import pagamentos_estados as est

revision: str = "0085"
down_revision: str | Sequence[str] | None = "0084"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "pagamentos"

# Espelha o §4.5 da spec e o MAPA de tests/test_pagamentos_migration_0085.py.
MAPA_BACKFILL: dict[str, tuple[str, str, str]] = {
    "RASCUNHO":               ("RASCUNHO", "NAO_REGISTRADA", "NAO_INICIADA"),
    "EM_VALIDACAO":           ("AGUARDANDO_VALIDACAO", "NAO_REGISTRADA", "NAO_INICIADA"),
    "DEVOLVIDO":              ("AJUSTE_VALIDACAO", "NAO_REGISTRADA", "NAO_INICIADA"),
    "VALIDADO":               ("AGUARDANDO_AUTORIDADE", "REGISTRADA", "NAO_INICIADA"),
    "ENVIADO_SECRETARIO":     ("AGUARDANDO_AUTORIDADE", "REGISTRADA", "NAO_INICIADA"),
    "AGUARDANDO_AUTORIZACAO": ("AGUARDANDO_AUTORIDADE", "REGISTRADA", "NAO_INICIADA"),
    "AUTORIZADO":             ("AUTORIZADA", "ELEGIVEL", "NAO_INICIADA"),
    "ENVIADO_TESOURARIA":     ("AUTORIZADA", "ELEGIVEL", "PROGRAMADA"),
    "EM_PROCESSAMENTO":       ("AUTORIZADA", "ELEGIVEL", "EM_PROCESSAMENTO"),
    "PAGO_PARCIAL":           ("AUTORIZADA", "ELEGIVEL", "PAGA_PARCIAL"),
    "PAGO":                   ("AUTORIZADA", "CONCLUIDA", "PAGA"),
    "CONCILIADO":             ("AUTORIZADA", "CONCLUIDA", "PAGA"),
    "REJEITADO":              ("REJEITADA_GESTOR", "NAO_REGISTRADA", "NAO_INICIADA"),
    "SUSPENSO":               ("AJUSTE_VALIDACAO", "BLOQUEADA", "NAO_INICIADA"),
    "CANCELADO":              ("CANCELADA", "RETIRADA", "CANCELADA"),
    "ESTORNADO":              ("AUTORIZADA", "ELEGIVEL", "ESTORNADA"),
}


def _lista_sql(valores: Iterable[str]) -> str:
    """Literal SQL `'A','B','C'` a partir de um iterável, ordenado p/ diff estável."""
    return ",".join(f"'{v}'" for v in sorted(valores))


def upgrade() -> None:
    # ---------------------------------------------- 1. colunas das dimensões
    op.add_column("debito", sa.Column("situacao_tramitacao", sa.String(30),
                  nullable=True), schema=S)
    op.add_column("debito", sa.Column("situacao_fila", sa.String(30),
                  nullable=True), schema=S)
    op.add_column("debito", sa.Column("situacao_pagamento", sa.String(20),
                  nullable=True), schema=S)

    for legado, (tram, fila, pag) in MAPA_BACKFILL.items():
        op.execute(
            f"UPDATE {S}.debito SET situacao_tramitacao = '{tram}', "
            f"situacao_fila = '{fila}', situacao_pagamento = '{pag}' "
            f"WHERE status = '{legado}'"
        )
    # Rede de segurança: linha com status fora do enum (dado sujo do legado)
    # vira rascunho em vez de derrubar o SET NOT NULL abaixo.
    op.execute(
        f"UPDATE {S}.debito SET situacao_tramitacao = 'RASCUNHO', "
        f"situacao_fila = 'NAO_REGISTRADA', situacao_pagamento = 'NAO_INICIADA' "
        f"WHERE situacao_tramitacao IS NULL"
    )

    for coluna in ("situacao_tramitacao", "situacao_fila", "situacao_pagamento"):
        op.alter_column("debito", coluna, nullable=False, schema=S)

    # CHECK de domínio — `status` tem `ck_debito_status` e `categoria` ganha
    # `ck_contrato_categoria` nesta mesma migration; as três dimensões novas
    # não podiam ficar sem a mesma rede. Valores vêm de
    # `app.services.pagamentos_estados` — mudou lá, a próxima migration ajusta.
    op.create_check_constraint(
        "ck_debito_situacao_tramitacao", "debito",
        f"situacao_tramitacao IN ({_lista_sql(est.TRAMITACAO)})", schema=S)
    op.create_check_constraint(
        "ck_debito_situacao_fila", "debito",
        f"situacao_fila IN ({_lista_sql(est.FILA)})", schema=S)
    op.create_check_constraint(
        "ck_debito_situacao_pagamento", "debito",
        f"situacao_pagamento IN ({_lista_sql(est.PAGAMENTO)})", schema=S)

    # ------------------------------------------------------- 2. id_unidade
    op.add_column("debito", sa.Column("id_unidade", sa.Integer(), nullable=True), schema=S)
    op.create_foreign_key("fk_debito_unidade", "debito", "unidade_trabalho",
                          ["id_unidade"], ["id"], source_schema=S,
                          referent_schema="utils")
    # Backfill em três passadas: contrato quando há, unidade do solicitante
    # (utils.usuario.id_unidade_trabalho) quando não, e como último recurso a
    # menor unidade do tenant. Volume medido em 2026-08-07 (banco de
    # homologação, 544 débitos não excluídos): 6 via contrato, 536 via
    # usuário, 2 via último recurso (tenants 151 e 152, cujos solicitantes não
    # tinham unidade cadastrada).
    # As três passadas filtram tenant explicitamente — a FK do Postgres não
    # filtra por tenant, e sem o predicado um `contrato` ou `usuario` de outro
    # tenant gravaria a unidade errada em silêncio nesta coluna, que vira
    # chave da fila cronológica na F3.
    op.execute(f"""
        UPDATE {S}.debito d SET id_unidade = c.id_unidade
        FROM {S}.contrato c
        WHERE d.id_contrato = c.id AND d.id_unidade IS NULL
          AND c.tenant_id = d.tenant_id
    """)
    op.execute(f"""
        UPDATE {S}.debito d SET id_unidade = u.id_unidade_trabalho
        FROM utils.usuario u
        WHERE d.id_usuario_solicitante = u.id AND d.id_unidade IS NULL
          AND u.id_unidade_trabalho IS NOT NULL
          AND u.tenant_id = d.tenant_id
    """)
    # Último recurso: a menor unidade do tenant. Débito sem unidade nenhuma
    # tornaria a coluna inviável como NOT NULL e quebraria a chave da fila na F3.
    # (já filtrava tenant — `u.tenant_id = d.tenant_id` — mantido explícito.)
    op.execute(f"""
        UPDATE {S}.debito d SET id_unidade = (
            SELECT MIN(u.id) FROM utils.unidade_trabalho u
            WHERE u.tenant_id = d.tenant_id AND u.excluido = false
        ) WHERE d.id_unidade IS NULL
    """)
    op.execute(f"DELETE FROM {S}.debito WHERE id_unidade IS NULL AND excluido = true")

    # Pré-checagem: se algum débito VIVO (excluido = false) escapou das três
    # passadas — típico de tenant sem nenhuma unidade_trabalho ativa —, o
    # SET NOT NULL abaixo estouraria com um NotNullViolation cru. Como o
    # entrypoint roda `alembic upgrade head` com `set -e`, isso apareceria só
    # como container morrendo no start. Falha aqui, com diagnóstico.
    op.execute(f"""
        DO $$
        DECLARE
            cnt integer;
            tenants text;
        BEGIN
            SELECT count(*) INTO cnt
            FROM {S}.debito
            WHERE id_unidade IS NULL AND excluido = false;

            IF cnt > 0 THEN
                SELECT string_agg(DISTINCT tenant_id::text, ', ' ORDER BY tenant_id::text)
                  INTO tenants
                  FROM {S}.debito
                 WHERE id_unidade IS NULL AND excluido = false;
                RAISE EXCEPTION 'migration 0085: % débito(s) vivo(s) ficaram sem id_unidade após o backfill, nos tenants [%]. Esses tenants não têm nenhuma utils.unidade_trabalho ativa (excluido = false) — cadastre ao menos uma unidade nesses tenants antes de aplicar esta migration.', cnt, tenants;
            END IF;
        END $$;
    """)

    op.alter_column("debito", "id_unidade", nullable=False, schema=S)
    op.create_index("ix_debito_unidade", "debito", ["tenant_id", "id_unidade"], schema=S)

    # ------------------------------- 3. versionamento e concorrência
    op.add_column("debito", sa.Column("versao", sa.Integer(), nullable=False,
                  server_default="1"), schema=S)
    op.add_column("debito", sa.Column("lock_version", sa.Integer(), nullable=False,
                  server_default="0"), schema=S)

    # ------------------------------- 4. quem decidiu em cada etapa
    op.add_column("debito", sa.Column("id_gestor_decisor", sa.Integer(), nullable=True), schema=S)
    op.add_column("debito", sa.Column("id_validador", sa.Integer(), nullable=True), schema=S)
    op.create_foreign_key("fk_debito_gestor", "debito", "usuario",
                          ["id_gestor_decisor"], ["id"], source_schema=S,
                          referent_schema="utils")
    op.create_foreign_key("fk_debito_validador", "debito", "usuario",
                          ["id_validador"], ["id"], source_schema=S,
                          referent_schema="utils")
    # Backfill do validador a partir da trilha — a informação já existe.
    op.execute(f"""
        UPDATE {S}.debito d SET id_validador = h.id_usuario
        FROM (
            SELECT DISTINCT ON (id_debito) id_debito, id_usuario
            FROM {S}.debito_historico WHERE acao = 'VALIDADO'
            ORDER BY id_debito, criado_em DESC
        ) h WHERE h.id_debito = d.id
    """)

    # --------------------------------------- 5. categoria do contrato
    op.add_column("contrato", sa.Column("categoria", sa.String(20), nullable=True), schema=S)
    op.execute(f"UPDATE {S}.contrato SET categoria = 'SERVICOS' WHERE categoria IS NULL")
    op.create_check_constraint(
        "ck_contrato_categoria", "contrato",
        "categoria IS NULL OR categoria IN ('BENS','LOCACOES','SERVICOS','OBRAS')",
        schema=S)

    # ----------------------------- 6. transação do Gestor da Pasta
    op.execute("""
        INSERT INTO utils.transacao (transacao, codigo)
        SELECT 'Gestão da pasta (pagamentos)', 'pagamento_gerir'
        WHERE NOT EXISTS (
            SELECT 1 FROM utils.transacao WHERE codigo = 'pagamento_gerir'
        )
    """)
    # Quem hoje encaminha é quem mais se aproxima do gestor. Sem esta concessão
    # a etapa nova nasce sem ninguém que a exerça, e o fluxo trava na primeira
    # solicitação enviada.
    #
    # Divergência frente ao plano: `utils.grupo_transacao.tenant_id` é
    # NOT NULL (a tabela tem RLS FORCE), então o INSERT precisa carregar
    # `gt.tenant_id` explicitamente — o plano original omitia essa coluna.
    # `gt.excluido = false` é obrigatório: sem ele, um grupo cuja concessão de
    # `pagamento_encaminhar` foi revogada (soft-delete, `excluido = true`)
    # ganharia `pagamento_gerir` ATIVO — a cópia arrastaria uma permissão que
    # o tenant já havia retirado. `services/permissoes.py` filtra
    # `excluido.is_(False)` na leitura; a concessão nova tem de nascer coerente.
    op.execute("""
        INSERT INTO utils.grupo_transacao (id_grupo, id_transacao, inserir, atualizar, excluir, tenant_id)
        SELECT gt.id_grupo, novo.id, gt.inserir, gt.atualizar, gt.excluir, gt.tenant_id
        FROM utils.grupo_transacao gt
        JOIN utils.transacao antiga ON antiga.id = gt.id_transacao
                                   AND antiga.codigo = 'pagamento_encaminhar'
        CROSS JOIN (SELECT id FROM utils.transacao WHERE codigo = 'pagamento_gerir') novo
        WHERE gt.excluido = false
          AND NOT EXISTS (
            SELECT 1 FROM utils.grupo_transacao x
            WHERE x.id_grupo = gt.id_grupo AND x.id_transacao = novo.id
        )
    """)


def downgrade() -> None:
    op.drop_constraint("ck_contrato_categoria", "contrato", schema=S, type_="check")
    op.drop_column("contrato", "categoria", schema=S)
    op.drop_constraint("fk_debito_validador", "debito", schema=S, type_="foreignkey")
    op.drop_constraint("fk_debito_gestor", "debito", schema=S, type_="foreignkey")
    op.drop_column("debito", "id_validador", schema=S)
    op.drop_column("debito", "id_gestor_decisor", schema=S)
    op.drop_column("debito", "lock_version", schema=S)
    op.drop_column("debito", "versao", schema=S)
    op.drop_index("ix_debito_unidade", table_name="debito", schema=S)
    op.drop_constraint("fk_debito_unidade", "debito", schema=S, type_="foreignkey")
    op.drop_column("debito", "id_unidade", schema=S)
    op.drop_constraint("ck_debito_situacao_pagamento", "debito", schema=S, type_="check")
    op.drop_constraint("ck_debito_situacao_fila", "debito", schema=S, type_="check")
    op.drop_constraint("ck_debito_situacao_tramitacao", "debito", schema=S, type_="check")
    op.drop_column("debito", "situacao_pagamento", schema=S)
    op.drop_column("debito", "situacao_fila", schema=S)
    op.drop_column("debito", "situacao_tramitacao", schema=S)
    # `pagamento_gerir` e suas concessões NÃO são removidas: apagar concessão
    # de permissão num downgrade é destrutivo e irreversível na prática.
