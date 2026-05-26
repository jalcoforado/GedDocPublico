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
| 17 | Motor de notificações multi-canal (in-app, email stub, whatsapp reservado). Migration 0011 cria `aprimora_py.notificacao` com RLS. Service [backend/app/services/notificacoes.py](backend/app/services/notificacoes.py) com `enviar(destinatarios, canais, tipo, titulo, mensagem, link_url, payload, prioridade)` que persiste 1 row por (destinatário×canal), despacha externos via drivers plugáveis (email=stub log hoje, prod: aiosmtplib). Erros de envio gravam em `notificacao.erro` sem levantar. Endpoints `GET /api/v2/notificacoes/me` (lista + contador `nao_lidas`), `POST /{id}/marcar-lida`, `POST /marcar-todas-lidas`. Integração na task SLA (Fase 21): ao criar alerta novo, notifica todos os usuários `ativos` cuja `id_unidade_trabalho` == unidade atual do processo, marca `notificado_em` no alerta — dedup via `if not rowcount: continue`. Frontend: `<NotificacoesBell>` no Header com badge contador (polling 30s + refetch on focus), dropdown popover com lista (linha azul=não lida, badge "Alta", link clicável → `link_url`), Marcar todas como lidas. Smoke E2E: SLA disparou notif com `prioridade=alta`, dedup confirmado (2ª verificação não cria 2ª notif), marcar-lida → `nao_lidas` cai a 0. **Preferências por usuário (canais on/off) e driver SMTP real ficam pra 17b**. |

## Cutover

Quando estiver pronto para aposentar o PHP, ver [CUTOVER.md](CUTOVER.md) — checklist passo a passo.

## Decisões pendentes

- **5.2+ GovBr / AssineJá:** bloqueado por credenciais de homologação.
- **CI/CD:** sem pipeline (ruff/mypy/pytest/playwright em PR seriam bem-vindos).
