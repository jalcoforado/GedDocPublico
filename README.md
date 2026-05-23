# Aprimora — Migração Python/React

Substituição gradual do monolito PHP `aprimora/` (porta 8081) por stack moderna (FastAPI + Next.js), via **Strangler Fig**. Roda em paralelo ao PHP — o nginx entry point decide rota a rota qual servidor responde.

**Status:** todas as fases do plano concluídas. Resta o cutover propriamente dito (ver [CUTOVER.md](CUTOVER.md)).

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
- Container `ged-saas-project-db-1` UP (subir antes pelo PHP se não estiver)
- Networks `aprimora_default` (do PHP) e `aprimora-py` (criada pelo compose) — a primeira é declarada como `external`

```powershell
cd c:\projetos\aprimora-py
docker compose up -d --build
```

Sobe 6 containers: `backend` (FastAPI :8000), `worker` (Celery), `beat` (Celery scheduler), `frontend` (Next.js :3000), `redis` (broker), `nginx` (:8090).

Abrir <http://localhost:8090> → redireciona pra `/login` (credenciais pré-preenchidas em dev).

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
# Suite Playwright (22 testes — routing, auth, fluxo completo cidadão)
docker compose --profile test run --rm e2e

# Relatório HTML
start tests-e2e\report\index.html

# pytest do backend (instalar primeiro)
docker exec aprimora-py-backend pip install -e ".[dev]"
docker exec aprimora-py-backend pytest
```

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

Mudanças de schema do Python são versionadas em [backend/alembic/versions/](backend/alembic/versions/). O `env.py` escopa para o que pertence ao Python:

- Tudo no schema `aprimora_py.*` (ex.: `aprimora_py.job`)
- Colunas `senha_bcrypt` adicionadas a `utils.usuario`/`utils.usuario_externo`

**NUNCA toca** o resto (`utils.*`, `protocolos.*`, `public.*`) — pertence ao PHP. `target_metadata = None` desliga autogenerate (migrations são escritas manualmente para evitar acidente).

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

| | |
|---|---|
| 0 | Fundação (Docker + JWT + login) |
| 1 | Auth + estrutura organizacional |
| 2 | Cadastros (cidade/bairro/manifestante/assunto/...) |
| 3 | Processo (CRUD + movimentação + encaminhamento + anexos) |
| 4 | PDFs (capa, etiquetas, comprovantes, carimbo, processo completo) |
| 5.1 | Assinatura interna |
| 6 | Relatórios (processos, tramitação, assinaturas) |
| 7 | Jobs assíncronos (Celery + Redis + Beat) |
| 8 | Portal cidadão (auth próprio, cadastrar, abrir, acompanhar) |
| 9.1-9.4 | Strangler nginx + bcrypt + RS256 + Playwright + cookie HttpOnly |

## Cutover

Quando estiver pronto para aposentar o PHP, ver [CUTOVER.md](CUTOVER.md) — checklist passo a passo.

## Decisões pendentes

- **5.2+ GovBr / AssineJá:** bloqueado por credenciais de homologação.
- **CI/CD:** sem pipeline (ruff/mypy/pytest/playwright em PR seriam bem-vindos).
