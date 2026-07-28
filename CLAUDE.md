# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Idioma: código, comentários, docs e mensagens de commit deste repositório são em **português (pt-BR)**. Mantenha o padrão.

## O que é

Plataforma SaaS multi-tenant de GED/protocolo para prefeituras (piloto: Sobral). Backend **FastAPI + SQLAlchemy 2 async + Postgres**, frontend **Next.js 15 App Router + React 19 + Tailwind**, jobs em **Celery + Redis**, tudo orquestrado por `docker compose` com **nginx** na frente (`:8090`).

Módulos de negócio já entregues: protocolo/processos, anexos, assinatura eletrônica v2, workflow BPM, notificações, auditoria, portal do cidadão, serviços, frota, transporte regulado, pagamentos, minutas (com integração Google Docs), admin de plataforma/tenants.

O nginx nasceu como *Strangler Fig* na frente de um monolito PHP legado. Hoje a versão Python é tratada como **independente** — não portar comportamento do PHP nem consultá-lo como fonte de verdade. O que sobra dessa herança e continua valendo: o schema Postgres é compartilhado com o legado (`utils.*`, `protocolos.*` são tabelas legadas; `aprimora_py.*` e `frota.*` são nossos), e o nginx tem uma regex de rotas migradas (ver "Adicionando um módulo").

## Comandos

```powershell
# Subir tudo (produção-like; frontend em build standalone)
docker compose up -d --build

# Dev com hot-reload do frontend
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Bootstrap de banco novo (schema legado + seeds) — perfil `init`, roda uma vez
docker compose --profile init up bootstrap
```

Containers: `aprimora-py-backend` (:8000), `-frontend` (:3100), `-worker`, `-beat`, `-redis`, `-nginx` (:8090), `-db` (:5432). Entrar sempre por `http://localhost:8090` (nginx) — é lá que o roteamento e o header `Host` (resolução de tenant) funcionam.

### Seeds

São **três**, com papéis distintos:

```bash
# 1. Pré-requisitos globais — roda a cada deploy, idempotente. Garante
#    utils.sistema/nivel, o tenant+admin padrão, o segredo JWT e o catálogo
#    protocolos.acao (ABERTURA/ENCAMINHAMENTO/RECEBIMENTO). Sem as ações não
#    se abre nem tramita processo.
docker exec aprimora-py-backend python -m app.cli.seed_bootstrap

# 2. Protocolo: 12 processos, 15 anexos, 6 serviços, manifestantes, servidores
docker exec aprimora-py-backend python -m app.cli.seed_demo apply --tenant sobral --allow-non-demo

# 3. Pagamentos/frota/transporte. Passa pelos SERVIÇOS: os débitos percorrem o
#    rito real e as baixas geram movimentação de conta — é disso que a
#    conciliação vive. `--modulo` limita a um deles; `reset`/`status` também.
docker exec aprimora-py-backend python -m app.cli.seed_demo_operacional apply --tenant sobral --allow-non-demo
```

`--allow-non-demo` é obrigatório fora de um tenant `demo*`. Na VPS o alvo tem de ser **`sobral`**: o acesso é por IP e o `TenantMiddleware` resolve tudo para o tenant padrão, então dados em outro tenant ficariam invisíveis.

Os dois seeds de demonstração assumiam artefatos que só o `provisionar_tenant` cria ("Protocolo Geral", tipo de manifestante "Pessoa Física", `admin@demo.test`). Hoje caem em get_or_create/fallback — mas é o tipo de acoplamento a vigiar ao estender qualquer um deles.

### Testes

```bash
# Backend — suíte completa (~8 min). PYTEST_DB_HOST é obrigatório: o default do
# conftest é `ged-saas-project-db-1`, container do stack legado que não existe
# mais aqui. Sem ele todo teste morre com socket.gaierror.
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest -q

# Um arquivo / um teste
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_frota_designacao.py -v
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_rls_isolation.py::test_select_isolado -v

# Cobertura
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest --cov=app --cov-report=term-missing

# Frontend — vitest (no host; a imagem `runner` é standalone e não tem devDeps)
cd frontend && npm test
cd frontend && npx vitest run __tests__/GoogleConnectDialog.test.tsx

# Type-check (obrigatório antes de commitar mexida no frontend)
cd frontend && npx tsc --noEmit

# E2E Playwright
docker compose --profile test run --rm e2e
```

**Não rode `npm run lint`** — o projeto não tem ESLint configurado e `next lint` é interativo/trava.

O backend roda com bind-mount do working tree (`./backend:/app`), então `docker exec ... pytest` valida o código da branch atual sem rebuild.

**Testes HTTP usam duas conexões.** As fixtures (`admin_engine`) vão por `PYTEST_DB_HOST`, mas o app FastAPI vai por `DATABASE_URL`. Ao apontar os testes para outro banco, redirecione **as duas** — senão os requests consultam o banco de dev enquanto os dados foram criados no outro, e o sintoma é 403/404 inexplicável.

**Verde local não garante verde no CI.** O container tem coisas que o runner não tem: `/app` gravável, o serviço `redis` na rede e o `backend/.env` (gitignored) com credenciais reais do Google. O CI supre isso via env do job — ao adicionar teste que dependa de credencial, storage ou Redis, confira `.github/workflows/backend-tests.yml`.

**São três workflows** (`backend-tests`, `frontend-tests`, `e2e-assinatura`) e os dois que tocam o banco repetem a mesma sequência de bootstrap (stubs → dump → role `aprimora_app` → `alembic stamp 0020` → `upgrade head` → seeds). Corrigiu bootstrap num, verifique o outro.

### Migrations

```bash
docker exec aprimora-py-backend alembic heads          # DEVE ser head único
docker exec aprimora-py-backend alembic current
docker exec aprimora-py-backend alembic upgrade head
docker exec aprimora-py-backend alembic downgrade -1   # valide reversibilidade
```

### Deploy (VPS de homologação)

Merge em `main` dispara `deploy-vps.yml`, que roda `scripts/deploy.sh start` por SSH. Duas armadilhas custaram várias rodadas de diagnóstico:

**O script se sobrescreve em execução.** `deploy_full` chama `pull_code`, que faz `git reset --hard` sobre o próprio `scripts/deploy.sh` enquanto o bash já o está executando; as funções foram parseadas na entrada. Hoje há um `exec` do script novo após o pull (`DEPLOY_REEXECUTADO` evita laço), mas **mudança no `deploy.sh` ainda leva um deploy para valer** quando a cópia no servidor é anterior a esse `exec` — nesse caso, dispare `gh workflow run deploy-vps.yml` uma segunda vez.

**O nome do projeto compose vem do diretório.** `DEPLOY_PATH` aponta para `/root/GedDocPublico` → projeto `geddocpublico`. Apontar para outro diretório cria uma instalação paralela com volume Postgres **novo e vazio**, e os `container_name:` fixos (globais no daemon) fazem as duas colidirem. Se o deploy falhar com "Conflict. The container name ... is already in use", suspeite disso antes de qualquer outra coisa.

## Arquitetura

### Ciclo de um request

1. **nginx** (`nginx/default.conf`) decide o upstream e adiciona `X-Aprimora-Backend` para depuração. `/api/v2/*` → backend; rotas da regex de páginas migradas → Next.js; resto → fallback legado.
2. **`RequestLoggingMiddleware`** → log JSON estruturado (`app/observability/logging.py`).
3. **`TenantMiddleware`** (`app/middleware/tenant.py`) resolve o tenant pelo **subdomínio do header `Host`** contra `aprimora_py.tenant.slug` e popula `request.state.tenant_id/slug/nome`. Em dev (`STRICT_TENANT_RESOLUTION=false`) cai no `default_tenant_slug`. Por isso testes manuais via curl frequentemente mandam `-H "Host: sobral.aprimora.local"`.
4. **`get_db`** (`app/database.py`) grava `tenant_id` em `session.info`; um listener `after_begin` emite `SET LOCAL app.tenant_id = '<id>'` a cada transação — é isso que faz as policies de **RLS** enxergarem o tenant.
5. Router → service → models.

### Camadas do backend (`backend/app/`)

- `routers/<dominio>.py` — só HTTP: dependências (`require_permission`, `require_tenant_id`, `get_db`), validação de schema e mapeamento para `*Out`. Um módulo pode exportar vários `APIRouter` (ex.: `frota.motoristas_router`); **todos** precisam de `include_router(..., prefix="/api/v2")` em `main.py`.
- `services/<dominio>.py` — regra de negócio, máquinas de estado, unicidade, 404/409. É onde ficam as decisões; routers não decidem.
- `schemas/` (Pydantic v2) — convenção `XCreate` / `XUpdate` / `XOut` / `XAcao` (ex.: `SolicitacaoVeiculoDesignar`).
- `models/` — SQLAlchemy declarativo. `models/__init__.py` reexporta tudo; imports usam `from ..models import Veiculo`.
- `auth/` — `deps.py` (`get_current_user`, `get_current_cidadao`, `require_tenant_id`, `require_platform_admin`), `perms.py` (`require_permission(codigo, action)`), `jwt.py` (HS256/RS256), `password.py` (md5 legado + bcrypt com rehash transparente no primeiro login).
- `tasks/` — Celery (`app.tasks.celery_app`). `cli/` — comandos administrativos (ex.: provisionar tenant). `middleware/`, `observability/`, `utils/`.
- `routers/_crud.py` — `paginated_list` etc. para o CRUD repetitivo (soft-delete + busca + paginação + escopo de tenant).

### Multi-tenancy — as regras que não podem ser quebradas

Isolamento tem **três camadas** e todas são obrigatórias:

1. **RLS no Postgres** — tabelas de negócio têm `ENABLE + FORCE ROW LEVEL SECURITY` com policies `tenant_isolation_select`/`tenant_isolation_modify` sobre `current_setting('app.tenant_id')`.
2. **Filtro aplicacional** — `tenant_filter(stmt, Model, tenant_id)` em `database.py` levanta `ValueError` se você esquecer o filtro num modelo tenanted, ou passar tenant num catálogo global. Use-o.
3. **Disciplina no service** — `tenant_id` **sempre vem do caller** (`require_tenant_id`), **nunca do payload**. Campos server-side (`id_usuario_solicitante`, `status`, `excluido`, `id`) não entram em schemas de entrada. Carga por id filtra `tenant_id` + `excluido.is_(False)` e devolve **404 cross-tenant** (não 403). FKs "soft" (unidade, usuário, veículo) precisam de validação **same-tenant** explícita — a FK do Postgres não filtra por tenant.

Outras convenções de domínio: exclusão é **soft-delete** (`excluido=True`, nunca DELETE físico); unicidade por tenant vira **índice único parcial** `WHERE excluido = false`; transição de estado ilegal é **409**; permissão negada é **403** via `require_permission("<codigo>", "inserir"|"atualizar"|"excluir")` (leitura sem action). Super-usuário faz bypass.

### Migrations (`backend/alembic/versions/`)

`target_metadata = None` — **autogenerate está desligado de propósito**. Todas as migrations são escritas à mão; o ORM mapeia tabelas legadas e o autogenerate tentaria dropar colunas do PHP. Numeração sequencial `NNNN_descricao.py` (já em 0072+), `down_revision` no head anterior, **head sempre único**, `downgrade()` desfazendo o `upgrade()` na ordem inversa.

Tabela nova exige o boilerplate completo: `tenant_id` NOT NULL → `aprimora_py.tenant(id)`, índices `(tenant_id, ...)`, `ENABLE + FORCE ROW LEVEL SECURITY`, as duas policies com `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int`, `GRANT SELECT,INSERT,UPDATE,DELETE` na tabela e `GRANT USAGE, SELECT` na sequence para a role `aprimora_app`. `ADD COLUMN` em tabela existente herda RLS/grants — não repita.

O agente `migrations-checker` (`.claude/agents/`) roda esse checklist; `frota-reviewer` e `frota-test-runner` cobrem revisão e bateria de validação de PR.

### Frontend (`frontend/`)

- `app/(app)/` — portal admin autenticado (layout com Sidebar); `app/cidadao/` — portal público; `app/(plataforma)/` — admin de tenants; `app/login/`, `app/validar/`, `app/alterar-senha-obrigatoria/`.
- `lib/api.ts` (~4.4k linhas) — **cliente único** de toda a API: interfaces TypeScript espelhando os `*Out` do backend + métodos agrupados por domínio. Endpoint novo entra aqui, com o tipo correspondente. Resolve base URL por contexto: `NEXT_PUBLIC_API_URL` no browser, `INTERNAL_API_URL` no SSR.
- `lib/auth.tsx` (admin) e `lib/cidadao-auth.tsx` (cidadão) — providers separados, cookies separados (`aprimora_token` × `aprimora_cidadao_token`); dá para estar logado nos dois ao mesmo tempo. `middleware.ts` faz os guards de rota.
- `components/CrudPage.tsx` — telas de cadastro simples derivam dela. Componentes por módulo em `components/<modulo>/`.
- Ao enviar formulários, normalize `""` → `null` em campos opcionais/datas antes do POST/PUT.

### Adicionando um módulo — o que costuma ser esquecido

1. Registrar **todos** os routers em `main.py` com `prefix="/api/v2"`.
2. Tipos + métodos em `frontend/lib/api.ts`; entrada em `components/Sidebar.tsx`.
3. **Adicionar a rota de topo à regex de `location ~ ^/(...)` em `nginx/default.conf`** — sem isso a página cai no fallback legado e "some" no `:8090`, mesmo funcionando em `:3000`.
4. Migration com o boilerplate de RLS acima.
5. Testes `backend/tests/test_<modulo>_*.py`.

## Testes — convenções

`backend/tests/conftest.py` expõe dois engines por um motivo: `admin_session` usa `ged_user` (SUPERUSER, **BYPASSRLS**) só para setup/teardown; `app_session` usa `aprimora_app` (**NOBYPASSRLS**) e é o único jeito de validar RLS de verdade — teste de isolamento escrito com `admin_session` passa por engano. Com `app_session`, o teste é responsável por `SET LOCAL app.tenant_id` em cada transação. A fixture `two_tenants` cria/limpa dois tenants com slug aleatório.

Dados de teste: e-mails no domínio reservado `.test` (`@e2e.test`, `@ux1smoke.test`), slugs com prefixo identificável (`e2e-`, `sec1-`, `ux1-smoke-`) + sufixo `uuid4().hex[:8]`, cleanup obrigatório no teardown. Testes **não devem assumir banco vazio** — evite contagens globais; ancore em `admin@local.test` no tenant default ou num tenant isolado da fixture.

CI (`.github/workflows/`): `backend-tests.yml` carrega `ci/legacy-schema.sql`, faz `alembic stamp <baseline>` e `upgrade head` — ou seja, **a migration nova é exercitada em banco limpo**. Ao regenerar o dump, atualize o número do `stamp` no workflow. `frontend-tests.yml` roda vitest.

## Docs de referência

`README.md` (arquitetura, tabela completa de migrations, decisões registradas), `RUNBOOK.md` (onboarding de tenant, `must_change_password`/SEC-1, backup por tenant, observabilidade, incidentes comuns), `CUTOVER.md`/`CUTOVER-INVENTORY.md`, `PROTOCOLO-PLAN.md`, `DEPLOY-PLAN.md`/`DEPLOY-SETUP.md`, `CHATBOT-PLAN.md`.
