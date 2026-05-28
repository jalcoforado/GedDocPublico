# Aprimora — Migração Python/React

[![Backend tests](https://github.com/jalcoforado/GedDocPublico/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/jalcoforado/GedDocPublico/actions/workflows/backend-tests.yml)

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
# Suite Playwright (e2e: routing Strangler, auth admin, fluxo cidadão)
docker compose --profile test run --rm e2e

# Relatório HTML
start tests-e2e\report\index.html

# pytest backend — dev deps já vêm no Dockerfile, sem instalar nada
docker exec aprimora-py-backend pytest

# Com cobertura
docker exec aprimora-py-backend pytest --cov=app --cov-report=term-missing
```

**Suites:**
- `tests/test_login_md5_compat.py` — compatibilidade md5 com PHP legacy
- `tests/test_jwt_compat.py` — formato JWT compatível PHP↔Python
- `tests/test_rls_isolation.py` — isolamento Row-Level Security entre tenants
  (4 testes: SELECT/INSERT/sem-setting/UPDATE — todos via role `aprimora_app`
  NOBYPASSRLS pra validar policies de verdade)

**Cobertura atual:** 86 testes backend (login compat, JWT, RLS isolation,
NUP Mod-11 + concorrência, apensamento anti-ciclo, permissões granulares,
tokenize + hierarquia TTD) + 31 specs e2e Playwright (auth admin, ciclo
cidadão, routing Strangler, balcão P1, wizard cidadão P3). Rodam a cada
PR via GitHub Actions (`.github/workflows/backend-tests.yml`).

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

Migrations atuais:

| Revisão | O que faz |
|---|---|
| `0001` | Cria schema `aprimora_py` + tabela `aprimora_py.job` (Celery) |
| `0002` | Adiciona `senha_bcrypt` em `utils.usuario`/`utils.usuario_externo` |
| `0003` | Cria `aprimora_py.tenant` + seed Sobral (`id=1, slug='sobral'`) |
| `0004` | Adiciona `tenant_id INTEGER NOT NULL REFERENCES aprimora_py.tenant(id)` em 26 tabelas de negócio (todo `protocolos.*` exceto catálogos `acao`/`prioridade`/`tipo_assinatura`, todo `utils.*` exceto catálogos `estado`/`cidade`/`bairro`/`nivel`/`sistema`/`transacao`, e `aprimora_py.job`). Backfill: todas as linhas existentes recebem `tenant_id=1`. Índices `(tenant_id, id)` em `processo`, `movimentacao`, `encaminhamento`, `anexo_processo`. |
| `0005` | Particiona UNIQUEs globais por tenant: `utils.usuario.email` e `utils.usuario.cpf` viram `(tenant_id, email/cpf)` partial unique WHERE excluido IS FALSE. |
| `0006` | RLS (Row-Level Security): cria role `aprimora_app` (LOGIN, NOSUPERUSER, NOBYPASSRLS, senha dev=`ged_password_secure_local`), GRANTs DML, `ENABLE + FORCE ROW LEVEL SECURITY` em 26 tabelas, policies `tenant_isolation_select/modify USING (tenant_id = current_setting('app.tenant_id'))`. Em dev `ged_user` (super) bypassa; em prod basta mudar `DATABASE_URL` para usar `aprimora_app`. |
| `0007` | `aprimora_py.workflow_definition` (DSL JSONB + versionamento por slug+versao) + RLS + GRANTs `aprimora_app`. Schema da Fase 19 (workflow BPM). |
| `0008` | `aprimora_py.workflow_instance` + `workflow_transicao_log` (engine de transições — Fase 20a). Índice parcial único `(id_processo) WHERE ativa IS TRUE` garante 1 instance ativa por processo. RLS + GRANTs idênticos ao padrão das demais. |
| `0009` | `aprimora_py.tipo_processo_workflow` — mapeia `(tenant_id, id_tipo_processo)` → `slug_workflow`. Unique por `(tenant_id, id_tipo_processo)`. RLS + GRANTs. Schema da Fase 20b (integração Processo↔Workflow). |
| `0010` | `aprimora_py.workflow_sla_alerta` (Fase 21) — registra SLA estourado por estado da instance. Dedup atômico via índice parcial único `(id_workflow_instance, estado) WHERE resolvido_em IS NULL`. RLS + GRANTs. |
| `0011` | `aprimora_py.notificacao` (Fase 17) — motor de notificações multi-canal (in_app, email, whatsapp). Destinatário interno (id_usuario FK utils.usuario) OU email livre (check constraint exige um). Colunas: canal, tipo, titulo, mensagem, link_url, payload (JSONB), prioridade, lido_em, enviado_em, erro. Índices: `(tenant_id, id_usuario, canal, lido_em)` (Bell unread) e `(tenant_id, tipo, criado_em)`. RLS + GRANTs. |
| `0012` | `aprimora_py.notificacao_preferencia` (Fase 17b) — 1 row por (tenant_id, id_usuario) unique. Flags `canal_in_app/email/whatsapp` (defaults: in_app=true, email=true, whatsapp=false). Ausência da row = defaults. RLS + GRANTs. |
| `0013` | Adiciona `telefone VARCHAR(20)` em `utils.usuario` (Fase 16, WhatsApp). Idempotente — checa `information_schema` antes do ALTER porque o legado PHP pode já ter a coluna. Downgrade no-op pelo mesmo motivo (coluna compartilhada). |
| `0014` | `aprimora_py.audit_log` (Fase 24) — append-only. `(tenant_id, id_usuario, acao, entidade, id_entidade, payload JSONB, request_id, ip, criado_em)`. Convenção de ação `<entidade>.<verbo>` (ex: `processo.aberto`, `processo.encaminhado`). 3 índices: por tenant+tempo, por entidade+id, por usuário+tempo. RLS com policy SELECT+INSERT (sem UPDATE/DELETE — imutável). |

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
| 10 | Alembic (substitui os SQLs antigos) |
| 11 | Multi-tenant foundation: `aprimora_py.tenant` + `tenant_id` em todas as tabelas de negócio (Sobral = tenant 1) |
| 12 | Resolução de tenant via subdomínio (`{slug}.aprimora.local` em dev, `{slug}.aprimora.app` em prod): `TenantMiddleware`, deps `require_tenant_id`/`get_current_tenant`, endpoint `GET /api/v2/tenants/me`. Fallback default em dev. |
| 13a | Helper `tenant_filter()` + propagação de `tenant_id` em 12 routers, 10 services, 4 tasks Celery; JWT (admin + cidadão) carrega claim `tenant_id`; `get_current_user`/`get_current_cidadao` validam token↔Host (403 cross-tenant). |
| 13b | Migration 0005 (UNIQUE email/cpf por tenant) + 0006 (RLS habilitado em 26 tabelas, role `aprimora_app` sem BYPASSRLS, policies `tenant_isolation`, listener SQLAlchemy faz `SET LOCAL app.tenant_id` em cada BEGIN). |
| 14 | Uploads por tenant: `/app/uploads/tenants/{slug}/anexos|carimbados|jobs/...`. Anexos legacy de Sobral em `/app/uploads/anexos/` continuam acessíveis via `resolve_anexo_path()`. Tasks Celery passam `tenant_slug` + escrevem em paths multi-tenant. |
| 15 | CLI `python -m app.cli.tenant create|list|deactivate|activate` para onboarding manual. Endpoint público `GET /api/v2/branding/me` retorna `{slug, nome, cor_primaria, logo_url}` pro frontend customizar antes do login. `BrandingProvider` no layout aplica cor + logo + título da aba. |
| 33 | Observabilidade multi-tenant: logs JSON estruturados (`{ts, level, logger, msg, request_id, tenant_id, tenant_slug, usuario_id, method, path, status, duration_ms}`) via `RequestLoggingMiddleware` + `JsonFormatter`. Endpoint `/health` reporta `version, db, db_latency_ms, tenant`. Integração Sentry opcional via `SENTRY_DSN` env — tags `tenant_id/slug/request_id` populadas automaticamente. |
| 34 | Backup/DR por tenant: CLI `python -m app.cli.backup stats|export|dr-drill --tenant SLUG`. Export gera SQL standalone idempotente (DELETEs filhos-primeiro + INSERTs pais-primeiro + setval das sequences) em `/app/uploads/tenants/{slug}/backups/`. Restore: `psql -f arquivo.sql`. Runbook completo em [RUNBOOK.md](RUNBOOK.md). |
| 19 | Workflow — schema + DSL JSON + avaliador SAFE (sem engine ainda, vem na 20a). Tabela `aprimora_py.workflow_definition` com RLS + versionamento (PUT cria nova versão e desativa anterior). DSL Pydantic-validado: estados (com `final`/`sla_dias`), transições (com `condicao` opcional, `grupos_permitidos`, `label`). Avaliador via `simpleeval` em `services/workflow_dsl.py` — `eval()` NUNCA usado; `__import__`/funções não-whitelisted bloqueados. Endpoints CRUD + `POST /api/v2/workflow-definitions/test-expr` pra UI validar condições. |
| 20a | Workflow engine — instanciação + transições. Tabelas `aprimora_py.workflow_instance` (1 ativa por processo, garantido por índice parcial único) e `workflow_transicao_log` (auditoria append-only com `contexto_snapshot`). Service `workflow_engine.py` (`iniciar`, `compute_contexto`, `transicoes_disponiveis`, `executar_transicao`). Contexto auto carrega `dias_aberto/numero_processo/id_assunto/...` do Processo associado + `estado_anterior` do último log. Estado final marca `ativa=false` + `finalizada_em`. Endpoints `POST /api/v2/workflow-instances`, `GET /workflow-instances?id_processo=`, `GET /workflow-instances/{id}` (com transições disponíveis + log), `POST /workflow-instances/{id}/transicao`. |
| 20b | Integração Processo↔Workflow. Migration 0009 cria `aprimora_py.tipo_processo_workflow` (mapeia `tipo_processo → slug_workflow`). DSL `WorkflowTransicao` ganha `evento: "manual" | "abertura" | "encaminhamento" | "recebimento"`. Service `workflow_integration.py` com `auto_iniciar_workflow_se_aplicavel` (chamado no fim de `abertura_processo.abrir_processo`) e `disparar_evento` (chamado em `acoes_processo.encaminhar/receber`). Falhas silenciadas (workflow é opt-in). Endpoints `PUT /api/v2/tipo-processo-workflow/{id_tipo_processo}` (slug_workflow=null remove) e atalho `GET /api/v2/processos/{id}/workflow`. Smoke E2E validou ciclo completo: mapear, abrir processo, ver instance auto-criada, encaminhar→transição automática, receber→transição automática. |
| 21 | SLA por etapa + alertas. Migration 0010 cria `aprimora_py.workflow_sla_alerta` com índice parcial único pra dedup atômico. DSL `WorkflowEstado.sla_dias` (1..365) já existia desde 19. `workflow_engine.compute_dias_no_estado` usa `executada_em` do último log com `estado_para==estado_atual` (ou `iniciada_em` se nunca transitou). `executar_transicao` auto-resolve alertas pendentes do estado deixado (`resolucao="transitado"`). Task beat `verificar_sla_workflows` varre tenants ativos 4x/dia (00,06,12,18 BRT) e usa `INSERT ... ON CONFLICT DO NOTHING`. Endpoints `GET /api/v2/workflow-alertas?apenas_pendentes&id_processo` (com detalhes do processo), `POST /workflow-alertas/{id}/resolver` (resolução manual) e `POST /workflow-alertas/verificar-agora` (dispatch imediato). Notificação real (email/whatsapp) depende do motor de notificações da Fase 17. |
| 22a | UI workflow read-only (diagrama). Frontend ganha `@xyflow/react@12` e 3 entradas: lista em `/workflow` (todos os WorkflowDefinitions do tenant), detalhe em `/workflow/[id]` (diagrama React Flow + listas de estados/transições) e painel embutido no detalhe do processo (`<ProcessoWorkflowPanel>` em `/processos/[id]`) mostrando instance ativa, estado atual destacado no diagrama, alertas SLA com resolução inline, transições disponíveis (botão dispara `POST /transicao`) e histórico de transições. Layout dos nodos via BFS por coluna a partir de `estado_inicial`. Códigos visuais: borda dashed=inicial, verde=final, primary=atual, edge roxa=tem condição, edge tracejada=evento automático (não-manual). Link no Sidebar (grupo Geral) + rota `workflow` adicionada à regex nginx Strangler. **Sem edição** — DSL ainda só por API; editor visual fica pra 22b. |
| 22b | Editor visual de workflow. Schema `WorkflowEstado` ganha `posicao: {x,y}` opcional (DSL). Páginas `/workflow/novo` e `/workflow/[id]/editar` montam `<WorkflowEditor>` (drag pra reposicionar nodos, persiste em DSL; arrastar handle entre nodos cria transição; Backspace exclui selecionado; estado inicial não pode ser excluído) + `<WorkflowEditPanel>` lateral com form do estado (slug/nome/SLA/final/definir-como-inicial — slug renomeado propaga em transicoes/estado_inicial) ou da transição (label/evento/condição/grupos), incluindo botão **Testar condição** que chama `POST /workflow-definitions/test-expr` com contexto JSON editável e mostra resultado truthy/falsy/erro inline. Validação client-side antes de salvar: slug válido, sem duplicados, transições referenciam estados, estado inicial existe, alcançabilidade (warning se há órfãos), final sem transição saindo. **`PUT /workflow-definitions/{id}` agora gera nova versão sempre que DSL é enviado** (instâncias ativas continuam na versão antiga); só nome/descricao/ativo atualizam in-place. Botão "Editar (nova versão)" no detalhe + "Novo workflow" na lista. Smoke E2E: POST com posições round-trip OK, PUT criou v2 com v1 desativada, test-expr retornou `truthy=true` pra `dias_aberto<30`, páginas compilam 200 OK. |
| 22c | Migração de instances entre versões. Backend: `GET /workflow-definitions/{id}/versoes` lista todas as versões do mesmo slug com contagem de instances ativas; `POST /workflow-instances/{id}/migrar` body `{id_workflow_definition_destino, mapa_estados?}` valida mesmo slug + destino ativo + estado destino existente, grava log `MIGRAÇÃO v→v` com snapshot, se estado destino é `final` encerra a instance. Service `workflow_engine.migrar_instance()`. Mapa identidade quando `mapa_estados=null`. Frontend: `<WorkflowVersoes>` no detalhe do WF lista todas as versões com badge ativa/inativa e contagem de instances; quando o WF aberto é o ativo e há instances em versões antigas, botão "Migrar N → v{N+1}" (com confirm) ou migração individual via accordion "Ver instances". Smoke: criei v1+v2 do mesmo slug, instance criada em v1 estado `a`, listVersoes retornou ambas, `POST /migrar` moveu instance pra v2 mantendo estado, log mostra "MIGRAÇÃO v1 → v2". |
| Trail processo | Mini-trail horizontal mostrando unidades visitadas pelo processo. Backend: `GET /api/v2/processos/{id}/trail` retorna lista ordenada de passos (1ª passo = abertura na unidade proprietária, demais = encaminhamentos). Cada passo tem `unidade_nome/sigla`, `tipo`, `data`, `cancelado`, `atual` (último não-cancelado). Frontend: `<ProcessoTrail>` faixa horizontal de cards conectados por `ArrowRight` no card do processo. Cards destacam atual (border primary), riscam cancelados (opacity 60%, dashed border). Mostra sigla grande e nome embaixo. Adicionado ao detalhe `/processos/[id]`. |
| Picker forms | `<UnidadePicker>` aplicado em mais 2 forms: `/processos/novo` (`id_unidade_proprietaria`) e `/unidades-trabalho` editor (`id_unidade_pai`). Sub previne ciclo no pai-edit (não permite escolher a própria unidade como pai). Removido o `useQuery` `unidades-all` redundante de `/processos/novo` — picker carrega sob demanda. |
| Picker organograma | Substitui o dropdown "Unidade responsável" do editor de workflow por um modal com organograma clicável. Componente reusável [components/UnidadePicker.tsx](frontend/components/UnidadePicker.tsx): trigger button (mostra nome+sigla da unidade atual ou placeholder), abre Dialog `size=lg` (max-w-3xl) com mesma árvore React Flow do `/organograma` (layout DFS centralizado), nodos clicáveis (1 click = seleciona + fecha), botão "Sem unidade" no footer pra limpar. Carrega organograma sob demanda (`enabled: open` no useQuery). Usado em `<WorkflowEditPanel>` substituindo o `<select>` de unidades. |
| 24 | Auditoria + busca global. **Auditoria**: migration 0014 cria `aprimora_py.audit_log` append-only com RLS (policies só SELECT+INSERT — imutável por design). Service [services/audit.py](backend/app/services/audit.py) com `log(db, *, tenant_id, id_usuario, acao, entidade, id_entidade, payload, request)` que captura `request_id` (Fase 33) e `ip` (x-forwarded-for) automaticamente. NÃO comita — caller controla transação (atômica). Integrado em `abertura_processo.abrir_processo`, `acoes_processo.encaminhar` e `acoes_processo.receber` (mais hooks podem ser adicionados sem mudança de schema). Endpoint `GET /api/v2/audit?acao=&entidade=&id_entidade=&id_usuario=&desde=&ate=&page=&page_size=` retorna paginado com JOIN em `utils.usuario` pra trazer `nome_usuario`. Página [/auditoria](frontend/app/(app)/auditoria/page.tsx) com filtros (Aplicar/Limpar), tabela com badge intent por verbo (`success` pra criado, `danger` pra excluido/cancelado, `info` pra encaminhado/recebido, `warning` pra workflow), payload colapsável (`<details>`), paginação Prev/Next. Link Sidebar "Auditoria" no grupo Geral. **Busca global**: endpoint `GET /api/v2/busca?q=...` (mín 2 chars) faz 3 ILIKE em paralelo: `Processo.numero_processo`, `Manifestante.nome|cpf_cnpj`, `Usuario.nome|email`, retorna até 8 por bucket. Componente [`<BuscaGlobal>`](frontend/components/BuscaGlobal.tsx) no Header (centro): input com debounce 300ms, dropdown 3 buckets com ícone (FileText/UserCircle/User), atalho `/` foca + `Esc` fecha, clique navega pra entidade. Smoke validou: `?q=P0` retornou 8 processos, `?q=admin` retornou usuário `Usuário Local`. Rotas `auditoria` e `busca` adicionadas à regex nginx. |
| 23 | Heatmap por unidade no organograma. Frontend-only — `/organograma` ganha 4 botões no header (`Sem heatmap`/`Processos ativos`/`SLA pendentes`/`Tempo médio (30d)`). Quando uma métrica está ativa, cada nó tem background colorido por gradient HSL `hue 120 (verde) → 0 (vermelho)` normalizado pelo MAX da árvore — interpolação no espaço de cor, não no valor (evita perder contraste em distribuições skewed). Legend horizontal embaixo da linha de ícones mostra a escala com o `máx` numérico. Card do nó preserva o conteúdo (KPIs em grid 2×2) — só o fundo muda. Sem backend novo: endpoint `/organograma` já retornava as 3 métricas desde a Fase Organograma. Polling 60s continua atualizando. |
| Organograma | Visualização gráfica da estrutura organizacional. Backend [services/organograma.py](backend/app/services/organograma.py) com `tree(db, tenant_id)` que faz 5 queries paralelas (lista unidades + 4 agregações: processos ativos via `id_local_atual`, usuários via `id_unidade_trabalho`, alertas SLA via join Alerta→Instance→Processo, tempo médio via `AVG(NOW() - data_hora_movimentacao)` nos últimos 30d). Endpoint `GET /api/v2/organograma` retorna lista plana com `id_unidade_pai` — frontend monta árvore. Página `/organograma` em React Flow com layout top-down DFS (pais centralizados sobre filhos), nodos customizados com 4 KPIs em grid 2x2 (FileText/Users/AlertTriangle/Clock), polling 60s, click no nó destaca + mostra detalhes. Link "Organograma" no Sidebar grupo Geral. Smoke: endpoint retornou tree com KPIs do tenant Sobral, página compila 200 com chunk contendo `layoutTree`+`xyflow`. |
| WF↔Org | Workflow ↔ unidades da estrutura organizacional. `WorkflowEstado` ganha `id_unidade_responsavel` no DSL. `executar_transicao` faz auto-encaminhamento programático (cancela pendentes pra outros destinos, cria Movimentacao + Encaminhamento, atualiza `processo.id_local_atual`) quando o estado destino tem unidade ≠ local atual. `transicoes_disponiveis(usuario=...)` filtra transições cujo destino exige unidade ≠ `usuario.id_unidade_trabalho` (admins sem lotação veem tudo). Frontend: dropdown "Unidade responsável" no painel do estado do editor; badge `🏢 <nome>` no nodo de cada estado; hint "→ será encaminhado pra unidade #X" no painel do processo. Smoke E2E confirmou transição `aberto→analise(unid=7)` move `processo.id_local_atual` 3→7 e cria registro em `protocolos.encaminhamento`. |
| 22 UX | Fix de usabilidade do workflow após feedback ("confuso e difícil"). Connect-to-create agora tem 2 caminhos: drag dos **handles visíveis** (CSS global aumenta para 12px azul) ou **Shift+click origem → Shift+click destino**. Tooltip "Como usar" no toolbar do editor lista atalhos. UI de mapeamento `tipo_processo → workflow` embedada na página do WF (`<WorkflowMapeamentoTipos>`) — lista todos os tipos do tenant com botões Vincular/Desvincular/Substituir, antes só via API. Botão **Iniciar manualmente** no card Workflow do processo quando não tem instance — select dos WFs ativos + chamada `POST /workflow-instances`. Guia 3-passos (criar→vincular→abrir processo) em `/workflow` como `<details>` colapsável. |
| 16 | WhatsApp via Zenvia. Migration 0013 (idempotente) garante `utils.usuario.telefone`. `Destinatario` ganha `telefone` opcional; `enviar()` resolve telefone via `utils.usuario.telefone` quando vier só `id_usuario`. Driver `_whatsapp_driver` plugável por `WHATSAPP_PROVIDER` env: `stub` (default, só loga) ou `zenvia` (POST httpx em `ZENVIA_API_URL` com `X-API-TOKEN` header + body `{from, to, contents:[{type:text,text}]}`). Sem credenciais → erro útil. Endpoints `GET/PUT /api/v2/notificacoes/telefone` (do usuário corrente) e `POST /whatsapp-test` (envia mensagem livre pro telefone informado, retorna `provider` e status). Task SLA agora passa `canais=["in_app","email","whatsapp"]` — filtragem por preferência (17b), por falta de endereço (email/telefone vazio) e por config (provider stub ainda é "enviado" — só loga). Frontend `/perfil/notificacoes`: campo telefone com validação client-side regex `^\+?[1-9]\d{7,14}$`, botão Salvar (mutate `PUT /telefone`), botão "Enviar teste" (FlaskConical) que chama `whatsapp-test`. Toggle WhatsApp ativo só quando telefone está cadastrado. Smoke validou pipeline completo: ligando preferência whatsapp + cadastrando telefone, SLA dispatch criou **3 notificações simultâneas** (in_app/email/whatsapp), todas com `enviado_em` populado e sem erro. **Provider Zenvia real depende de credenciais de homologação** — config via env mas sem teste de integração real. |
| 17b | Preferências de notificação por usuário + driver SMTP real. Migration 0012 cria `notificacao_preferencia` (toggles canal_in_app/email/whatsapp, defaults sensatos). Service `enviar()` filtra cada (destinatário×canal) por preferência — usuário interno sem row usa defaults; email livre nunca filtra. Driver email: se `SMTP_HOST` env setado → `aiosmtplib.send()` com STARTTLS opcional + auth user/pass; senão continua stub log. Helpers `get_preferencia()` / `set_preferencia()` (upsert) no service. Endpoints `GET /api/v2/notificacoes/preferencias` (sempre retorna struct, default se sem row) e `PUT /preferencias` (PATCH-style, campos None mantêm valor). API client TS `notificacoesApi.getPreferencias/setPreferencias`. Página `/perfil/notificacoes` com 3 toggles (Bell/Email/WhatsApp), WhatsApp desabilitado (Fase 16). Link no /perfil. Smoke validou opt-out: `in_app=false` faz task SLA criar alerta (esperado) mas pular notif (esperado). Dependência nova: `aiosmtplib==3.0.2` no pyproject. |
| 18c | Exportação do dashboard em CSV e PDF. Backend: [services/dashboard_export.py](backend/app/services/dashboard_export.py) com `to_csv(payload, nome_tenant)` (multi-seção: header `#`, depois `[Volume]`, `[Conclusão]`, `[SLA]`, breakdowns e série temporal — deltas pré-calculados como `+800.0%`/`+∞`) e `to_pdf(payload, nome_tenant)` (reportlab Platypus, A4 vertical, grid 3×2 de cards KPI com tendência colorida verde/vermelho, tabelas dos top 5/10 com ZebraStrip, padrão visual igual aos relatórios da Fase 6). Endpoints `GET /api/v2/dashboard/export.csv?periodo&id_unidade` (`text/csv; charset=utf-8` com BOM pra Excel-PT) e `.pdf?...&inline=true`. Frontend: bloco "Exportar" no header do `/dashboard` com 2 botões `PDF`/`CSV` (lucide `FileText`/`FileSpreadsheet`) que respeitam os filtros atuais (período + unidade). Smoke validou via nginx: PDF 2678 bytes `application/pdf` magic `%PDF-1.4`, CSV 899 bytes com seções e BOM. |
| 18b | Dashboard com filtros + comparativo. Backend: service `_counts_intervalo(desde, ate)` extraído pra rodar 2x (período atual + período anterior do mesmo tamanho). Payload ganha bloco `comparativo` com contadores `*_anterior` pra todos os KPIs janelados (abertos, externos, sigilosos, arquivados, taxa, tempo médio, SLA resolvidos). KPIs snapshot (ativos_hoje, sla.pendentes) ficam sem comparativo. Frontend: `<UnidadePicker>` no topo do dashboard (todas as unidades = null), aceita filtro em todos os queries. Cada `<KpiCard>` ganha props `current/previous/lowerIsBetter/comparePctPoints` e renderiza `<TrendBadge>` com seta `↑`/`↓`/`–` em verde/vermelho conforme regra (queda do tempo médio = bom). Smoke validou: payload retornou `comparativo.abertos_anterior=1` vs `volume.abertos_periodo=9` → delta calculado +800%, página compila 200, chunk tem `TrendBadge` + `UnidadePicker`. |
| 18a | Dashboard executivo (BI). Endpoint `GET /api/v2/dashboard/kpis?periodo=7|30|90|365&id_unidade=...` retorna payload com KPIs de volume (abertos no período, ativos hoje, externos, sigilosos), conclusão (arquivados, taxa, tempo médio em dias via `Movimentacao WHERE id_arquivamento IS NOT NULL` — `Arquivamento` não tem FK direta a `Processo`), SLA (pendentes/resolvidos), e breakdowns top N por tipo_processo (5), assunto (10) e unidade (10), além de série temporal de abertos por dia. Frontend instala `recharts@3` e tem página `/dashboard` com seletor de período (chips 7/30/90/365), 6 cards KPI grandes (FileText/TrendingUp/CheckCircle2/Clock/AlertTriangle ícones com intent colors), LineChart pra série temporal, PieChart pra tipo_processo, BarChart horizontal pra unidade e assunto. Polling 60s. Link no Sidebar (grupo Geral) + rota `dashboard` na regex nginx. **Gotcha PG resolvido**: `GROUP BY date_trunc('day', ...)` falhava porque Postgres bind o literal `'day'` em params diferentes pra SELECT vs GROUP — usei `literal_column("1")` (ordinal) em GROUP BY/ORDER BY. |
| P3 Portal Cidadão | Wizard de protocolo no portal — Fase P3 do plano. Backend [services/cidadao_processos.py](backend/app/services/cidadao_processos.py) `abrir_processo_cidadao` ganhou: rate-limit anti-spam (max 5 aberturas em 24h por CPF no tenant, conta `canal_entrada='portal'`), carimba `canal_entrada='portal'` + `data_recepcao=now`, valida `id_especie_documental` opcional contra subset exposto ao portal (`REQUERIMENTO/PETICAO/DECLARACAO`), chama `sugerir_ccd_por_assunto` (P4) com `id_assunto + corpo` e auto-classifica CCD quando score ≥ 0.3, gera NUP via `gerar_nup` quando tenant tem `usar_nup_federal=true` + `codigo_orgao_nup` (P2). `get_meu_detail` agora retorna anexos públicos não-desentranhados + nome da espécie + código/nome do CCD. Novos endpoints em [routers/cidadao.py](backend/app/routers/cidadao.py): `GET /cidadao/especies` (lista subset do portal) e `POST /cidadao/processos/{id}/anexos` (upload multipart, valida ownership do cidadão via CPF/CNPJ do manifestante, sempre `publico=true`, `id_usuario=NULL`, reusa `upload_anexo` do service existente — assinatura relaxada para `usuario_id: int | None`). Frontend: [`/cidadao/abrir`](frontend/app/cidadao/abrir/page.tsx) reescrito como **wizard 3 passos** com indicador stepper (círculos numerados + linhas conectoras, check verde ao concluir), passo 1 (Dados: Select assunto + chips espécie + Textarea corpo + observação), passo 2 (Documento: dropzone com `<label>` para arquivo + preview com ícone FileText + remover, validação client-side de extensão + tamanho ≤25MB), passo 3 (Confirmação: dl revisando todos os dados). Submit faz `POST /processos` + se há arquivo `POST /processos/{id}/anexos`. Detalhe [`/cidadao/processos/[id]`](frontend/app/cidadao/processos/[id]/page.tsx) mostra NUP como identificador principal (cai em legacy quando ausente), badge da espécie, linha "Classificação documental" com código+nome, novo card "Anexos" com FileText + descrição + qtd_paginas. Lista [`/cidadao/processos`](frontend/app/cidadao/processos/page.tsx) exibe NUP quando disponível. Tipos `CidadaoEspecie`/`CidadaoAnexo` + métodos `api.cidadao.especies/uploadAnexo` em `lib/api.ts`. **Pendente:** captcha externo (hCaptcha/Turnstile) e notificação email/WhatsApp por movimentação. |
| P6 Apensamento+ | Apensamento + Desentranhamento + Volumes — Fase P6 do plano de Protocolo (paridade PHP). Migration 0018: cria `protocolos.processo_apensamento` (log com motivo + usuário, índice parcial único `id_processo_apensado WHERE desapensado_em IS NULL` garante 1 apensamento ativo por filho), adiciona 4 colunas em `protocolos.anexo_processo` (`desentranhado_em`, `id_usuario_desentranhamento`, `motivo_desentranhamento`, `autoridade_desentranhamento`), cria `protocolos.processo_volume` (numeração unique por (tenant, processo), CHECK pagina_final≥pagina_inicial). Models [apensamento.py](backend/app/models/apensamento.py) + colunas adicionadas em Processo/AnexoProcesso. Services: [apensamento.py](backend/app/services/apensamento.py) com **validação anti-ciclo** walk ancestor chain (pai não pode ser descendente do filho); [desentranhamento.py](backend/app/services/desentranhamento.py) marca `desentranhado_em` sem deletar arquivo + atualiza filtro `_load_anexos` pra esconder desentranhados da listagem do detail; [volumes.py](backend/app/services/volumes.py) CRUD com validação de duplicidade e ranges. 3 PDFs formais em [pdf_termos.py](backend/app/services/pdf_termos.py): termo de apensamento, desapensamento e desentranhamento, todos com banda preta + accent brand, tipografia hierárquica (Courier para identificadores, Helvetica para corpo), linha de assinatura tracejada cartorial, serial number rastreável no rodapé + advertência de valor probatório Lei 11.419/2006. 10 endpoints novos em [routers/processos.py](backend/app/routers/processos.py): `POST /{id}/apensar`, `POST /{id}/desapensar`, `GET /{id}/apensamentos` (histórico) + `GET /{id}/apensados` (filhos ativos), `GET /apensamentos/{id}/termo.pdf` (rota inteligente — gera termo de apensamento OU desapensamento conforme estado), `POST /{id}/anexos/{ap_id}/desentranhar` (gated `processo.excluir`) + `GET .../termo-desentranhamento.pdf`, e CRUD `/{id}/volumes`. Audit logs em todas operações. Frontend: 3 componentes — [ProcessoApensados](frontend/components/ProcessoApensados.tsx) com **árvore visual** (linha vertical de tronco + ramos horizontais com nó circular brand no encontro, último item com gradient pra ocultar trecho final) + dialog de apensar com Combobox filtrado, separação clara entre vínculos ativos e histórico colapsável; [ProcessoVolumes](frontend/components/ProcessoVolumes.tsx) com **lombadas de livro** estilizadas (faixa lateral 12mm gradient brand → brand/70, texto `VOL 01` rotacionado 180° vertical, dados à direita); [AnexoDesentranhar](frontend/components/AnexoDesentranhar.tsx) com **modal severo** (header danger + ícone AlertTriangle, footer com nota "audit + termo PDF gerados", botão "Desentranhar" em cor danger). `apensamentoApi`/`desentranhamentoApi`/`volumesApi` em `lib/api.ts`. Filtro de anexos desentranhados aplicado em ProcessoDetail. Smoke E2E backend: apensar 22→21 OK, listar retorna filho com NUP+manifestante, **bloqueio de ciclo** "Apensamento criaria ciclo: o processo pai é descendente do filho" → 400, desapensar marca + libera novo apensamento, termo apensamento 2821b + desapensamento 2786b + desentranhamento 3001b, volumes 1/2/3 criados sequencialmente + duplicidade bloqueada. Detalhe `/processos/21` retorna 200. |
| P2 NUP federal | Número Único de Protocolo (Decreto 8.539/2015) — Fase P2 do plano de Protocolo. **Opt-in por tenant** via flag `usar_nup_federal`. Formato `NNNNN.NNNNNN/AAAA-DD` (5 dígitos órgão SIORG + 6 sequencial + 4 ano + 2 DVs Mod-11). Migration 0017: adiciona `aprimora_py.tenant.codigo_orgao_nup` (com CHECK regex `^[0-9]{5}$`) + `usar_nup_federal` (default FALSE), cria `aprimora_py.nup_sequencia` (counter atômico por (tenant, órgão, ano)) com RLS, adiciona `protocolos.processo.nup` + `numero_sequencial_orgao` com **unique index parcial global** em `nup WHERE NOT NULL`. Service [services/nup.py](backend/app/services/nup.py): `calcular_dvs_nup()` (Mod-11 com pesos cíclicos 2..9 + 2 DVs DV1/DV2), `formatar_nup()`, `validar_nup()` (parse + recompute DVs), `gerar_nup()` (UPSERT atômico via `INSERT ... ON CONFLICT DO UPDATE RETURNING` — concorrência segura sem `SELECT FOR UPDATE`). Integração em `abertura_processo.abrir_processo`: ANTES do commit, se tenant tem `usar_nup_federal=true` E `codigo_orgao_nup` definido, gera NUP na mesma transação. Falha não bloqueia abertura — registra audit `processo.nup_falhou`. Endpoint `PUT /api/v2/tenants/me/nup-config` (gate `usuario.atualizar`) com validação: não permite ativar flag sem código. PDFs ([pdf_protocolo.py](backend/app/services/pdf_protocolo.py)): quando NUP presente, vira identificador principal (banner "NUP FEDERAL · APRIMORA", barcode usa NUP, numero_processo cai pra "Legado: …" abaixo). Frontend: [`/configuracoes`](frontend/app/(app)/configuracoes/page.tsx) com input código 5 dígitos (input numérico mascarado) + toggle NUP + preview do formato + bloqueio "ativar sem código"; badge "Ativo" quando flag ligada. `tenantsApi.updateNupConfig()` em `lib/api.ts`. Listagem `/processos` mostra NUP em cima do número legado quando preenchido. Detalhe `/processos/[id]` exibe NUP no título (font-mono) + "Legado: P000017/2026" como subtítulo. SuccessCard do balcão idem. Sidebar "Configurações" em Administração + nginx regex. Smoke E2E backend: PUT nup-config → activated, POST /balcao → P000017 + `99001.000001/2026-80`, validar_nup gera/valida (adulterado=false), 3 protocolos paralelos → sequenciais 2,3,4 sem race (UPSERT atômico testado). PDFs: etiqueta 2707b (vs 2462b sem NUP) + comprovante 3562b (vs 3347b). 4 páginas frontend retornam 200. |
| P4 CCD+TTD | Classificação documental + Temporalidade — Fase P4 do plano de Protocolo. Migration 0016 cria `protocolos.ccd_classe` (taxonomia hierárquica auto-referente, `palavras_chave` CSV pra sugestão automática) + `protocolos.ttd_regra` (1 regra por classe+espécie via unique index parcial; `destino_final` ENUM-via-CHECK `ELIMINACAO|GUARDA_PERMANENTE`) + adiciona `processo.id_ccd_classe`. Seed: 22 classes CONARQ atividades-meio (000 Adm geral → 070 Comunicações com sub-níveis 010/021/031/041/051/052/053…) + 14 regras TTD comuns (cadastro funcional = guarda permanente, folha de pagamento = 100 anos previdência, compras = 10 anos, almoxarifado = 5 anos). Models [CcdClasse + TtdRegra](backend/app/models/ccd.py). Service [services/temporalidade.py](backend/app/services/temporalidade.py): `calcular_temporalidade(processo_id)` resolve regra com fallback na hierarquia (classe → catch-all → pai → pai do pai) e calcula `fim_fase_corrente`/`fim_fase_intermediaria` (1 ano = 365 dias) + `destino_final`. `sugerir_ccd_por_assunto()` tokeniza assunto (NFD strip accents + stopwords PT) e ranqueia classes por overlap com `nome + palavras_chave`. Router [routers/protocolo.py](backend/app/routers/protocolo.py) ganhou 11 endpoints: CRUD `ccd-classes` + `ccd-classes/tree` (aninhada) + CRUD `ttd-regras` + `GET /sugerir-ccd?id_assunto&texto` + `GET /vencendo-prazo?dias&incluir_permanentes` (calcula temporalidade em memória — todo: virar job pra escala). `ProtocoloBalcaoRequest` aceita `id_ccd_classe` opcional. Endpoint `GET /processos/{id}/temporalidade` em [routers/processos.py](backend/app/routers/processos.py). Ciclo bloqueado no PUT de classe (walk ancestor chain) + delete bloqueado se há filhos. Frontend: 3 páginas novas — [`/protocolo/ccd`](frontend/app/(app)/protocolo/ccd/page.tsx) (árvore expand/collapse com `expanded: Set<number>` + form lateral edit/create com Combobox de pai), [`/protocolo/ttd`](frontend/app/(app)/protocolo/ttd/page.tsx) (lista filtrável por classe com badges intent por destino), [`/protocolo/vencendo-prazo`](frontend/app/(app)/protocolo/vencendo-prazo/page.tsx) (relatório com select de janela 6m/12m/2a/5a/10a, indicador urgente <365d, link pro processo). `/protocolo/balcao` ganhou campo CCD com sugestão automática debounced 300ms ao escolher assunto — chips clicáveis mostram codigo+nome+score%. Sidebar links em "Geral" (Vencendo prazo) + "Catálogos" (CCD/TTD). `ccdApi`/`ttdApi`/`temporalidadeApi` em `lib/api.ts`. Smoke E2E: árvore retornou 22 classes em 3 níveis, sugerir por id_assunto=5 (Aquisição licenças) → classe 031 score 0.333, P000015 com CCD=031 → temporalidade calculada `fim_fase_intermediaria=2036-05-24 ELIMINACAO`, /vencendo-prazo?dias=3650 retornou 2 processos. Todas as 4 páginas frontend compilam 200 (CCD 33123b, TTD 33123b, vencendo-prazo 33233b, balcao 33708b). |
| P1 Balcão | Protocolo de balcão — primeira fase do módulo de Protocolo (PROTOCOLO-PLAN.md). Migration 0015 cria `protocolos.especie_documental` (catálogo tenant-scoped, RLS, seed de 10 espécies: Ofício, Requerimento, Memorando, Declaração, Petição, Carta, Relatório, Edital, Certidão, Outros) + adiciona `id_especie_documental`/`canal_entrada`/`data_recepcao` em `protocolos.processo` (backfill `canal_entrada='interno'` para processos existentes). Model [EspecieDocumental](backend/app/models/especie_documental.py). Service [services/protocolo.py](backend/app/services/protocolo.py) `abrir_protocolo_balcao()` reusa `abertura_processo.abrir_processo` (numeração PG + WF auto-instanciação + audit `processo.aberto`) e carimba os 3 campos novos + audit adicional `processo.protocolado_balcao` com payload completo (espécie, canal, data_recepcao). Router [routers/protocolo.py](backend/app/routers/protocolo.py): CRUD `GET/POST/PUT/DELETE /api/v2/protocolo/especies-documentais` (gated por `catalogo.*`) + `POST /api/v2/protocolo/balcao` (gated por `processo.inserir`) + 2 PDFs: `GET /api/v2/protocolo/{id}/etiqueta.pdf` (etiqueta Pimaco 6182 com banda colorida, espécie destacada, código Code128 do número, recepção + canal + manifestante) e `GET /api/v2/protocolo/{id}/comprovante.pdf` (2 vias na mesma folha A4 separadas por linha tracejada de corte: "VIA DO MANIFESTANTE" + "VIA DA UNIDADE", cada uma com número + barcode + dados completos + linha de assinatura). Service [services/pdf_protocolo.py](backend/app/services/pdf_protocolo.py) com `gerar_etiqueta_protocolo()` e `gerar_comprovante_protocolo()`. Frontend: [`/protocolo/balcao`](frontend/app/(app)/protocolo/balcao/page.tsx) com layout single-screen otimizado pra digitação rápida — espécie como chips de seleção horizontal, Combobox manifestante (CPF/CNPJ), Combobox assunto, UnidadePicker (default na unidade do user), toggle sigiloso, atalho **Ctrl+Enter** pra protocolar. Após sucesso, card grande com `numero_processo` + 4 botões: "Protocolar próximo" (reset e foca manifestante), "Etiqueta" + "Comprovante (2 vias)" (abrem PDF em nova aba via `target="_blank"`), "Ver processo". Sidebar "Protocolo (Balcão)" grupo Geral. Histórico de protocolos da sessão (localStorage, max 8). nginx regex ganhou `protocolo`. Smoke E2E: protocolei P000014/2026 (Requerimento, manifestante 4) e P000015/2026 (Ofício, ACME) com etiqueta 2468b + comprovante 3344b PDFs válidos; 2 entries em audit_log por processo (`processo.aberto` + `processo.protocolado_balcao`). |
| Strict mode WF | Workflow obrigatório (opt-in por workflow via `dsl.strict: bool`). Backend bloqueia ações fora do trilho: `validar_acao_strict()` em [services/workflow_integration.py](backend/app/services/workflow_integration.py) — `encaminhar` exige `id_unidade_destino` bater com `id_unidade_responsavel` de estado alcançável via transição manual/encaminhamento; `receber`/`cancelar` bypass; `arquivar` só em estado final. Nova exceção `WorkflowStrictBlock` em [services/acoes_processo.py](backend/app/services/acoes_processo.py) com `is_super_usuario` + `override_motivo` (super-user pode quebrar com motivo, registrado em `audit_log` como `processo.encaminhar.override_strict` + `bloqueio_original`). Helper `_is_super()` em [routers/processos.py](backend/app/routers/processos.py) detecta via `load_permissions().is_super_usuario`. `EncaminharRequest`/`CancelarEncaminhamentoRequest` ganharam `override_motivo: str | None`. Frontend: `ProcessoWorkflowPanel` mostra badge **"Fluxo obrigatório"** (warning intent) + warning box quando `defQ.data.dsl.strict`. Smoke E2E: usuário sem permissão recebe 400 com motivo do bloqueio, super-user com `override_motivo` recebe 200 + entry de auditoria. Workflow `aquisicao-bens-consumo` v3 ativo com strict=true. |
| Permissões granulares | Gating de endpoints por transação (`codigo`) + ação (`inserir`/`atualizar`/`excluir`). Módulo [auth/perms.py](backend/app/auth/perms.py) com factory `require_permission(codigo, action)` baseada em `permissoes.load_permissions()` que retorna `is_super_usuario` (nivel.valor==0 bypass) + união de `grupo_transacao` com flags por grupo. Aplicado em ~51 endpoints de 10 routers: `usuarios.py` (`usuario.*`), `manifestantes.py` (`manifestante.*`), `assuntos.py` (`catalogo.*` + `assunto.*`), `localizacao.py` (`cidade.*`+`endereco.*`), `grupos.py` (`usuario.atualizar`), `processos.py` (`processo.*`), `anexos.py` (`processo.atualizar/excluir`), `assinaturas.py` (`processo.atualizar`), `unidades.py` (`unidadeTrabalho.*`), `workflow.py` (`workflow.*`). Frontend: `useAuth().can(codigo, action)` esconde botões/callbacks em UI quando sem permissão (ex: organograma `onEdit={canUpdate ? openEdit : undefined}`). 403 com texto explicativo `Sem permissão de '<acao>' em '<codigo>'`. |
| Organograma editor | Overhaul visual do organograma (`/organograma`) com edição completa via drag-and-drop. Novos componentes: [`UnidadeEditDrawer`](frontend/components/organograma/UnidadeEditDrawer.tsx) (form com Combobox pai + Select tipo, validação de ciclo via `getInvalidParents` excluindo self+descendants), [`OrganogramaListView`](frontend/components/organograma/OrganogramaListView.tsx) (tree compacta com chevron expand/collapse, drag handle `GripVertical`, drop targets glow verde, ancestor inválido fade 40%), [`OrganogramaDiagramView`](frontend/components/organograma/OrganogramaDiagramView.tsx) (React Flow com `getIntersectingNodes()` durante drag, hover highlight `border dashed success`, drag-to-root via distância >120px Manhattan, `setResetTick++` força layout recompute). Backend: `_validar_sem_ciclo()` em [routers/unidades.py](backend/app/routers/unidades.py) walk de ancestor chain antes de PUT/PATCH (raise 400 se ciclo). Page orchestrator com view toggle (list/diagram) + collapsed Set + search persistidos em localStorage. Padrão **undo toast** após reparent: `toast.success(...).action({label: "Desfazer", onClick: rollback})`. Permissões granulares: `canInsert`/`canUpdate`/`canDelete` via `useAuth().can("unidadeTrabalho", ...)` escondem callbacks. |
| Aquisição bens | Workflow demo end-to-end para aquisição de bens de consumo (licitação pública). Estados: `dfd_etp_tr` → `juridico` → `verificacao_final` → `compras_cotacao` → `licitacao` → `contratos` → `execucao` (final). Cada estado vinculado a unidade responsável (req/jurídico/compras/licitação/contratos). Versão v3 ativa com `strict=true` — encaminhamentos fora do trilho bloqueados. Smoke: processo P000015 abre na unidade requisitante, transição auto-encaminha pra próxima unidade, super-user testou override registrado em auditoria. |
| Sobral organograma | Carga real do organograma da Prefeitura Municipal de Sobral (https://www.sobral.ce.gov.br/institucional/organograma). 24 secretarias + Prefeitura + PGM como raiz; sub-departamentos típicos inferidos sob SEFIN (Compras/Licitação/Contratos), SEPLAG (TI/RH/Patrimônio) etc. IDs preservaram referências de unidades já apontadas por workflows (id=3=Prefeitura, id=8/9/12=Departamentos sob SEFIN, id=11=PGM, id=20=SEDUC). Workflow Aquisição usa essas unidades reais. |
| Polish UX | Pacote de melhorias UX: (1) [`/processos/novo`](frontend/app/(app)/processos/novo/page.tsx) refatorado em 3 seções com Combobox para manifestante + Tiptap em `corpo` + ToggleCards + auto-save em localStorage; (2) [`RichTextEditor`](frontend/components/ui/rich-text-editor.tsx) com Tiptap minimal (bold/italic/strike/h2/h3/lists/blockquote/link/undo-redo) + `RichTextView` p/ leitura; (3) [`Combobox`](frontend/components/ui/combobox.tsx) searchable com arrow-keys + footer slot; (4) [`LoadingBar`](frontend/components/LoadingBar.tsx) global usando `useIsFetching`/`useIsMutating`+`usePathname`; (5) [`AvatarDropdown`](frontend/components/AvatarDropdown.tsx) absorve theme/density toggles + menu de perfil; (6) `Toast` ganhou prop `action?: ToastAction` para padrão de undo; (7) Sidebar token mais escuro (`--sidebar: 217 22% 86%` light / `222 28% 6%` dark) e prose styles no `globals.css`. |
| 17 | Motor de notificações multi-canal (in-app, email stub, whatsapp reservado). Migration 0011 cria `aprimora_py.notificacao` com RLS. Service [backend/app/services/notificacoes.py](backend/app/services/notificacoes.py) com `enviar(destinatarios, canais, tipo, titulo, mensagem, link_url, payload, prioridade)` que persiste 1 row por (destinatário×canal), despacha externos via drivers plugáveis (email=stub log hoje, prod: aiosmtplib). Erros de envio gravam em `notificacao.erro` sem levantar. Endpoints `GET /api/v2/notificacoes/me` (lista + contador `nao_lidas`), `POST /{id}/marcar-lida`, `POST /marcar-todas-lidas`. Integração na task SLA (Fase 21): ao criar alerta novo, notifica todos os usuários `ativos` cuja `id_unidade_trabalho` == unidade atual do processo, marca `notificado_em` no alerta — dedup via `if not rowcount: continue`. Frontend: `<NotificacoesBell>` no Header com badge contador (polling 30s + refetch on focus), dropdown popover com lista (linha azul=não lida, badge "Alta", link clicável → `link_url`), Marcar todas como lidas. Smoke E2E: SLA disparou notif com `prioridade=alta`, dedup confirmado (2ª verificação não cria 2ª notif), marcar-lida → `nao_lidas` cai a 0. **Preferências por usuário (canais on/off) e driver SMTP real ficam pra 17b**. |

## Cutover

Quando estiver pronto para aposentar o PHP, ver [CUTOVER.md](CUTOVER.md) — checklist passo a passo.

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
