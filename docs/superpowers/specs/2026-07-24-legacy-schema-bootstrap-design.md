# Design: Incorporar o schema legado via bootstrap correto

**Data:** 2026-07-24
**Autor:** Jorge + Claude
**Status:** Aprovado (aguardando review do spec)

## Problema

O sistema aprimora-py depende do schema legado PHP (`utils` + `protocolos`) como
baseline. O bootstrap do banco no servidor (e a config atual) é uma versão
**quebrada e simplificada** do bootstrap real que o CI usa e que funciona:

- Servidor faz: carrega `ci/legacy-schema-filtered.sql` com erros suprimidos
  (`grep -v ERROR`) → `alembic upgrade head` **do zero (0001)**.
- Resultado: **1301 erros** no load, tabelas core (ex.: `protocolos.processo`)
  **nunca criadas**, migrations nunca aplicam limpo (`alembic_version` vazio),
  `utils.usuario` sem 7 colunas → login 500, catálogo de permissões vazio →
  nenhum módulo na sidebar. Foi a origem do "minimal MVP".

**Causa raiz:** o dump legado foi gerado de um banco **já-migrado até a revision
baseline `0020`** e referencia objetos externos (extensions, funções `public`,
FKs para schemas legados `despesas`/`empresasimples`/`agendamento`, e a tabela
`sistema_chamados.tipo_chamado` usada por um trigger legado). Carregado **sem os
pré-requisitos** e **sem `alembic stamp 0020`**, falha.

## Descoberta-chave

O bootstrap **correto já existe e funciona** — em
`.github/workflows/backend-tests.yml`. São 4 passos (stubs → dump completo →
`stamp 0020 && upgrade head` → role RLS). **O dump não precisa ser regenerado**;
o bootstrap do deploy precisa ser corrigido para espelhar o CI.

## Decisões (brainstorming)

1. **Estado-final:** manter o legado como **baseline dump** (`ci/legacy-schema.sql`),
   replicando o bootstrap do CI. NÃO fundir em migration baseline; NÃO migrar
   dados reais do PHP (mantém [[feedback_php_independence]]).
2. **Seed pós-schema:** **mínimo automatizado** (catálogo global + tenant Sobral
   + admin super-usuário + JWT), idempotente, corrigindo a inconsistência
   `app=sistemas` vs `aprimora`.
3. **Estrutura:** **script único idempotente** `scripts/bootstrap-db.sh` como
   fonte da verdade, chamado pelos init services do compose (profile `init`) e
   rodável à mão. Substitui os services `schema-init`/`db-init` atuais.
4. **Credenciais:** admin `admin@local.test` / senha dev `admin123` (mantidas).

## Arquitetura

### A. `scripts/bootstrap-db.sh` — 6 passos idempotentes

| # | Passo | Detalhe |
|---|-------|---------|
| 0 | Guard | Espera DB pronto; se `protocolos.processo` já existe, pula passos 1-2 (idempotência — o load de dump não é re-executável) |
| 1 | Stubs | `CREATE EXTENSION uuid-ossp`; `public.trigger_set_timestamp()`; schemas stub `despesas.feempliq`, `empresasimples.cnae_subgrupos`, `agendamento.servico_informacao`, `agendamento.servico_unidade_trabalho`; **`sistema_chamados.tipo_chamado`** (o trigger legado `utils.copia_sistemas_tipochamados()` insere nela ao inserir em `utils.sistema` — sem o stub, o seed falha) |
| 2 | Dump completo | `psql -v ON_ERROR_STOP=1 -f ci/legacy-schema.sql` (o **completo**, não o `-filtered`) |
| 3 | **Role RLS (ANTES do upgrade!)** | cria `aprimora_app` + grants nos 4 schemas. **DEVE vir antes do upgrade** — a migration 0024 faz GRANT à role (validação provou que falha senão) |
| 4 | Baseline + Migrations | `INSERT INTO aprimora_py.alembic_version VALUES ('0020')` (determinístico) → `alembic upgrade head` (roda 0021–0062) |
| 5 | Seed | invoca `python -m app.cli.seed_bootstrap` (seção C) |
| 6 | Sanidade | asserts: `protocolos.processo` existe, alembic em `0062`, ~224 tabelas, tenant Sobral existe, admin é super-usuário |

Config via env (`DATABASE_URL`/PGHOST etc.), defaults de dev. Falha ruidosa
(`set -e`, `ON_ERROR_STOP=1`) — o oposto do `grep -v ERROR` atual.

### A.1 Correções de bug pré-requisito (descobertas na validação)

Dois bugs **bloqueavam qualquer build limpo** — já corrigidos e a serem
commitados como parte deste trabalho:

1. **`backend/alembic/env.py` não fazia commit** — `run_migrations_online()`
   chamava `context.run_migrations()` mas nunca `connection.commit()`. Em
   SQLAlchemy 2.0 a conexão não faz autocommit, então TODAS as migrations (e o
   bump de `alembic_version`) faziam rollback ao fechar a conexão. **Causa raiz
   de `alembic_version` sempre vazio no servidor.** Fix: `connection.commit()`
   após `run_migrations()`.
2. **`0062_minuta_sanitizar_templates.py` sem guard** — fazia
   `SELECT conteudo FROM protocolos.template_documento` sem checar existência
   (a 0060, idêntica, tem o guard). Quebrava com `column "conteudo" does not
   exist` em build limpo (a tabela mora em outro schema/nome). Fix: mesmo guard
   da 0060 (noop se coluna ausente).

### B. Wiring no compose + imagem

- O script roda a partir do **container backend** (tem python/alembic). Adicionar
  `postgresql-client` ao `backend/Dockerfile` (psql pros passos 1-4).
- Novo service `bootstrap` (profile `init`) chama `scripts/bootstrap-db.sh`;
  monta o repo (bind-mount já existe) + `ci/legacy-schema.sql`.
- **Remove** os services `schema-init` e `db-init`.
- `entrypoint.sh` do backend deixa de rodar `alembic upgrade head` cru (o
  bootstrap cuida disso); backend só sobe uvicorn. (Confirmar na implementação.)

### C. `app.cli.seed_bootstrap` — novo CLI idempotente

Passos (todos `get_or_create`, seguros para re-execução):

1. Catálogo global: `utils.sistema(app='aprimora', ...)` + `utils.nivel(valor=0)`.
   (Inserção em `utils.sistema` já funciona pois o stub `sistema_chamados` existe.)
2. Tenant Sobral (`aprimora_py.tenant`, id=1) — o dump é schema-only e o
   `stamp 0020` pula a migration 0003 que semeava.
3. Admin super-usuário `admin@local.test` (bcrypt de `admin123`,
   `must_change_password=false`) + `utils.grupo` (nível 0, sistema aprimora) +
   `utils.usuario_grupo` (tenant 1, ativo).
4. Segredo `KEY_LOGIN_GLOBAL_JWT` em `utils.sistema_constante` (gera random se
   ausente).
5. Alinha `app='aprimora'` em todos os pontos (corrige a inconsistência onde
   `provisioning_tenant` hardcoda `'sistemas'`).

### D. Rollout: local → servidor

1. **Local (validar):**
   `docker compose down -v` → `docker compose --profile init up bootstrap`
   → `docker compose up -d`. Critérios: `processo` existe, alembic `0062`,
   login 200, `/auth/me` super=true, módulos na sidebar.
2. **Servidor:** `git pull` → mesmo fluxo (rebuild limpo, `docker compose down -v`).
   Backup **opcional** — sistema em testes, dados atuais descartáveis (confirmado
   pelo Jorge 2026-07-24).

### E. Validação / testes

**✅ VALIDADO end-to-end (2026-07-24)** num DB descartável local
(`ged_bootstrap_test`): stubs → dump completo (181 tabelas, carregou LIMPO com
`ON_ERROR_STOP=1`) → role → baseline 0020 → `upgrade head` → **`alembic=0062`,
224 tabelas, `protocolos.processo`+`pagamentos.debito`+`transporte_regulado.*`
todos presentes**. Os 2 bugs (env.py commit, 0062 guard) foram achados e
corrigidos nessa validação.

- Check de sanidade automatizado no fim do bootstrap (passo 6).
- Testes existentes (pytest backend via docker) continuam válidos.
- Falta validar na implementação: passo 5 (seed) end-to-end (login 200 +
  `/auth/me` super=true) e o fluxo completo via `docker compose --profile init`.

## Fora de escopo

- Regenerar/reordenar o dump legado (não é necessário).
- Fundir o legado em migration Alembic baseline.
- Migrar dados reais do PHP.
- Mobile/PWA, Gov.br/ICP-Brasil.

## Riscos

- ~~Dump pode não estar na baseline 0020~~ — **RESOLVIDO na validação:** baseline
  0020 confirmada (0021 rodou sem colisão de tabela).
- ~~Qual dump é o correto~~ — **RESOLVIDO:** `legacy-schema.sql` (completo) é o
  certo; carrega limpo com stubs. O `-filtered` é descartado.
- **Estado atual do servidor** é híbrido/sujo — o rollout é rebuild limpo
  (destrói o DB atual; backup antes). Dados atuais são desprezíveis.
- **Passo 5 (seed) ainda não validado end-to-end** — o CLI `seed_bootstrap` será
  escrito e validado na implementação (login 200 + super-usuário).

## Band-aids atuais a consolidar

Já aplicados à mão no servidor (a formalizar no bootstrap): 7 colunas em
`utils.usuario`, segredo JWT, seed super-usuário, `frontend/.env.local`
(`NEXT_PUBLIC_API_URL=/api/v2`), override de compose. Ver [[project_next_step]].
