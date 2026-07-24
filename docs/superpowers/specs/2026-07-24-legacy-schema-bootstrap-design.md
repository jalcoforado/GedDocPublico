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
| 3 | Migrations | `alembic stamp 0020` → `alembic upgrade head` (roda só 0021–0062) |
| 4 | Role RLS | cria `aprimora_app` (LOGIN, NOSUPERUSER, NOBYPASSRLS) + grants nos 4 schemas (0006 é pulada pelo stamp) |
| 5 | Seed | invoca `python -m app.cli.seed_bootstrap` (seção C) |
| 6 | Sanidade | asserts: `protocolos.processo` existe, alembic em `0062`, tenant Sobral existe, admin é super-usuário |

Config via env (`DATABASE_URL`/PGHOST etc.), defaults de dev. Falha ruidosa
(`set -e`, `ON_ERROR_STOP=1`) — o oposto do `grep -v ERROR` atual.

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
2. **Servidor:** `pg_dump` backup → `git pull` → mesmo fluxo (rebuild limpo).

### E. Validação / testes

- **Primeiro passo da implementação:** validar a hipótese num **DB descartável
  local** (dump completo + stubs + `stamp 0020` + `upgrade head`). Se `processo`
  e as tabelas de módulo aparecerem e alembic chegar em `0062`, o design está
  provado antes de tocar em algo real. (No servidor esse teste já rodou parcial:
  0001–0005 e 0006-corrigido passam; falta provar com dump completo + stamp.)
- Check de sanidade automatizado no fim do bootstrap (passo 6).
- Testes existentes (pytest backend via docker) continuam válidos — o CI já
  exercita esse caminho.

## Fora de escopo

- Regenerar/reordenar o dump legado (não é necessário).
- Fundir o legado em migration Alembic baseline.
- Migrar dados reais do PHP.
- Mobile/PWA, Gov.br/ICP-Brasil.

## Riscos

- **Dump pode não estar exatamente na baseline 0020** — se drift, `stamp 0020`
  + `upgrade` pode colidir. Mitiga: validação em DB descartável primeiro.
- **`legacy-schema.sql` (completo, May 28) pode estar desatualizado** vs o
  `-filtered` (Jul 23). Confirmar qual reflete o schema correto na validação;
  se o filtered for o "bom", ajustar o passo 2.
- **Estado atual do servidor** é híbrido/sujo — o rollout é rebuild limpo
  (destrói o DB atual; backup antes). Dados atuais são desprezíveis.

## Band-aids atuais a consolidar

Já aplicados à mão no servidor (a formalizar no bootstrap): 7 colunas em
`utils.usuario`, segredo JWT, seed super-usuário, `frontend/.env.local`
(`NEXT_PUBLIC_API_URL=/api/v2`), override de compose. Ver [[project_next_step]].
