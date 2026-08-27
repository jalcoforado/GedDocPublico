# Aprimora — Migração Python/React

[![Backend tests](https://github.com/jalcoforado/GedDocPublico/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/jalcoforado/GedDocPublico/actions/workflows/backend-tests.yml)

Plataforma SaaS multi-tenant de GED/protocolo para prefeituras. FastAPI +
SQLAlchemy 2 async + Postgres no backend, Next.js 15 + React 19 no frontend,
Celery + Redis nos jobs, nginx na frente (`:8090`).

> **Onde entrar:** [`docs/INDEX.md`](docs/INDEX.md) roteia por tarefa — "vou
> mexer numa migration", "vou fazer deploy", "vou adicionar um módulo". Se você
> é um agente, `CLAUDE.md` já está no seu contexto e tem precedência sobre este
> arquivo em qualquer divergência.

**Status:** em homologação na VPS, piloto Sobral. O sistema é **contratável por
módulo** desde 2026-07-30 (`protocolo`, `pagamentos`, `frota`, `transporte`,
`administracao`) — ver `CLAUDE.md` §Modularização.

**Sobre o PHP.** O nginx nasceu como *Strangler Fig* na frente de um monolito
PHP. Hoje a versão Python é tratada como **independente**: não se porta
comportamento do legado nem se consulta ele como fonte de verdade. O que sobra
da herança e continua valendo é concreto — o schema Postgres é compartilhado
(`utils.*` e `protocolos.*` são tabelas legadas; `aprimora_py.*` e `frota.*` são
nossos) e o nginx tem uma regex de rotas migradas. O desenho abaixo descreve
essa coexistência histórica.

## Arquitetura

```
                                              ┌────────────────────────────┐
  navegador → http://localhost:8090  ────────▶│  nginx Strangler           │
                                              │  (matriz de rotas)         │
                                              └─┬───────────┬──────┬───────┘
                                                │           │      │
                          ┌─────────────────────┘           │      └─────────────────┐
                          │ rotas migradas (/login, /home,  │ /api/v2/*              │ fallback
                          │ /processos, /cidadao, ...)      │                        │
                          ▼                                 ▼                        ▼
                  ┌──────────────┐                  ┌──────────────┐         ┌──────────────────┐
                  │  Next.js 15  │                  │  FastAPI     │         │  Apache + PHP    │
                  │  :3000       │                  │  :8000       │         │  :8081 (legacy)  │
                  └──────────────┘                  └──┬───────────┘         └────────┬─────────┘
                                                      │                              │
                                          ┌───────────┴───────┐  ┌────────┐          │
                                          ▼                   ▼  ▼        │          │
                                  ┌──────────────┐    ┌──────────────┐    │          │
                                  │  Celery      │    │  Redis       │    │          │
                                  │  worker+beat │    │  broker      │    │          │
                                  └──────┬───────┘    └──────────────┘    │          │
                                         │                                │          │
                                         └────────────────┬───────────────┘          │
                                                          ▼                          │
                                              ┌────────────────────────────┐         │
                                              │ PostgreSQL (compartilhado) │◀────────┘
                                              │ ged-saas-project-db-1      │
                                              │ banco: ged_saas_db         │
                                              └────────────────────────────┘
```

**Princípios da coexistência:**

- **Banco único.** Python e PHP escrevem no mesmo `ged_saas_db`. Triggers de auditoria PG continuam disparando.
- **Senhas duplas.** `utils.usuario.senha` (MD5, PHP) preservada; `utils.usuario.senha_bcrypt` (Python) populada por rehash transparente no 1º login.
- **JWT compartilhado.** Por padrão HS256 com o mesmo segredo (`utils.sistema_constante.KEY_LOGIN_GLOBAL_JWT`). Validação aceita HS256 OU RS256. Trocar pra RS256 (`JWT_ALGORITHM=RS256`) quebra interop com PHP — fazer só no cutover.
- **Cookies separados.** Admin usa `aprimora_token`, cidadão usa `aprimora_cidadao_token`, PHP usa `PHPSESSID`. Mesmo navegador pode estar logado em todos simultaneamente.

## Como rodar

Pré-requisitos:
- Docker Desktop rodando
- **`.env` na raiz** — copie de `.env.example` e gere a
  `DADOS_SENSIVEIS_ENCRYPTION_KEY` (chave Fernet que cifra tokens OAuth do
  Google e dados bancários de fornecedor). Sem ela o compose **aborta de
  propósito**, em vez de subir com um segredo padrão. Trocá-la torna ilegível o
  que já foi cifrado com a anterior.
- Networks `aprimora_default` (herdada do legado, declarada como `external`) e
  `aprimora-py` (criada pelo compose)

O banco sobe no próprio compose (serviço `db`, container `aprimora-py-db`) — não
depende mais do stack do PHP estar de pé.

```powershell
cd c:\projetos\aprimora-py
docker compose up -d --build
```

Sobe 7 containers: `db` (Postgres 16), `backend` (FastAPI), `worker` (Celery),
`beat` (scheduler), `frontend` (Next.js), `redis` (broker) e `nginx` (`:8090`).

**Entre sempre pelo `:8090`.** É no nginx que o roteamento e o header `Host`
(resolução de tenant) funcionam. O `:3100` direto **não** serve na stack de
produção-like: o `docker-compose.yml` assa `NEXT_PUBLIC_API_URL=/api/v2` no
bundle — base relativa, que só resolve atrás do nginx —, então o próprio Next
recebe `/api/v2/...` e devolve 404 no login. Para iterar em `:3100` use o
overlay `docker-compose.dev.yml`, que usa base absoluta.

**Toda porta do compose base é `127.0.0.1:`, menos a 8090.** Até 2026-08-05 não
era, e `5432`/`8000`/`3100` respondiam da internet na VPS.
`tests/test_guarda_portas_publicadas.py` reprova quem republicar em `0.0.0.0`.

Abrir <http://localhost:8090> → redireciona pra `/login`.

### Sobre o `healthcheck`

O nginx tem `depends_on: backend: condition: service_healthy`. Em dev, isso evita 502 quando o backend ainda está iniciando. Se o backend recreate e o nginx mantiver IP antigo cacheado, o `resolver 127.0.0.11 valid=10s` no [nginx/default.conf](nginx/default.conf) revalida em até 10s.

## Verificação rápida

```bash
# Banco e API vivos
curl http://localhost:8090/api/v2/health

# Login admin
curl -X POST http://localhost:8090/api/v2/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"admin@local.test","senha":"admin123"}'

# Confirma que PHP legacy continua respondendo
curl -I http://localhost:8081/

# Confirma roteamento (header X-Aprimora-Backend)
curl -I http://localhost:8090/home          # python-frontend
curl -I http://localhost:8090/api/v2/health # python-backend
curl -I http://localhost:8090/qualquer      # php-legacy
```

## Testes

```powershell
# Suite Playwright (e2e: routing Strangler, auth admin, fluxo cidadão)
docker compose --profile test run --rm e2e

# Relatório HTML
start tests-e2e\report\index.html

# pytest backend — `PYTEST_DB_HOST=db` é OBRIGATÓRIO. O default do conftest é
# `ged-saas-project-db-1`, container do stack legado que não existe mais aqui;
# sem a variável todo teste morre com socket.gaierror.
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest -q

# Com cobertura
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest --cov=app --cov-report=term-missing
```

**Suites:**
- `tests/test_login_md5_compat.py` — compatibilidade md5 com PHP legacy
- `tests/test_jwt_compat.py` — formato JWT compatível PHP↔Python
- `tests/test_rls_isolation.py` — isolamento Row-Level Security entre tenants
  (4 testes: SELECT/INSERT/sem-setting/UPDATE — todos via role `aprimora_app`
  NOBYPASSRLS pra validar policies de verdade)

**Tamanho da suíte** (medido em 2026-08-27): **1.400 testes** em 139 arquivos
no backend, mais os specs Playwright. Rodam a cada PR em três workflows —
`backend-tests`, `frontend-tests` e `e2e-assinatura`. Número aqui é fotografia,
não contrato: confira com `pytest --collect-only -q | tail -1`.

## Estrutura

```
backend/
  app/
    main.py                    FastAPI entrypoint
    config.py                  Settings via pydantic-settings
    database.py                Engine async
    auth/
      jwt.py                   HS256 + RS256 (Fase 9.3)
      password.py              MD5 + bcrypt (Fase 9.2)
      deps.py                  get_current_user + get_current_cidadao
    models/                    SQLAlchemy declarative (utils/protocolos/aprimora_py)
    schemas/                   Pydantic v2
    routers/                   FastAPI APIRouter por domínio
    services/                  Lógica de negócio
    tasks/                     Celery (processo_completo, carimbar_anexos, ...)
  pyproject.toml

frontend/
  app/                         Next.js App Router
    (app)/                     Portal admin (com Sidebar)
    cidadao/                   Portal público
    login/                     Login admin
  components/
  lib/api.ts                   Cliente fetch + types
  lib/auth.tsx                 AuthProvider admin
  lib/cidadao-auth.tsx         AuthProvider cidadão
  middleware.ts                Guards de rota

tests-e2e/                     Playwright (rodar com --profile test)
keys/                          Par RSA para JWT RS256 (gitignored)

docker-compose.yml             6 serviços (+ e2e opcional)
nginx/default.conf             Strangler Fig — rotas migradas vs PHP fallback
backend/alembic/               Migrations versionadas (0001 jobs, 0002 bcrypt)
seed-phase2.sql                Catálogos de dev (estados/cidades/etc)
seed-phase3.sql                Processos/movimentações dev
```

## Migrations (Alembic)

Mudanças de schema do Python são versionadas em [backend/alembic/versions/](backend/alembic/versions/). `target_metadata = None` desliga autogenerate — migrations são escritas manualmente para evitar acidente (o ORM mapeia tabelas que serão paulatinamente assumidas pelo Python e o autogenerate poderia querer dropar colunas).

O estado real vem do banco, não daqui — uma tabela de migrations num README
envelhece em silêncio, e esta cobria 22 de 105 antes de alguém notar:

```bash
docker exec aprimora-py-backend alembic current   # onde este banco está
docker exec aprimora-py-backend alembic heads     # DEVE ser head único
docker exec aprimora-py-backend alembic history   # a lista completa
```

As regras para **escrever** uma migration (boilerplate de RLS, GRANTs por
papel, head único, reversibilidade, as três armadilhas que já custaram um
módulo inteiro) estão em `CLAUDE.md` §Migrations — é lá que elas são mantidas,
e o agente `migrations-checker` roda esse checklist.

A narrativa das 22 primeiras — onde o multi-tenant foi construído — está em
[docs/HISTORICO-FASES.md](docs/HISTORICO-FASES.md#migrations-00010022--a-fundação-multi-tenant).

### Admin de plataforma (PR3a)

Gestão de tenants pela interface (`/admin/tenants`) e API (`/api/v2/admin/...`),
além da CLI (`app.cli.tenant`, que reusa o mesmo serviço de provisionamento).

Acesso: desde `SEC-01A` ([ADR-016](docs/architecture/adr/ADR-016-platform-operator-identity.md))
exige **token administrativo RS256** de um IdP dedicado — `iss`, `aud`, JWKS e
`hd` próprios, configurados por `PLATFORM_OIDC_*` — **e** um principal ativo em
`aprimora_py.platform_principal`, cadastrado pela CLI
`app.cli.platform_principal` no host. A allowlist **`PLATFORM_ADMIN_EMAILS` foi
removida**: era o achado F-01, autorização cross-tenant por um e-mail que é
único apenas *por tenant*. Não é permissão de tenant — super-usuário de
prefeitura não entra, e agora nem é uma credencial reconhecida aqui.
Ver [RUNBOOK](RUNBOOK.md) e o
[runbook de operador](docs/runbooks/platform-operator-bootstrap.md).

```bash
# Estado atual
docker exec aprimora-py-backend alembic current

# Histórico
docker exec aprimora-py-backend alembic history

# Aplicar tudo (banco novo)
docker exec aprimora-py-backend alembic upgrade head

# Banco já tem o schema (rodou os SQLs antigos antes do Alembic)? Apenas marcar:
docker exec aprimora-py-backend alembic stamp head

# Criar nova migration (manual — autogenerate desligado)
docker exec aprimora-py-backend alembic revision -m "descricao"
# Edite o arquivo gerado em backend/alembic/versions/ e suba:
docker exec aprimora-py-backend alembic upgrade head

# Rollback de 1 migration
docker exec aprimora-py-backend alembic downgrade -1
```

A tabela `alembic_version` mora em `aprimora_py` (não em `public`) pra isolamento.

## Fases concluídas

O registro completo — ~50 fases, da fundação ao módulo de transporte — está em
[docs/HISTORICO-FASES.md](docs/HISTORICO-FASES.md). Ficava aqui e respondia por
74% do tamanho deste arquivo, cobrando ~11k tokens de quem só queria se
orientar. É histórico: descreve o estado no dia em que cada fase fechou, e
várias foram remapeadas depois.


## Cutover

Quando estiver pronto para aposentar o PHP, ver [CUTOVER.md](docs/archive/CUTOVER.md) — checklist passo a passo.

## Decisões pendentes

- **5.2+ GovBr / AssineJá:** bloqueado por credenciais de homologação.
- **CI/CD:** GitHub Actions roda pytest backend a cada PR ([.github/workflows/backend-tests.yml](.github/workflows/backend-tests.yml)). Falta ruff/mypy + playwright e2e no pipeline.

## Decisões de arquitetura registradas

### Hospedagem de arquivos — manter filesystem local por ora; migrar para object storage antes de produção multi-tenant real

**Estado atual:** anexos, PDFs carimbados e resultados de jobs vivem no filesystem local do container backend (`/app/uploads/tenants/{slug}/...`), montado via bind volume. Servidos pelo Python (`FileResponse` com auth+RLS); nginx não serve `uploads/` direto. Indireção limpa via `e_doc` (DB) + `resolve_anexo_path()` / `tenant_anexos_dir()` — o serviço `services/anexos.py` é o único ponto que toca o disco.

**Decisão:** **manter** filesystem local enquanto é dev + piloto Sobral (single host). Migrar é over-engineering agora.

**Gatilho de migração:** quando entrar **o primeiro documento real que não pode ser perdido** — i.e., antes de onboarding do 2º tenant em produção ou antes de dados com valor probatório. O eixo crítico do domínio **não é escala/throughput**, é **durabilidade + integridade legal** (guarda por décadas via TTD, Lei 11.419/2006) e **isolamento multi-tenant dos bytes** (RLS protege o DB, não o filesystem).

**Alvo:** object storage S3-compatible com **versioning + Object Lock (WORM)** para guarda permanente, **server-side encryption**, **bucket/prefixo por tenant com IAM** (equivalente do RLS para bytes) e **lifecycle policy espelhando a TTD** (corrente→quente, intermediária→frio, permanente→lock, eliminação→delete auditado). Provedor é decisão de compliance/LGPD (MinIO self-hosted vs cloud nacional vs S3), não técnica.

**Caminho de baixo custo:** introduzir interface `StorageBackend` (put/get/delete/exists) com impl `LocalFS` (atual) + seleção por env. Desacopla sem obrigar a subir MinIO já. Refactor localizado em `services/anexos.py` + `config.py`.

**Pendência menor relacionada:** limite de upload divergente — backend `max_upload_size_mb=20`, wizard do cidadão anuncia 25MB. Alinhar.
