# Inventário do bypass de RLS no runtime (achado F-12)

**PR:** `SEC-RLS-00A` · **Data da medição:** 2026-08-01 · **Estado:** caracterização, sem correção.

Este documento **mede**; não conserta. Ele existe porque a ordem acordada em
[ADR-016 §9.1](../adr/ADR-016-platform-operator-identity.md) é *caracterizar, depois conter*: o
runtime opera com bypass há tempo suficiente para que caminhos hoje funcionais dependam dele sem
registro, e trocar a credencial antes do inventário converteria um achado de segurança conhecido
num incidente de disponibilidade desconhecido.

O achado: **a aplicação conecta no Postgres como `ged_user`, que é `SUPERUSER` e `BYPASSRLS`.** A
RLS que o invariante 10 do spec chama de "última barreira de isolamento de tenant" está **inerte no
runtime**; o isolamento hoje depende inteiramente do filtro aplicacional (`tenant_filter` +
disciplina de service).

Prova executável: `backend/tests/test_rls_bypass_caracterizacao.py`.

## Ambiente da medição

| Item | Valor |
|---|---|
| Banco | `ged_saas_db` em `aprimora-py-db` |
| Versão | PostgreSQL 17.10 (aarch64, Alpine) |
| Papel do runtime | `ged_user` (`docker-compose.yml:4`) |
| Papel alternativo já existente | `aprimora_app` (usado só pelos testes) |
| Branch | `sec-rls/00a-caracterizacao` |

Todas as consultas abaixo são reexecutáveis com:

```bash
docker exec aprimora-py-db psql -U ged_user -d ged_saas_db -P pager=off -c "<consulta>"
```

---

## 1. Papéis (`pg_roles`)

```sql
SELECT rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb,
       rolcanlogin, rolreplication, rolinherit
  FROM pg_roles
 WHERE rolname NOT LIKE 'pg\_%'
 ORDER BY rolname;
```

| rolname | super | bypassrls | createrole | createdb | canlogin | replication | inherit |
|---|---|---|---|---|---|---|---|
| `aprimora_app` | f | f | f | f | t | f | t |
| `ged_user` | **t** | **t** | t | t | t | t | t |

Existem **dois** papéis com login. Todo consumidor de banco do projeto — API, worker, beat,
migrations, CLIs, seeds — usa o mesmo: `ged_user`. `aprimora_app` só aparece em
`backend/tests/conftest.py`.

`DATABASE_URL` apontando para `ged_user` está versionado em:

- `docker-compose.yml:4` (anchor `x-backend-env`, propaga para `backend`, `worker` e `beat`)
- `backend/.env.example:2`
- `.github/workflows/backend-tests.yml:54`
- `.github/workflows/e2e-assinatura.yml:114` e `:125`
- default de `Settings.database_url` em `backend/app/config.py:10`

A VPS de homologação sobe pelo mesmo `docker-compose.yml` (`scripts/deploy.sh`), então o achado
vale lá também.

> `docker-compose.dev.yml` não redefine `DATABASE_URL` — herda o anchor.

## 2. RLS por tabela (`pg_class`)

```sql
SELECT n.nspname, count(*) FILTER (WHERE c.relrowsecurity) AS com_rls, count(*) AS total
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind = 'r' AND n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
 GROUP BY 1 ORDER BY 1;
```

| schema | com RLS | total |
|---|---|---|
| `agendamento` | 0 | 2 |
| `aprimora_py` | 11 | 16 |
| `despesas` | 0 | 1 |
| `empresasimples` | 0 | 1 |
| `frota` | 8 | 8 |
| `pagamentos` | 22 | 22 |
| `protocolos` | 26 | 86 |
| `sistema_chamados` | 0 | 1 |
| `transporte_regulado` | 11 | 11 |
| `utils` | 9 | 86 |
| **total** | **87** | **234** |

Das 87 tabelas com RLS, **79** têm `FORCE`. Todas as 234 tabelas do banco pertencem a `ged_user`
(`pg_get_userbyid(relowner)`), o que torna o `FORCE` decisivo: sem ele, o dono contorna as policies
mesmo sem `BYPASSRLS`.

### 2.1 Divergência — tabelas com `tenant_id` sem RLS habilitada **e** forçada

```sql
SELECT n.nspname || '.' || c.relname AS tabela, c.relrowsecurity, c.relforcerowsecurity
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN information_schema.columns col
    ON col.table_schema = n.nspname AND col.table_name = c.relname
   AND col.column_name = 'tenant_id'
 WHERE c.relkind = 'r' AND NOT (c.relrowsecurity AND c.relforcerowsecurity)
 ORDER BY 1;
```

| tabela | rls | force | avaliação |
|---|---|---|---|
| `aprimora_py.tenant_modulo` | f | f | **Deliberado.** Tabela de plataforma, escrita pelo platform admin operando sobre outros tenants. Registrado no CLAUDE.md e na migration 0073. Está na allowlist do teste. Sem RLS, o `GRANT` é a única barreira — e desde a `0079` (`SEC-RLS-00C`) `aprimora_app` só tem `SELECT` aqui. |
| `transporte_regulado.alvara` | t | **f** | Divergência |
| `transporte_regulado.alvara_auditoria` | t | **f** | Divergência |
| `transporte_regulado.alvara_documento` | t | **f** | Divergência |
| `transporte_regulado.alvara_responsavel` | t | **f** | Divergência |
| `transporte_regulado.alvara_veiculo` | t | **f** | Divergência |
| `transporte_regulado.veiculo_avaliacao` | t | **f** | Divergência |
| `transporte_regulado.veiculo_documento` | t | **f** | Divergência |
| `transporte_regulado.veiculo_vistoria` | t | **f** | Divergência |

Nenhuma outra tabela do banco tem coluna `tenant_id` sem RLS habilitada e forçada — em particular,
`protocolos.*`, `utils.*`, `pagamentos.*`, `frota.*` e o resto de `aprimora_py.*` estão completos.

`aprimora_py.tenant` e `aprimora_py.modulo`/`modulo_transacao` não têm RLS **e não têm `tenant_id`**
— são catálogo global e tabela de plataforma; coerente.

**Por que as 8 de `transporte_regulado` importam:** hoje nada acontece, porque o dono das tabelas é
`ged_user` e o runtime é `ged_user`. No dia em que `SEC-RLS-00B` fizer o runtime ser um papel
não-dono, elas passam a ser filtradas — e nesse instante o problema da seção 3.1 estoura.

As nove linhas desta tabela são exatamente a `ALLOWLIST_SEM_RLS_FORCADA` de
`backend/tests/test_rls_bypass_caracterizacao.py`, e a guarda estrutural cobre os três schemas
(`aprimora_py`, `frota`, `transporte_regulado`). Conforme o `SEC-RLS-00B` aplicar `FORCE`, a
allowlist **tem** de encolher: o teste reprova entrada que já ganhou RLS habilitada e forçada. Só
`aprimora_py.tenant_modulo` é permanente.

## 3. Policies (`pg_policies`)

182 policies em 87 tabelas. **Nenhuma tabela tem RLS habilitada sem policy** (verificado — o caso
"RLS ligada e nenhuma policy", que nega tudo, não ocorre).

```sql
SELECT schemaname, count(*) FROM pg_policies GROUP BY 1 ORDER BY 1;
```

| schema | policies |
|---|---|
| `aprimora_py` | 22 |
| `frota` | 16 |
| `pagamentos` | 44 |
| `protocolos` | 52 |
| `transporte_regulado` | 30 |
| `utils` | 18 |

Todas as policies são para `roles = {public}` — nenhuma é restrita a papel específico. Isso
simplifica `SEC-RLS-00B`: não há policy que já dependa de um papel nominal.

### 3.1 Divergência crítica — 20 policies usam uma GUC que a aplicação nunca seta

```sql
SELECT schemaname || '.' || tablename AS tabela, policyname, qual, with_check
  FROM pg_policies
 WHERE (coalesce(qual,'') || coalesce(with_check,'')) LIKE '%current_setting%'
   AND (coalesce(qual,'') || coalesce(with_check,'')) NOT LIKE '%true%'
 ORDER BY 1, 2;
```

Resultado: **20 policies**, todas em `transporte_regulado`, nas tabelas `alvara_documento`,
`alvara_responsavel`, `veiculo_avaliacao`, `veiculo_documento` e `veiculo_vistoria`. Elas dizem:

```sql
tenant_id = current_setting('app.current_tenant_id')::integer
```

São **dois** defeitos numa expressão só:

1. **A GUC está errada.** A aplicação seta `app.tenant_id` (listener `after_begin` em
   `backend/app/database.py:46`). `app.current_tenant_id` **nunca** é setada em lugar nenhum do
   repositório — só existe nessas migrations.
2. **Falta o segundo argumento `true`.** Sem ele, `current_setting` de uma GUC inexistente **levanta
   erro** em vez de devolver `NULL`. A policy não "nega"; ela **quebra a consulta**.

As outras 162 policies usam a forma padrão e tolerante:
`tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int`.

Reprodução da consequência, hoje, neste banco:

```console
$ docker exec -e PGPASSWORD=... aprimora-py-db psql -U aprimora_app -h localhost -d ged_saas_db \
    -c "SET app.tenant_id = '1'; SELECT count(*) FROM transporte_regulado.veiculo_documento;"
SET
ERROR:  unrecognized configuration parameter "app.current_tenant_id"
```

Origem: migrations `0050`, `0051`, `0053`, `0056`, `0057`. A migration `0061`
(`fix_rls_alvara_tenant_id`) corrigiu **apenas** `transporte_regulado.alvara`; as demais ficaram.

## 4. Grants de tabela (`information_schema.role_table_grants`)

```sql
WITH t AS (
  SELECT c.oid, n.nspname || '.' || c.relname AS nome
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE c.relkind = 'r'
     AND n.nspname IN ('aprimora_py','frota','pagamentos','transporte_regulado','protocolos','utils')
  OFFSET 0)
SELECT nome,
       has_table_privilege('aprimora_app', oid, 'SELECT') s,
       has_table_privilege('aprimora_app', oid, 'INSERT') i,
       has_table_privilege('aprimora_app', oid, 'UPDATE') u,
       has_table_privilege('aprimora_app', oid, 'DELETE') d
  FROM t
 WHERE NOT (has_table_privilege('aprimora_app', oid, 'SELECT')
        AND has_table_privilege('aprimora_app', oid, 'INSERT')
        AND has_table_privilege('aprimora_app', oid, 'UPDATE')
        AND has_table_privilege('aprimora_app', oid, 'DELETE'))
 ORDER BY 1;
```

> O `OFFSET 0` não é enfeite: sem a barreira de otimização, o planejador avalia
> `has_*_privilege` antes do filtro `relkind` e a consulta morre com
> `ERROR: "<índice>_pkey" is not a sequence`.

| tabela | SELECT | INSERT | UPDATE | DELETE | avaliação |
|---|---|---|---|---|---|
| `aprimora_py.modulo` | t | f | f | f | Catálogo global — leitura basta para o runtime, mas o `seed_bootstrap` **escreve** aqui |
| `aprimora_py.modulo_transacao` | t | f | f | f | Idem |
| `transporte_regulado.alvara` | **f** | f | f | f | Divergência: RLS ligada e **nenhum** grant |
| `transporte_regulado.alvara_auditoria` | t | **f** | f | f | Divergência: trilha de auditoria sem INSERT |
| `transporte_regulado.alvara_documento` | **f** | f | f | f | Divergência |
| `transporte_regulado.alvara_responsavel` | **f** | f | f | f | Divergência |

Os seis schemas somam **229** tabelas; com as 6 divergências acima, as demais **223** têm
`SELECT, INSERT, UPDATE, DELETE` para `aprimora_app`.

Reprodução:

```console
$ psql -U aprimora_app ... -c "SET app.tenant_id='1'; SELECT count(*) FROM transporte_regulado.alvara;"
SET
ERROR:  permission denied for table alvara
```

Causa provável: `scripts/bootstrap-db.sh:46-48` e o passo equivalente do
`.github/workflows/backend-tests.yml:179-181` concedem em
`protocolos, utils, aprimora_py, public` (+ `pagamentos, frota` no CI) e **não** em
`transporte_regulado`; as migrations de transporte, por sua vez, não trouxeram o `GRANT` do
boilerplate.

### 4.1 Privilégios de schema

```sql
SELECT nspname,
       has_schema_privilege('aprimora_app', oid, 'USAGE') AS usage,
       has_schema_privilege('aprimora_app', oid, 'CREATE') AS create
  FROM pg_namespace
 WHERE nspname NOT LIKE 'pg\_%' AND nspname <> 'information_schema' ORDER BY 1;
```

`USAGE = true` em `aprimora_py`, `frota`, `pagamentos`, `protocolos`, `public`,
`transporte_regulado`, `utils`. `USAGE = false` em `agendamento`, `despesas`, `empresasimples`,
`sistema_chamados` — schemas legados que o backend Python não mapeia (confirmado: nenhum modelo em
`backend/app/models/` os referencia).

`CREATE = false` em **todos** os schemas para `aprimora_app`. Consequência direta: `aprimora_app`
**não pode rodar migrations**. Ver seção 6, categoria "migrations/DDL".

## 5. Sequences (`role_usage_grants`)

```sql
WITH s AS (
  SELECT c.oid, n.nspname || '.' || c.relname AS nome
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE c.relkind = 'S'
     AND n.nspname IN ('aprimora_py','frota','pagamentos','transporte_regulado','protocolos','utils')
  OFFSET 0)
SELECT nome FROM s WHERE NOT has_sequence_privilege('aprimora_app', oid, 'USAGE') ORDER BY 1;
```

`information_schema.role_usage_grants` conta 237 sequences concedidas a `aprimora_app` e 237 a
`ged_user`. Faltam **6**, todas em `transporte_regulado`:

- `alvara_documento_id_seq`
- `alvara_id_seq`
- `alvara_responsavel_id_seq`
- `veiculo_avaliacao_id_seq`
- `veiculo_documento_id_seq`
- `veiculo_vistoria_id_seq`

Sem `USAGE` na sequence, o `INSERT` falha mesmo com `INSERT` na tabela.

## 6. Funções `SECURITY DEFINER` (`pg_proc.prosecdef`)

```sql
SELECT n.nspname || '.' || p.proname, pg_get_userbyid(p.proowner), p.prosecdef
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE p.prosecdef AND n.nspname NOT IN ('pg_catalog','information_schema');
```

**Zero linhas.** Existem 31 funções de usuário no banco e **nenhuma** é `SECURITY DEFINER`. Não há,
portanto, caminho de escalonamento por função — e também não há nenhuma função pronta para servir
de porta cross-tenant controlada em `SEC-RLS-00B`.

---

## 7. Classificação dos consumidores de banco

Quatro categorias, com o papel alvo de cada uma. Hoje **todas** usam `ged_user`.

### 7.1 API municipal — sujeita a RLS

| Consumidor | Como abre sessão | `app.tenant_id`? | Papel alvo |
|---|---|---|---|
| Rotas de `backend/app/routers/*` | `Depends(get_db)` (`app/database.py:49`) | Sim — `session.info["tenant_id"]` vindo de `request.state`, aplicado pelo listener `after_begin` | `aprimora_app` |
| `TenantMiddleware` (`app/middleware/tenant.py:62,73`) | `SessionLocal()` cru | **Não** — e não precisa: lê só `aprimora_py.tenant`, que não tem RLS | `aprimora_app` |
| `load_permissions` (`app/services/permissoes.py:61`) | recebe a sessão do request | Sim — refaz `SET LOCAL` explicitamente | `aprimora_app` |
| Portal do cidadão (`app/routers/cidadao*.py`) | `Depends(get_db)` | Sim, pela mesma via | `aprimora_app` |

O caminho principal da API é o que **menos** depende do bypass: o `tenant_id` é instalado na sessão
em todo request que passou pelo middleware.

### 7.2 Worker Celery / beat — grants mínimos

| Task | Escopo | `app.tenant_id`? | Depende de bypass? |
|---|---|---|---|
| `processo_completo.run` | por tenant | Sim (`task_session_scope(tenant_id=...)`) | Não |
| `carimbar_anexos.run` | por tenant | Sim | Não |
| `relatorio_tramitacao_bg.run` | por tenant | Sim | Não |
| `verificar_sla_workflows.run` | **1ª sessão sem tenant** para listar `aprimora_py.tenant`; depois uma sessão por tenant | Parcial, por desenho | Não — `aprimora_py.tenant` não tem RLS |
| `snapshot_saldos_pagamentos.run` | idem acima | Parcial, por desenho | Não |
| `limpar_jobs_antigos.run` | **cross-tenant quando `tenant_id=None`** — que é exatamente o modo do beat (`celery_app.py`, `crontab(hour=3)`) | **Não**, nesse modo | **Sim** — ver 8.1 |

Infra comum: `app/tasks/_task_db.py` cria um engine por task (`NullPool`) a partir do mesmo
`settings.database_url`.

Papel alvo: `aprimora_worker`, com grants mínimos por task — e uma decisão explícita sobre
`limpar_jobs_antigos`.

### 7.3 Migrations / DDL — dono do schema, fora do runtime

| Consumidor | Observação |
|---|---|
| `backend/alembic/env.py` | Usa `settings.sync_database_url`, isto é, **o mesmo `DATABASE_URL` do runtime**, trocando o driver. Não há URL separada para DDL. |
| `backend/entrypoint.sh` | Roda `alembic upgrade head` **no start do container da API**, com a credencial da API. |
| `scripts/bootstrap-db.sh` | Cria a role `aprimora_app`, carrega o schema legado e concede grants — exige `SUPERUSER`/`CREATEROLE`. |
| Migrations que fazem `CREATE ROLE` / `ALTER TABLE ... FORCE ROW LEVEL SECURITY` (`0006` e sucessoras) | Exigem ser dono da tabela. |

Papel alvo: `aprimora_migrator`, dono dos schemas, **nunca** usado por processo de runtime. Isto
exige separar o `alembic upgrade` do `entrypoint.sh` da API — hoje eles são o mesmo passo com a
mesma credencial.

### 7.4 Plataforma — cross-tenant por grant explícito

| Consumidor | Tabelas | Observação |
|---|---|---|
| `app/routers/admin_tenants.py` (8 rotas com `require_platform_admin`: linhas 89, 108, 138, 148, 182, 191, 200, 211) | `aprimora_py.tenant`, `modulo`, `tenant_modulo` — e `audit_log` | As três primeiras não têm RLS; `audit_log` **tem**, e é escrita com o `tenant_id` do tenant ALVO sob a sessão do tenant operante. **Depende de bypass** — ver 8.7 |
| `app/services/provisioning_tenant.py:117` | insere em `tenant` (sem RLS) e depois faz `SET LOCAL app.tenant_id` para o tenant recém-criado | Não depende de bypass |
| `app/cli/tenant.py` | delega ao serviço acima | Não depende de bypass |
| `app/cli/seed_bootstrap.py` | `SET LOCAL` correto (`:53`), mas **escreve** em `aprimora_py.modulo` e `modulo_transacao` | Depende de grant que `aprimora_app` não tem |
| `app/cli/seed_demo.py`, `seed_demo_operacional.py` | `SET LOCAL` correto | Não depende de bypass |
| `app/cli/backup.py` | `SessionLocal()` **sem** `tenant_id` | **Depende de bypass** — ver 8.2 |

Papel alvo: `aprimora_platform` (criado por `SEC-01A`), com grants cross-tenant enumerados.

---

## 8. O que **hoje depende** do bypass — lista nominal

Este é o conjunto que `SEC-RLS-00B` tem de resolver com policy ou grant. Restaurar `BYPASSRLS` como
atalho é proibido (ADR-016 §9.1).

### 8.1 `limpar_jobs_antigos.run` no modo beat

`backend/app/tasks/limpar_jobs_antigos.py:48,65-66`. Com `tenant_id=None`,
`task_session_scope()` não instala `app.tenant_id` e a task varre `aprimora_py.job` **de todos os
tenants** (`stmt.where(Job.tenant_id == tenant_id)` só é aplicado quando `tenant_id is not None`).
`aprimora_py.job` tem RLS habilitada e forçada. Sob papel sem bypass e sem GUC setada, a policy
avalia `tenant_id = NULL` → **zero linhas**: a limpeza roda todo dia às 03:00 e não apaga nada,
**sem erro** — falha silenciosa. É a agendada por `celery_app.conf.beat_schedule`.
**Resolução:** iterar tenants (como `verificar_sla_workflows` já faz) ou dar ao worker uma policy
cross-tenant explícita.

### 8.2 `app/cli/backup.py` — export e stats por tenant

`SessionLocal()` em `:106` e `:245`, sem `session.info["tenant_id"]` e sem `SET LOCAL`. As leituras
percorrem `TENANTED_TABLES` (lista de ~30 tabelas com RLS) filtrando por `WHERE tenant_id = :t`.
Sob papel sem bypass, **todos** os `SELECT` devolvem zero linhas: `stats` reporta o tenant vazio e
`export` grava um arquivo de backup **sintaticamente válido e sem dados**. Falha silenciosa, e a
mais perigosa da lista — o sintoma só aparece no restore.
O SQL gerado ainda emite `SET session_replication_role = 'replica'` (`:259`), que **exige
SUPERUSER**; o restore, portanto, depende de `ged_user` por um segundo motivo.
**Resolução:** instalar `tenant_id` na sessão do backup e decidir o papel do restore.

### 8.3 `alembic upgrade head` no `entrypoint.sh`

`backend/entrypoint.sh:6` roda DDL com a credencial da API. `aprimora_app` tem `CREATE = false` em
todos os schemas e não é dono de nenhuma tabela: as migrations falhariam em `CREATE TABLE`,
`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`, `CREATE POLICY` e `GRANT`.
**Resolução:** papel `aprimora_migrator` e um passo de deploy separado do start da API.

### 8.4 `scripts/bootstrap-db.sh`

Faz `CREATE ROLE`, carrega dump legado e concede grants. Exige `SUPERUSER`/`CREATEROLE`
inerentemente. **Resolução:** continua sendo operação de administrador; só precisa ficar
explicitamente fora do runtime.

### 8.5 Módulo Transporte Regulado — inteiro

Sete tabelas ficam **inacessíveis** para `aprimora_app`, por dois defeitos independentes que se
somam:

| Tabela | GUC errada (`app.current_tenant_id`, sem `true`) | Sem grant de tabela | Sem `USAGE` na sequence |
|---|---|---|---|
| `alvara` | — | **sim** (nenhum privilégio) | sim |
| `alvara_documento` | sim | **sim** | sim |
| `alvara_responsavel` | sim | **sim** | sim |
| `alvara_auditoria` | — | só `SELECT` | — |
| `veiculo_avaliacao` | sim | — | sim |
| `veiculo_documento` | sim | — | sim |
| `veiculo_vistoria` | sim | — | sim |

Erros reproduzidos hoje: `ERROR: unrecognized configuration parameter "app.current_tenant_id"` e
`ERROR: permission denied for table alvara`. As 8 tabelas de transporte também estão sem
`FORCE ROW LEVEL SECURITY` (seção 2.1).
**Resolução:** migration que reescreve as 20 policies para
`NULLIF(current_setting('app.tenant_id', true), '')::int`, aplica `FORCE`, concede tabela e
sequence. É o maior item de trabalho de `SEC-RLS-00B`.

### 8.6 `aprimora_py.modulo` e `modulo_transacao` na escrita

`app/cli/seed_bootstrap.py` popula o catálogo de módulos; `aprimora_app` só tem `SELECT`. Não afeta
o runtime da API (que só lê), mas quebra o bootstrap de banco novo se ele rodar com o papel da
aplicação. **Resolução:** o seed é operação de plataforma — atribuí-lo ao papel de migração ou de
plataforma, não ao da API.

### 8.7 Auditoria das rotas de plataforma — escrita cross-tenant em `audit_log`

`app/routers/admin_tenants.py` chama `audit_log(db, tenant_id=<tenant ALVO>, ...)` dentro de uma
sessão cuja `app.tenant_id` é o tenant **operante** (o que o `Host` resolveu). `aprimora_py.audit_log`
tem RLS com `WITH CHECK`, então a inserção é rejeitada:

```
asyncpg.exceptions.InsufficientPrivilegeError: new row violates row-level security policy
for table "audit_log"
[SQL: INSERT INTO aprimora_py.audit_log (tenant_id, ...) VALUES ($1::INTEGER, ...)]
```

Observado em `tests/test_modulos_admin.py::test_descontratar_e_recontratar` na execução da seção 9.
É a concretização do que a ADR-016 §1.6 aponta: as rotas de plataforma usam a sessão e o papel
municipais, sem transação nem identidade próprias para a fronteira cross-tenant.

Agrava: `services/audit.py:68-70` engole a exceção do flush (`except Exception` → `logger.exception`)
para "não quebrar o fluxo principal". Com RLS ativa, isso significa **operação de plataforma
concluída sem trilha de auditoria**, com erro só no log.
**Resolução:** a auditoria de ação de plataforma precisa de sessão/papel próprios
(`aprimora_platform`), ou de uma policy que aceite escrita cross-tenant desse papel.

### 8.8 O arreio dos testes HTTP

Os testes HTTP sobrepõem `require_tenant_id` via `app.dependency_overrides`, mas **não** ajustam
`request.state.tenant_id` — e é dele que `get_db` tira o valor do `SET LOCAL`. Resultado: a sessão
fica com o `app.tenant_id` do tenant default (`sobral`, resolvido pelo `TenantMiddleware` a partir
de `http://test`) enquanto os dados vivem no tenant temporário da fixture. Sob bypass ninguém nota;
sob RLS, tudo retorna vazio.

**A lista abaixo é "quem tem o padrão", não "quem falhou".** A distinção importa: só
`test_pr4d_http_gates.py` falhou *por causa* do arreio na seção 9, porque é o único que assevera
**leitura tenant-scoped**. Os outros asseveram status de gate (403/200) ou identidade, e por isso
passaram — não porque o arreio esteja correto neles. Corrigir só os que falharam deixaria os
demais aparecendo depois como se fossem regressão causada pelas mudanças de policy do
`SEC-RLS-00B`, que é exatamente o ruído que este PR existe para eliminar.

```bash
grep -rn "dependency_overrides\[require_tenant_id\]" backend/tests/
```

**14 ocorrências em 12 arquivos:**

| Arquivo (`backend/tests/`) | Linha(s) | Também sobrepõe `get_db`? | Falhou na §9? |
|---|---|---|---|
| `test_auth_routers.py` | 144, 188 | não | não |
| `test_leitura_por_modulo.py` | 153 | não | não |
| `test_modulos_me.py` | 46 | não | não |
| `test_permissoes_modulo.py` | 278 | não | não |
| `test_pr4d_http_gates.py` | 234, 252 | não | **sim (4 testes)** |
| `test_pr5a_dashboard_servicos.py` | 776 | não | falha pré-existente, nas duas execuções |
| `test_sec1_followup_put_usuario_senha.py` | 169 | **sim** | não |
| `test_sec1_guard_must_change_password.py` | 147 | não | não |
| `test_sec1_login_me_flag.py` | 166 | **sim** | não |
| `test_sec1_marcar_flag_must_change_password.py` | 322 | **sim** | não |
| `test_transporte_p4_relatorio.py` | 353 | não | sim, mas por grant (§9.3), não pelo arreio |
| `test_transporte_regulado_vistoria.py` | 125 | não | sim, mas pela GUC (§9.3), não pelo arreio |

Os três que sobrepõem `get_db` por uma sessão de `admin_engine` têm um segundo problema, e maior:
a sessão é de `ged_user` **independentemente** do `DATABASE_URL`, então esses testes nunca
exercitam RLS — nem hoje, nem depois do `SEC-RLS-00B`.

Contraexemplo bem-feito, para copiar: `tests/test_sec1_login_me_flag.py:144-148`
(`_login_host_header`) manda o header `Host` e deixa o `TenantMiddleware` resolver, com o motivo
documentado no próprio docstring — "o que também ativa RLS corretamente na session do `get_db`
real". Os únicos três arquivos que hoje mandam `Host` são `test_auth_routers.py`,
`test_sec1_followup_put_usuario_senha.py` e `test_sec1_login_me_flag.py`.

Não é defeito de produção — mas **é** dependência do bypass, e precisa ser corrigida **antes** de
`SEC-RLS-00B`, senão a suíte não consegue medir o que ele muda.

### 8.9 Fora da lista, e é bom que esteja

Não dependem do bypass, verificado: o caminho normal da API (o `tenant_id` chega pelo middleware),
`provisioning_tenant`, `seed_demo`, `seed_demo_operacional` (fora da parte de transporte), as cinco
tasks Celery tenant-scoped, e a leitura/escrita das rotas de plataforma em `aprimora_py.tenant`,
`modulo` e `tenant_modulo` — essas três não têm RLS. O que depende, dentro dessas rotas, é só a
auditoria (8.7). A suíte da seção 9 confirma: 907 dos 921 testes passam com `aprimora_app`.

---

## 9. Execução da suíte com `aprimora_app`

O `DATABASE_URL` foi trocado **apenas por variável de ambiente do `docker exec`** — nada foi
commitado. Mecanismo confirmado antes da execução: `Settings` é `pydantic_settings.BaseSettings`
(`backend/app/config.py:8`), e variável de ambiente tem precedência sobre o `backend/.env`
(que existe e traz a sua própria `DATABASE_URL`). Verificação:

```console
$ docker exec -e DATABASE_URL=postgresql+asyncpg://aprimora_app:...@db:5432/ged_saas_db \
    aprimora-py-backend python -c "from app.database import engine; print(engine.url.username)"
aprimora_app
```

Comando exato da medição:

```bash
docker exec -e PYTEST_DB_HOST=db \
  -e DATABASE_URL=postgresql+asyncpg://aprimora_app:ged_password_secure_local@db:5432/ged_saas_db \
  aprimora-py-backend pytest -q -p no:randomly
```

Baseline, para separar falha pré-existente de falha causada pela troca de papel:

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest -q -p no:randomly
```

> **`-p no:randomly` é no-op neste container.** `pytest-randomly` não está instalado
> (`importlib.util.find_spec('pytest_randomly') is None`), então a flag não desliga nada — a ordem
> já era a de coleta, e as duas execuções são comparáveis por isso, não pela flag. Registrado para
> que quem reproduzir a medição não suponha que a ordem foi fixada por ela. O CI também não passa
> a flag.

| Execução | Papel do app | Resultado | Duração |
|---|---|---|---|
| Medição | `aprimora_app` | **14 failed, 907 passed** | 599,56 s |
| Baseline | `ged_user` | **2 failed, 919 passed** | 548,77 s |

**A suíte não passou inteira.** A troca de papel produziu **12 falhas novas**. As fixtures continuam
usando `ged_user` nos dois casos (`PYTEST_DB_HOST` alimenta `admin_engine`); só o papel da
aplicação mudou.

### 9.1 Falhas pré-existentes (falham também com `ged_user` — não contam)

| Teste | Erro |
|---|---|
| `tests/test_jwt_compat.py::test_emitted_token_has_required_claims` | `AssertionError: assert 'aprimora' == 'sistemas'` |
| `tests/test_pr5a_dashboard_servicos.py::test_http_dashboard_com_perm_acessa` | `AssertionError: {"detail":"Sem permissão para a transação 'dashboard'"}` — `assert 403 == 200` |

Idênticas nas duas execuções. Não têm relação com F-12 e não foram investigadas neste PR.

### 9.2 Falha esperada por desenho (1)

| Teste | Erro |
|---|---|
| `tests/test_rls_bypass_caracterizacao.py::test_papel_do_runtime_hoje_tem_bypassrls` | `AssertionError: o runtime conecta como 'aprimora_app', que NÃO tem BYPASSRLS (rolsuper=False)` |

É o teste de caracterização fazendo o que foi feito para fazer: acusar que a configuração desta
execução não tem mais o bypass. Ver o docstring do teste.

### 9.3 Transporte Regulado — grant e policy (5)

| Teste | Erro |
|---|---|
| `tests/test_demo_seed_operacional.py::test_apply_cria_os_tres_modulos` | `asyncpg.exceptions.InsufficientPrivilegeError: permission denied for table alvara` |
| `tests/test_demo_seed_operacional.py::test_apply_idempotente` | idem |
| `tests/test_demo_seed_operacional.py::test_reset_limpa_tudo` | idem, e ainda `permission denied for table alvara_responsavel` e `... alvara_auditoria` |
| `tests/test_transporte_p4_relatorio.py::test_http_usuario_comum_acessa_relatorio_kpis` | `permission denied for table alvara` em `SELECT ... FROM transporte_regulado.alvara WHERE tenant_id = $1 AND excluido IS false` |
| `tests/test_transporte_regulado_vistoria.py::test_http_vencidas_nao_e_engolida_por_vistoria_id` | `asyncpg.exceptions.UndefinedObjectError: unrecognized configuration parameter "app.current_tenant_id"` em `SELECT count(...) FROM transporte_regulado.veiculo_vistoria` |

São exatamente os dois defeitos das seções 3.1 e 4, agora vistos pelo lado da aplicação. Item 8.5.

### 9.4 Escrita cross-tenant de plataforma (1)

| Teste | Erro |
|---|---|
| `tests/test_modulos_admin.py::test_descontratar_e_recontratar` | `InsufficientPrivilegeError: new row violates row-level security policy for table "audit_log"` no `INSERT INTO aprimora_py.audit_log`, seguido de `PendingRollbackError` |

Item 8.7.

### 9.5 Arreio de teste sem `app.tenant_id` (5)

| Teste | Erro |
|---|---|
| `tests/test_pr4d_http_gates.py::test_http_cidadao_dono_lista_complementacoes_200` | `assert 404 == 200` |
| `tests/test_pr4d_http_gates.py::test_http_cidadao_dono_responde_200` | `{"detail":"Processo não encontrado ou não pertence a você"}` — `assert 404 == 200` |
| `tests/test_pr4d_http_gates.py::test_http_cidadao_nao_responde_cancelada_409` | `assert 404 == 409` |
| `tests/test_pr4d_http_gates.py::test_http_cidadao_nao_responde_respondida_409` | `assert 404 == 409` |
| `tests/test_seed_bootstrap.py::test_seed_bootstrap_idempotente` | `assert 0 == 1` — o `SELECT count(*) FROM utils.usuario WHERE email='admin@local.test'` roda numa `SessionLocal()` sem `tenant_id`, e `utils.usuario` tem RLS |

Item 8.8. O `seed_bootstrap` em si **não** falhou: `test_seed_bootstrap_cria_super_usuario` passou,
porque `load_permissions` faz o `SET LOCAL` por conta própria.

### 9.6 O que a execução **não** provou

- O item 8.6 (escrita em `aprimora_py.modulo`/`modulo_transacao`) **não** apareceu como falha: o
  catálogo de módulos já existia no banco, então o seed não tentou inserir. Continua sendo risco em
  banco novo — verificado por consulta de grant, não por execução.
- Os itens 8.1 (`limpar_jobs_antigos` no beat), 8.2 (`cli/backup.py`) e 8.3 (`alembic` no
  `entrypoint.sh`) **não** têm cobertura de teste. Foram estabelecidos por leitura de código somada
  ao estado do catálogo, e **não** foram executados sob `aprimora_app`.
- Nada foi executado contra a VPS de homologação.

---

## 10. Resumo para o `SEC-RLS-00B`

| # | Item | Tipo | Onde |
|---|---|---|---|
| 1 | 20 policies com `app.current_tenant_id` sem `true` | policy | `transporte_regulado` (5 tabelas) |
| 2 | 8 tabelas sem `FORCE ROW LEVEL SECURITY` | policy/DDL | `transporte_regulado` |
| 3 | 4 tabelas sem grant completo | grant | `transporte_regulado` |
| 4 | 6 sequences sem `USAGE` | grant | `transporte_regulado` |
| 5 | `limpar_jobs_antigos` cross-tenant no beat | código ou policy de worker | `app/tasks/limpar_jobs_antigos.py` |
| 6 | `cli/backup.py` sem `app.tenant_id` (+ `session_replication_role`) | código + papel | `app/cli/backup.py` |
| 7 | `alembic` roda no `entrypoint.sh` com credencial da API | papel + deploy | `backend/entrypoint.sh`, `alembic/env.py` |
| 8 | Escrita em `aprimora_py.modulo`/`modulo_transacao` | grant + atribuição de papel | `app/cli/seed_bootstrap.py` |
| 9 | `audit_log` de rota de plataforma grava com o `tenant_id` do tenant ALVO | papel/policy de plataforma | `app/routers/admin_tenants.py`, `app/services/audit.py` |
| 10 | Arreio de teste HTTP sobrepõe `require_tenant_id` mas não `request.state.tenant_id` | teste — **pré-requisito** de 00B | **14 ocorrências em 12 arquivos** de `backend/tests/` (lista nominal em 8.8); só 1 falhou na §9 |

Nenhuma função `SECURITY DEFINER` existe, e nenhuma policy está amarrada a papel nominal — os dois
fatos simplificam a introdução de papéis novos.

---

## 11. Fechamento pelo `SEC-RLS-00B` — item a item

Adicionado em 2026-08-02. **O documento acima continua sendo a medição de `SEC-RLS-00A`, tal como
foi feita** — não foi reescrito. Esta seção diz o que aconteceu com cada item, para que ninguém
leia as seções 8 e 10 como estado atual.

O que `SEC-RLS-00B` **não** faz: trocar o papel efetivo de qualquer ambiente. `DATABASE_URL`
continua apontando para `ged_user`, e F-12 continua ABERTO em produção. O que mudou é que agora
existe para onde ir, e a ida é configuração — `APP_DATABASE_URL`, `WORKER_DATABASE_URL`,
`MIGRATOR_DATABASE_URL`, todas vazias por padrão e caindo em `DATABASE_URL`.

| # (§10) | Item | Estado | Onde |
|---|---|---|---|
| 1 | 20 policies com `app.current_tenant_id` sem `true` | **Fechado** | migration `0078`; guarda em `test_rls_papeis_minimos.py::test_toda_tabela_com_rls_responde_sob_aprimora_app` |
| 2 | 8 tabelas sem `FORCE` | **Fechado** | `0078`; as 8 saíram da `ALLOWLIST_SEM_RLS_FORCADA` |
| 3 | 4 tabelas sem grant | **Fechado** | `0078`. `alvara_auditoria` ficou em `SELECT, INSERT` — trilha append-only, mesma regra da 0076 para `audit_log` |
| 4 | 6 sequences sem `USAGE` | **Fechado** | `0078` |
| 5 | `limpar_jobs_antigos` cross-tenant no beat | **Fechado** | itera tenants ativos, uma sessão por tenant (padrão do `verificar_sla_workflows`) |
| 6 | `cli/backup.py` sem `app.tenant_id` | **Fechado** | `_sessao_do_tenant` instala a GUC **e prova que instalou**; export com zero linhas aborta sem gravar arquivo (`--permitir-vazio` para o tenant genuinamente vazio). O `session_replication_role` do RESTORE continua exigindo SUPERUSER — decidido: restore é operação de DBA, registrado no docstring do módulo |
| 7 | `alembic` com a credencial da API | **Parcial** | `sync_database_url` passou a derivar de `admin_database_url`, então definir `MIGRATOR_DATABASE_URL` já move o DDL para `aprimora_migrator`. O `alembic upgrade head` continua no `entrypoint.sh` da API — separar o passo é mudança de deploy (`scripts/deploy.sh`), não de código de aplicação |
| 8 | Escrita em `modulo`/`modulo_transacao` pelo seed | **Fechado** | os CLIs (`seed_bootstrap`, `seed_demo`, `seed_demo_operacional`, `backup`) abrem sessão por `app/database_admin.py` |
| 9 | `audit_log` de rota de plataforma | **Fechado** em `SEC-01A` (0077, `services/plataforma_auditoria.py`). O `services/audit.py` parou de engolir a exceção do flush — a propriedade agora é "ou a ação e a trilha acontecem, ou nenhuma das duas" |
| 10 | Arreio de teste HTTP | **Fechado** | `tests/conftest.py::arreio_tenant_http`, aplicado nos 12 arquivos. Os três que trocavam `get_db` por sessão de `admin_engine` — e portanto nunca exercitavam RLS — passaram a usar o `SessionLocal` real |

### 11.1 O que continua aberto, com a razão

- **`aprimora_migrator` não é dono das tabelas legadas — e por isso `MIGRATOR_DATABASE_URL` é um
  BLOQUEIO do `SEC-RLS-ROLLOUT`, não um degrau.** Ele tem `CREATE` nos schemas e DML completo, mas
  `ALTER TABLE` em tabela pré-existente (por exemplo `ENABLE ROW LEVEL SECURITY`) exige posse, e o
  dump de `scripts/bootstrap-db.sh` é carregado por `ged_user`. A própria 0078 não rodaria sob o
  papel que ela cria. Como `sync_database_url` deriva dessa variável e o `entrypoint.sh` roda
  `alembic upgrade head` com `set -e`, defini-la em homologação e depois mergear uma migration com
  `ADD COLUMN` faria o backend **morrer no start** com `must be owner of table` — indisponibilidade,
  não erro de permissão previsto. A ordem do rollout é, portanto, **worker → app**, com o migrator
  fora até que a posse dos schemas seja resolvida no bootstrap. Transferir a posse de 234 tabelas é
  mudança de bootstrap, com blast radius maior que este PR inteiro.
- ~~**`provisionar_tenant` continua monolítico**~~ — **FECHADO em `SEC-RLS-00C`** (2026-08-02,
  migration `0079`). O provisionamento virou dois atos com papéis distintos
  (`app/services/provisioning_tenant.py`): `criar_registro_de_tenant` sob `aprimora_platform`,
  `semear_tenant` sob o papel municipal. Com isso `aprimora_app` perdeu `INSERT` em `tenant` e em
  `tenant_modulo`. **Com a ressalva de sempre nesta família:** o `REVOKE` só produz efeito quando
  `APP_DATABASE_URL` estiver definida — hoje ela está vazia e o runtime conecta como `ged_user`,
  `rolbypassrls = t`. O teste prova a propriedade **sob `aprimora_app`**, papel que produção ainda
  não usa; revogar antes de trocar é a ordem certa (ver item 1.0.86 do backlog). Ficaram, por decisão
  caso a caso registrada na 0079: `UPDATE` em `tenant` (configuração institucional do próprio
  município — mas o grant é de TABELA INTEIRA, alcança `ativo`/`plano`/`slug`/limites, e fechar por
  coluna é o item `SEC-RLS-00D` do backlog) e `INSERT` em `audit_log` (trilha do próprio município,
  com RLS FORCE por trás — segunda barreira provada por teste).
  Guarda: `tests/test_entitlement_fronteira_sql.py`, com controle positivo em cada negativa.
  **Modo de falha novo, assumido por escrito:** os dois atos são transações separadas, então um
  provisionamento pode parar no meio. O tenant nasce `ativo = false` e só é ativado no fim, de modo
  que o estado incompleto é **inerte** (não resolve por subdomínio); a conclusão é
  `python -m app.cli.tenant retomar`, idempotente, que recusa tenant já ativo. Não há compensação
  por `DELETE`, e isso é deliberado — apagar tenant não é operação de runtime nenhum.
- **`audit_log_migrator_delete` é mais ampla do que "apagar dado de demonstração".** A policy
  autoriza `aprimora_migrator` a apagar **qualquer** linha de `aprimora_py.audit_log` do tenant que
  a sessão declarou, exceto `entidade = 'tenant'` (a trilha das operações de plataforma, que nenhum
  seed cria e nenhum reset precisa apagar). Não dá para estreitar mais sem quebrar o caso de uso:
  `seed_demo._reset` apaga por `entidade='processo' AND id_entidade IN (...)` **e também** por
  `id_usuario IN (...)`, ao remover os servidores extras — e precisa fazê-lo, porque
  `audit_log.id_usuario` tem FK para `utils.usuario`. Restringir a policy a `entidade = 'processo'`
  faria o segundo `DELETE` devolver zero linhas em silêncio e o `DELETE` do usuário estourar por FK.
  Quem executa `seed_demo reset --tenant sobral --allow-non-demo` (comando que o RUNBOOK ensina)
  está, na prática, autorizando isso. **Decisão pendente de Jorge:** registrar formalmente no
  ADR-016 ou restringir o `reset` a tenants `demo*`.
- **A fronteira de plataforma quase caiu por um grant-cobertor.** O
  `GRANT ... ON ALL TABLES IN SCHEMA aprimora_py TO aprimora_migrator` da 0078 alcançava
  `platform_principal` e `platform_audit_log`, que **não têm RLS** — grant é a única barreira.
  Corrigido com `REVOKE` explícito, e travado por
  `test_rls_papeis_minimos.py::test_tabelas_de_plataforma_so_do_papel_de_plataforma`, que varre
  `information_schema.table_privileges` com allowlist de grantee. A guarda existe porque as
  `ALTER DEFAULT PRIVILEGES` da mesma migration alcançariam qualquer tabela de plataforma futura
  sem que a migration que a criasse precisasse decidir nada.
- **F-12 em si.** O papel do runtime não mudou em ambiente nenhum. Isso é o gate
  `SEC-RLS-ROLLOUT`, por decisão.
