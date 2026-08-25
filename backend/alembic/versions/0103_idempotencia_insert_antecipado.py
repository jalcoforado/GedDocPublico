"""Pagamentos C2.3 — Task 7: idempotência com insert antecipado + busca por prefixo sob RLS.

Revision ID: 0103
Revises: 0102
Create Date: 2026-08-24

Duas mudanças, nenhuma tabela nova:

1. `pagamentos.idempotencia.status_code`/`corpo_resposta` viram NULLABLE.

   O algoritmo de `executar_idempotente` (`app/services/pagamentos_idempotencia.py`)
   insere a linha ANTES de rodar a operação real — um placeholder com
   `status_code`/`corpo_resposta` NULL, protegido pelo unique
   `(tenant_id, id_sistema, chave)` (migration 0102). Duas requisições
   concorrentes com a MESMA chave colidem nesse INSERT em vez de duplicar a
   execução: a perdedora relê a linha do vencedor. A 0102 criou as colunas
   `NOT NULL` porque na hora não havia executor nenhum ainda — esta migration
   é a "sua", como o brief da Task 7 registra.

2. Policy `tenant_isolation_select` de `pagamentos.sistema_integrado` ganha
   `OR GUC IS NULL`.

   Precedente conferido (item 3 do review da Task 6): `aprimora_py.tenant`
   NÃO tem RLS — é o catálogo global de tenants, lido pelo `TenantMiddleware`
   por `slug` ANTES de qualquer tenant existir na sessão; não serve de molde
   direto porque a tabela nem tem coluna `tenant_id`. `pagamentos.sistema_integrado`
   é diferente: TEM `tenant_id` e RLS (0102), mas a busca de
   `get_current_sistema_integrado` (por `prefixo`, unique GLOBAL, ver 0102)
   roda ANTES de o tenant ser conhecido — é a própria linha encontrada que
   revela o tenant, não o inverso. A sessão usada nessa busca é a de `get_db`
   comum: só carrega `session.info["tenant_id"]` se `request.state.tenant_id`
   já existir (host resolveu algum tenant); para uma chamada M2M cujo Host não
   resolve tenant nenhum, a GUC fica NULL na transação daquele SELECT.

   Sob `ged_user` (BYPASSRLS, F-12) isso nunca deu problema porque a RLS não
   filtra nada em produção hoje. Sob `aprimora_app` (papel-alvo do
   SEC-RLS-ROLLOUT) a policy ANTIGA (`tenant_id = GUC`) devolveria ZERO linhas
   quando a GUC está NULL — `tenant_id = NULL` nunca é verdadeiro — e a busca
   por prefixo, que É o desenho (unique global, ver 0102), deixaria de
   funcionar exatamente no caso em que ela precisa funcionar. A policy nova
   permite ver QUALQUER tenant quando a sessão não tem tenant fixado (GUC
   NULL) e continua restringindo ao tenant da sessão quando ele existe — não é
   um afrouxamento geral: é reconhecer, na política de leitura, o mesmo "unique
   global" que a 0102 já documentou na estrutura da tabela.

   A policy de ESCRITA (`tenant_isolation_modify`) não muda: `INSERT`/`UPDATE`/
   `DELETE` continuam exigindo `tenant_id = GUC` — GUC NULL nunca satisfaz essa
   comparação —, então nada passa a escrever `sistema_integrado` sem tenant
   conhecido. Só a leitura pré-autenticação fica mais permissiva, e só quando a
   sessão genuinamente não sabe qual tenant é.

   Prova disto: `tests/test_pagamentos_c2_api.py` — seção "correções Task 7",
   teste que roda sob `app_session` (papel `aprimora_app`, NOBYPASSRLS) e
   autentica por prefixo com a GUC NULL, depois consulta um débito do próprio
   tenant e confere 404 cross-tenant — o roteiro de
   `tests/test_rls_papeis_minimos.py`.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0103"
down_revision: str | Sequence[str] | None = "0102"
branch_labels = None
depends_on = None

S = "pagamentos"
GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {S}.idempotencia ALTER COLUMN status_code DROP NOT NULL")
    op.execute(f"ALTER TABLE {S}.idempotencia ALTER COLUMN corpo_resposta DROP NOT NULL")

    op.execute(f"DROP POLICY tenant_isolation_select ON {S}.sistema_integrado")
    op.execute(
        f"CREATE POLICY tenant_isolation_select ON {S}.sistema_integrado "
        f"FOR SELECT USING (tenant_id = {GUC} OR {GUC} IS NULL)"
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY tenant_isolation_select ON {S}.sistema_integrado")
    op.execute(
        f"CREATE POLICY tenant_isolation_select ON {S}.sistema_integrado "
        f"FOR SELECT USING (tenant_id = {GUC})"
    )

    op.execute(f"ALTER TABLE {S}.idempotencia ALTER COLUMN corpo_resposta SET NOT NULL")
    op.execute(f"ALTER TABLE {S}.idempotencia ALTER COLUMN status_code SET NOT NULL")
