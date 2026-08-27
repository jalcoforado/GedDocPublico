# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Idioma: código, comentários, docs e mensagens de commit deste repositório são em **português (pt-BR)**. Mantenha o padrão.

## O que é

Plataforma SaaS multi-tenant de GED/protocolo para prefeituras (piloto: Sobral). Backend **FastAPI + SQLAlchemy 2 async + Postgres**, frontend **Next.js 15 App Router + React 19 + Tailwind**, jobs em **Celery + Redis**, tudo orquestrado por `docker compose` com **nginx** na frente (`:8090`).

Módulos de negócio já entregues: protocolo/processos, anexos, assinatura eletrônica v2, workflow BPM, notificações, auditoria, portal do cidadão, serviços, frota, transporte regulado, pagamentos, minutas (com integração Google Docs), admin de plataforma/tenants.

### Modularização — o sistema é contratável por módulo

Desde 2026-07-30 (fatia F1, `c4dcb53`) o sistema é dividido em **cinco módulos contratáveis** —
`protocolo`, `pagamentos`, `frota`, `transporte`, `administracao` — mais `comum`, que não é
contratável e nunca é bloqueado. O catálogo é global (`aprimora_py.modulo`, `modulo_transacao`); a
contratação é por tenant (`aprimora_py.tenant_modulo`, **sem RLS** por decisão: é tabela de
plataforma, escrita pelo platform admin operando sobre outros tenants). Como não há RLS, o `GRANT`
é a única barreira, e desde a migration `0079` (`SEC-RLS-00C`) o papel do runtime municipal
(`aprimora_app`) tem **só `SELECT`** ali — quem contrata é o papel de plataforma. Por isso
`provisionar_tenant` é **dois atos** com sessões distintas
(`app/services/provisioning_tenant.py`): mexer nele sem ler aquele docstring quebra o onboarding.
Esse `REVOKE` só passa a valer no dia em que `APP_DATABASE_URL` for definida — enquanto ela estiver
vazia o runtime conecta como `ged_user` (`BYPASSRLS`) e nenhuma revogação da família `SEC-RLS-*`
tem efeito. A troca é o gate humano `SEC-RLS-ROLLOUT`, não um passo de PR.

Cada módulo declara os códigos de `utils.transacao` que lhe pertencem (o mapa vive em
`app/cli/seed_bootstrap.py::MODULO_TRANSACOES`). Transação de módulo não contratado entra no
conjunto de bloqueados e o gate nega — em `auth/perms.py`, **antes** do bypass de super-usuário. Um
SU de tenant sem o módulo leva 403 igual a qualquer um; isso é deliberado e tem teste.

Três coisas a não quebrar ao mexer nisso:

- **Fail-open é intencional.** Transação **sem** vínculo de módulo NÃO é bloqueada. O esquecimento
  aparece como teste vermelho (`tests/test_guarda_modularizacao.py`, `tests/test_transacoes_rbac.py`)
  e não como tela sumida em produção. Não "conserte" isso para fail-closed.
- **Transação nova precisa de módulo.** Criou código em `utils.transacao`? Declare-o em
  `MODULO_TRANSACOES`, senão a guarda reprova o PR.
- **Contratação em banco limpo vem do seed.** O backfill da 0073 só alcança tenants que já existiam;
  em banco novo quem contrata é `seed_bootstrap` (e `ci/seed-e2e.sql`, porque o
  `e2e-assinatura.yml` **não** roda o seed_bootstrap). Sem isso o tenant sobe com zero módulos e o
  sistema inteiro dá 403.

Desde 2026-07-30 (fatia `leitura-por-modulo`, `5c47729`) a leitura também é gateada por
contratação: `require_modulo(slug)` (`auth/modulos.py`) barra 69 GETs (58 `protocolo`, 11
`administracao`; 7 permanecem transversais, sem gate, com a razão registrada em
`tests/test_guarda_modularizacao.py::ENDPOINTS_LEITURA_SEM_GATE`). Diferença essencial para
`require_permission`: **`require_modulo` não olha o usuário** — não consulta grupo, transação nem
nível. Um usuário sem nenhuma permissão continua lendo o que lê hoje, desde que o tenant tenha o
módulo contratado. Não "melhore" essa dependência para também checar permissão sem falar com o
Jorge antes — mudaria política de acesso, e há teste (`test_usuario_sem_permissao_continua_lendo`)
que trava essa propriedade.

A outra metade — "este usuário pode ler isto?" — foi fechada em 2026-08-11 pelo item 1.0.8: 58 GETs
ganharam `require_permission("<codigo>")` **sem `action`**, somando ao gate de módulo. Ficam livres,
por decisão registrada em `LEITURA_SEM_PERMISSAO_DECIDIDA`, só os catálogos de formulário e as rotas
de si-mesmo. **GET novo nasce exigindo transação** — `test_leitura_sem_permissao_nao_cresce_sem_decisao`
reprova o contrário, e a isenção pede razão escrita ao lado da entrada.

Duas consequências que valem lembrar antes de mexer em permissão:

- **A fatia entrou inerte, e isso não é o estado permanente.** Todo grupo é super-usuário hoje, e o
  SU passa por cima do gate. Quem criar o primeiro grupo não-SU precisa conceder a **leitura**
  também — inclusive `unidadeTrabalho` e `usuario`, que alimentam telas de *protocolo*. Conjunto
  sugerido no `RUNBOOK.md`; `app.cli.diagnostico_permissoes` mostra o que falta.
- **`require_permission` é o terceiro eixo, não o único.** Continua valendo que módulo
  (`require_modulo`) e sigilo (`assert_acesso_processo`) são independentes dele; nenhum substitui
  outro.

### A interface (fatia F2, PR #17, em `main` desde 2026-07-31)

Até aqui a modularização era invisível: a Sidebar mostrava o menu inteiro e o usuário só descobria
que não tinha o módulo ao clicar e tomar 403. A F2 é a fatia que o **usuário vê**.

- **`frontend/lib/menus/`** — o `NAV` monolítico da Sidebar virou seis arquivos, um por módulo
  (`protocolo`, `pagamentos`, `frota`, `transporte`, `administracao`, `comum`). É a **fonte única**
  de navegação: a Sidebar e o Ctrl+K (`CommandPalette`) consomem daqui, e `canSeeItem`
  (`lib/menus/permissoes.ts`) é compartilhado pelos dois — duas cópias divergiriam, e o sintoma
  seria item aparecendo num lugar e não no outro.
- **`frontend/lib/modulos.ts`** — `moduloDoPathname(path)` resolve o módulo ativo a partir da URL.
  É o que a F3 vai reaproveitar para gerar os redirects 308.
- **`/modulos`** — o launcher, em `app/(launcher)/`, layout próprio sem Sidebar. Com **um módulo
  só ele redireciona direto** ("porta, não pedágio").
- O login aterrissa no launcher; `must_change_password` (SEC-1) **tem precedência** e continua indo
  para `/alterar-senha-obrigatoria`.
- **Aba Módulos** no admin de tenant contrata e descontrata por tenant.

Dois filtros independentes governam o menu, e **nenhum substitui o outro**: o módulo escolhe *qual
conjunto* de itens é candidato; a permissão (`perm`/`anyOf`) decide *quais daquele conjunto*
aparecem. Um `perm` perdido não quebra tela — vira item visível para quem não deveria vê-lo. Há
teste que trava isso (`__tests__/menus.test.tsx`, tabela `PERMISSOES_ESPERADAS`).

**O guard de módulo no frontend é UX, não segurança.** A barreira real é o gate de contratação no
backend. Nenhum teste do frontend deve afirmar que ele protege dado.

**Rota de topo nova precisa entrar na regex do `nginx/default.conf`** — sem isso a tela cai no
fallback legado e "não existe" no `:8090`, mesmo funcionando em dev. Quase aconteceu com `/modulos`.

### A F3 (`/m/<slug>`), em `main` desde 2026-08-03

As telas de módulo moram em **`app/(app)/m/<slug>/`**. Na raiz de `app/(app)/` ficam só as
transversais da D5 — `home`, `dashboard`, `perfil`, `para-assinar`. Tela nova de módulo nasce dentro
de `m/<slug>/`; rota de topo fora de `m/` só se for transversal de verdade (agrega *através* dos
módulos), e nesse caso entra em `TRANSVERSAIS` no `__tests__/rotas-modulo.test.ts`.

Três coisas que **não** podem ser desfeitas:

- **A regex do nginx só cresce.** Ela ganhou o token `m` e manteve todos os antigos. Remover
  `processos`, `frotas`, `pagamentos`… faria a URL antiga cair no fallback legado **antes** de
  chegar ao Next — ou seja, mataria o próprio 308 que a mantém viva. Como `notificacao.link_url` é
  registro histórico permanente, os tokens antigos ficam para sempre.
- **`permanent: true` (308) é cache de navegador.** Destino errado que chegue a produção não se
  conserta com redeploy: cada usuário precisa limpar o cache. Confira com `curl -I` antes.
- **`link_url` tem de NASCER com `/m/<slug>/`.** O 308 existe para o que já foi gravado, não para o
  que ainda vai ser: `notificacao.link_url` é registro permanente, e cada linha com prefixo legado
  é um salto extra e uma URL velha na barra, para sempre. `tests/test_guarda_link_url.py` reprova.
- **Prefixo novo em `ROTA_MODULO` exige regra nova em `redirects()`**, e o `href` do menu tem de
  apontar para `/m/<slug>/…`, não para o caminho antigo.

`__tests__/rotas-modulo.test.ts` reprova as três, mais chave órfã em `KEYWORDS_POR_HREF`. Ele existe
porque, durante a F3, a varredura manual por linha contendo `href` falhou **três vezes** — `abrirHref`
(caixa alta), `CHECKLIST_HREF` (mapa, não linha) e `KEYWORDS_POR_HREF` (fora do diretório varrido) —
e **nenhuma das três quebrou teste**. Link errado ainda funciona pelo 308, então o sintoma é salto
extra e URL velha na barra; a chave órfã só piora o Ctrl+K em silêncio.

Desde a P5.2 ele também reprova **página órfã**: toda subpágina sob `app/(app)/m/` tem de ser citada
em algum `href` da app. Tela pronta e sem link não quebra nada — nem build, nem teste — e a P2/P4 do
transporte passou meses assim, alcançável só digitando a URL. Tela nova precisa de caminho até ela
no mesmo PR.

**Essa guarda só passou a valer de verdade na P5.3.** Até lá ela truncava a rota no primeiro
segmento dinâmico, então `/m/transporte/recadastramento/[id]/faltosos` era conferida como
`/m/transporte/recadastramento` — que existe. Na prática **toda página aninhada sob `[param]` estava
isenta**, inclusive a de atendimento da própria P5.2, que a guarda dizia proteger. Ao consertar,
apareceu uma órfã real e antiga: o detalhe do alvará, pronto desde a P3, sem nenhum link. A lição
não é sobre esta guarda — é que **guarda verde só significa alguma coisa depois de invertida**; esta
passou duas fatias sem nunca ter sido.

O nginx nasceu como *Strangler Fig* na frente de um monolito PHP legado. Hoje a versão Python é tratada como **independente** — não portar comportamento do PHP nem consultá-lo como fonte de verdade. O que sobra dessa herança e continua valendo: o schema Postgres é compartilhado com o legado (`utils.*`, `protocolos.*` são tabelas legadas; `aprimora_py.*` e `frota.*` são nossos), e o nginx tem uma regex de rotas migradas (ver "Adicionando um módulo").

## Comandos

**Antes do primeiro `up`:** copie `.env.example` para `.env` (gitignored) e gere a `DADOS_SENSIVEIS_ENCRYPTION_KEY`. É a chave Fernet que cifra tokens OAuth do Google e dados bancários de fornecedor; sem ela o compose aborta de propósito, em vez de subir com um segredo padrão. Trocá-la torna ilegível o que já foi cifrado com a anterior.

```powershell
# Subir tudo (produção-like; frontend em build standalone)
docker compose up -d --build

# Dev com hot-reload do frontend
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Bootstrap de banco novo (schema legado + seeds) — perfil `init`, roda uma vez
docker compose --profile init up bootstrap
```

Containers: `aprimora-py-backend` (publicado em **:8001** pelo override local, :8000 no compose base), `-frontend` (:3100), `-worker`, `-beat`, `-redis`, `-nginx` (:8090), `-db` (:5432). Entrar sempre por `http://localhost:8090` (nginx) — é lá que o roteamento e o header `Host` (resolução de tenant) funcionam.

**Toda porta do compose base é `127.0.0.1:`, menos a 8090.** Até 2026-08-05 não era: `5432`, `8000` e
`3100` subiam em `0.0.0.0` e **respondiam da internet na VPS** — com a senha do banco literal neste
repositório, que é público, e `ged_user` sendo `SUPERUSER`/`BYPASSRLS`. `tests/test_guarda_portas_publicadas.py`
reprova quem republicar em `0.0.0.0`. Duas armadilhas registradas lá e que valem para qualquer
bloqueio futuro: **`ufw` não alcança porta publicada por container** (o Docker desvia do `INPUT` com
DNAT em `PREROUTING`; o bloqueio vai na chain `DOCKER-USER`), e **o DNAT reescreve a porta antes da
`DOCKER-USER`**, então a regra tem de casar a porta de *dentro* do container — foi por isso que a
3100 continuou aberta depois da primeira tentativa, sendo o mapeamento `3100:3000`.

**O `:3100` direto não funciona na stack de produção-like.** O `docker-compose.yml` assa
`NEXT_PUBLIC_API_URL=/api/v2` no bundle — base relativa, que só resolve atrás do nginx. Servido pelo
`:3100`, o próprio Next recebe `/api/v2/...` e devolve 404 no login. Para iterar em `:3100` use o
overlay `docker-compose.dev.yml`, que usa base absoluta.

### Seeds

São **três**, com papéis distintos:

```bash
# 1. Pré-requisitos globais — roda a cada deploy, idempotente. Garante
#    utils.sistema/nivel, o tenant+admin padrão, o segredo JWT e o catálogo
#    protocolos.acao (ABERTURA/ENCAMINHAMENTO/RECEBIMENTO). Sem as ações não
#    se abre nem tramita processo. Garante também o catálogo de módulos e a
#    CONTRATAÇÃO INICIAL do tenant — só quando ele não tem nenhuma linha em
#    tenant_modulo, para não ressuscitar descontratação deliberada do admin.
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

**São três workflows de teste** (`backend-tests`, `frontend-tests`, `e2e-assinatura`), mais o
`deploy-vps`, que **não** é disparado por push: ele espera os três (ver "Deploy"). Os dois que tocam o banco repetem a mesma sequência de bootstrap (stubs → dump → role `aprimora_app` → `alembic stamp 0020` → `upgrade head` → seeds). Corrigiu bootstrap num, verifique o outro.

### Migrations

```bash
docker exec aprimora-py-backend alembic heads          # DEVE ser head único
docker exec aprimora-py-backend alembic current
docker exec aprimora-py-backend alembic upgrade head
docker exec aprimora-py-backend alembic downgrade -1   # valide reversibilidade
```

### Deploy (VPS de homologação)

Merge em `main` **não dispara o deploy direto**. Desde 2026-08-04, `deploy-vps.yml` roda por
`workflow_run` **depois** do `Backend tests`, e um job `gate` confere por API se `Frontend tests` e
`E2E assinatura` também fecharam em `success` **no mesmo SHA**. Antes disso os quatro corriam em
paralelo e a VPS recebia código reprovado — aconteceu em `a1a0c8e`. Consequências práticas:

- **O deploy demora ~8 min a mais**, porque espera a suíte. Não é lentidão nova, é a espera que
  faltava.
- **Um workflow só no gatilho, e é de propósito.** `workflow_run` com vários dispara uma vez *por
  workflow que termina*, não uma vez quando todos terminam — dois deploys simultâneos seriam
  piores, e `cancel-in-progress` cortaria um deploy pela metade.
- **O filtro `paths:` saiu** (o gatilho não aceita filtro de caminho), então push só de
  documentação também deploya. Build desperdiçado é barulhento; deploy que não acontece é
  silencioso.
- **Renomear um workflow de teste barra TODO deploy, em silêncio** — o portão procura por nome.
  `tests/test_guarda_portao_de_deploy.py` reprova quem esquecer.
- **`workflow_dispatch` passa direto pelo portão**, e continua sendo o escape manual.

O `deploy.sh` roda `scripts/deploy.sh start` por SSH. Duas armadilhas custaram várias rodadas de diagnóstico:

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
- `auth/` — `deps.py` (`get_current_user`, `get_current_cidadao`, `require_tenant_id`), `perms.py` (`require_permission(codigo, action)`), `jwt.py` (HS256/RS256), `password.py` (bcrypt; MD5 legado só de **leitura** — nada grava, e o login converte a linha e apaga o MD5 no primeiro uso. `SENHA_MINIMA` é o piso único de senha nova; `tests/test_guarda_md5.py` reprova quem voltar a gravar), `plataforma.py` (`require_platform_admin`, ver abaixo).
- **A fronteira de plataforma é outro realm, e não se mistura com `deps.py`.** Desde `SEC-01A` (ADR-016) as 8 rotas de `routers/admin_tenants.py` exigem token administrativo **RS256** de um IdP dedicado (`iss`/`aud` próprios, `hd` do domínio corporativo) mais um principal ativo em `aprimora_py.platform_principal` — nunca e-mail, `usuario.id`, cookie ou token municipal. Elas usam `get_platform_db` (`database_plataforma.py`, papel `aprimora_platform`, `NOBYPASSRLS`), **não** `get_db`, e o tenant alvo vem sempre da operação. `PLATFORM_ADMIN_EMAILS` foi removida: era o achado F-01, autorização por uma string que só é única *por tenant*. Concessão e revogação são por CLI no host (`app.cli.platform_principal`), nunca por endpoint.
- `tasks/` — Celery (`app.tasks.celery_app`). `cli/` — comandos administrativos (ex.: provisionar tenant). `middleware/`, `observability/`, `utils/`.
- `routers/_crud.py` — `paginated_list` etc. para o CRUD repetitivo (soft-delete + busca + paginação + escopo de tenant).

### Multi-tenancy — as regras que não podem ser quebradas

Isolamento tem **três camadas** e todas são obrigatórias:

1. **RLS no Postgres** — tabelas de negócio têm `ENABLE + FORCE ROW LEVEL SECURITY` com policies `tenant_isolation_select`/`tenant_isolation_modify` sobre `current_setting('app.tenant_id')`.
2. **Filtro aplicacional** — `tenant_filter(stmt, Model, tenant_id)` em `database.py` levanta `ValueError` se você esquecer o filtro num modelo tenanted, ou passar tenant num catálogo global. Use-o.
3. **Disciplina no service** — `tenant_id` **sempre vem do caller** (`require_tenant_id`), **nunca do payload**. Campos server-side (`id_usuario_solicitante`, `status`, `excluido`, `id`) não entram em schemas de entrada. Carga por id filtra `tenant_id` + `excluido.is_(False)` e devolve **404 cross-tenant** (não 403). FKs "soft" (unidade, usuário, veículo) precisam de validação **same-tenant** explícita — a FK do Postgres não filtra por tenant.

Outras convenções de domínio: exclusão é **soft-delete** (`excluido=True`, nunca DELETE físico); unicidade por tenant vira **índice único parcial** `WHERE excluido = false`; transição de estado ilegal é **409**; permissão negada é **403** via `require_permission("<codigo>", "inserir"|"atualizar"|"excluir")` (leitura sem action). Super-usuário faz bypass.

#### Sigilo gradual (LAI) — a quarta dimensão de acesso, e a mais fácil de esquecer

Além de tenant, módulo e permissão, processo tem `nivel_sigilo` (`ostensivo` → `interno` →
`reservado` → `secreto` → `ultrassecreto`) e usuário tem a credencial `nivel_acesso_sigilo`. Regra:
alcança o que for **≤** sua credencial; super-usuário passa. A implementação está em
`services/sigilo.py`, e o guard reaproveitável é **`assert_acesso_processo`** (levanta
`SigiloAcessoError` → **404**, nunca 403 — 403 confirmaria a existência).

**Todo caminho que serve conteúdo ligado a um processo tem de passar por esse guard**, e isso inclui
caminho que não menciona processo nenhum na assinatura. O download de anexo ficou de fora por sete
meses exatamente assim: `require_permission` não cobre sigilo, o endpoint só falava em `anexo_id`, e
a listagem — que filtra certo — dava a impressão de que o assunto estava resolvido. Qualquer
autenticado do tenant baixava anexo de processo ultrassecreto iterando o id. Hoje o carregador cru
`get_anexo_path` é proibido em router (`tests/test_guarda_anexo_sigiloso.py`); use
`get_anexo_path_autorizado`.

Duas regras que saíram daquele conserto: **a autorização vem antes de resolver o recurso** (senão a
mensagem de erro distingue "existe" de "não existe" para quem não pode saber), e **teste de service
não cobre esta classe de defeito** — ela mora na costura router↔service, que é onde o `Depends`
some.

#### Papéis de banco — a camada 1 hoje está INERTE no runtime (achado F-12)

A aplicação conecta como `ged_user`, que é `SUPERUSER` e `BYPASSRLS`: **a RLS não filtra nada em
produção**, e o isolamento depende inteiramente das camadas 2 e 3. Medição em
`docs/architecture/security/rls-bypass-inventory.md`; decisão em `ADR-016 §9.1`.

Quatro papéis existem no banco, todos `NOSUPERUSER`/`NOBYPASSRLS`, e cada um tem a sua variável de
ambiente — **vazia por padrão, caindo em `DATABASE_URL`**:

| Papel | Variável | Quem usa |
|---|---|---|
| `aprimora_app` | `APP_DATABASE_URL` | API municipal (`app/database.py`) |
| `aprimora_worker` | `WORKER_DATABASE_URL` | tasks Celery (`app/tasks/_task_db.py`) |
| `aprimora_migrator` | `MIGRATOR_DATABASE_URL` | Alembic + CLIs de seed/backup (`app/database_admin.py`) |
| `aprimora_platform` | `PLATFORM_DB_URL` | fronteira de plataforma (`app/database_plataforma.py`) |

Trocar o valor efetivo é o gate **`SEC-RLS-ROLLOUT`**, um degrau por vez, e o rollback é apagar a
variável. Ordem: **worker, depois app**. **`MIGRATOR_DATABASE_URL` está BLOQUEADA** — não definir
em nenhum ambiente: `aprimora_migrator` tem `CREATE` mas **não é dono** das tabelas legadas, e como
o `entrypoint.sh` roda `alembic upgrade head` com `set -e`, a primeira migration com `ALTER TABLE`
em tabela pré-existente derruba o start do backend com `must be owner of table`. Ela serve hoje só
para invocar CLI de seed/backup à mão. Desbloqueia quando a posse dos schemas for resolvida no
bootstrap.

**Nunca "conserte" uma falha de permissão dando `BYPASSRLS` ou `SUPERUSER` a um desses papéis** —
é proibido pelo ADR e há teste que reprova (`tests/test_rls_papeis_minimos.py`). Policy ou grant que
falhar é corrigido.

**Tabela de plataforma (`aprimora_py.platform_*`) não entra em `GRANT ... ON ALL TABLES`.** Elas não
têm RLS: grant é a única barreira. Migration com grant-cobertor em `aprimora_py` precisa do `REVOKE`
correspondente, como a 0078 faz — `test_tabelas_de_plataforma_so_do_papel_de_plataforma` reprova
quem esquecer.

Consequência prática para quem escreve código: **CLI administrativa (seed, backup, provisionamento
em lote) não usa `SessionLocal`** — usa `AdminSessionLocal` de `app/database_admin.py`. O papel da
API não tem `CREATE` em schema nenhum, não escreve no catálogo de módulos e não apaga linha de
`audit_log`.

Rodar a suíte com o papel alvo, que é como se verifica que nada depende do bypass:

```bash
docker exec -e PYTEST_DB_HOST=db \
  -e DATABASE_URL=postgresql+asyncpg://aprimora_app:ged_password_secure_local@db:5432/ged_saas_db \
  aprimora-py-backend pytest -q
```

### Migrations (`backend/alembic/versions/`)

`target_metadata = None` — **autogenerate está desligado de propósito**. Todas as migrations são escritas à mão; o ORM mapeia tabelas legadas e o autogenerate tentaria dropar colunas do PHP. Numeração sequencial `NNNN_descricao.py` (já em 0072+), `down_revision` no head anterior, **head sempre único**, `downgrade()` desfazendo o `upgrade()` na ordem inversa.

Tabela nova exige o boilerplate completo: `tenant_id` NOT NULL → `aprimora_py.tenant(id)`, índices `(tenant_id, ...)`, `ENABLE + FORCE ROW LEVEL SECURITY`, as duas policies com `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int`, `GRANT SELECT,INSERT,UPDATE,DELETE` na tabela e `GRANT USAGE, SELECT` na sequence para a role `aprimora_app`. `ADD COLUMN` em tabela existente herda RLS/grants — não repita. **Exceção: `aprimora_py.tenant`.** Desde a `0080` (`SEC-RLS-00D`) o `UPDATE` de `aprimora_app` ali é **por coluna**, então coluna nova nasce sem `UPDATE` para o runtime municipal, e o `ALTER DEFAULT PRIVILEGES` da `0006` não socorre (ele vale para tabela nova, não para coluna nova). Se um caminho municipal for gravá-la, a mesma migration tem de acrescentá-la ao `GRANT UPDATE (...)` e a `COLUNAS_MUNICIPAIS_DE_TENANT` (`services/tenant_config.py`).

Os três detalhes do boilerplate que **já custaram um módulo inteiro** (`transporte_regulado`, 20
policies quebradas por 7 meses, corrigidas na `0078`): o nome da GUC é `app.tenant_id` e não
`app.current_tenant_id`; o segundo argumento `true` do `current_setting` não é opcional — sem ele
a policy **derruba a consulta** em vez de negar; e `ENABLE` sem `FORCE` não protege nada enquanto
o dono da tabela for também o papel do runtime. `tests/test_rls_papeis_minimos.py::test_toda_tabela_com_rls_responde_sob_aprimora_app`
varre o banco inteiro e reprova os três. Grant para `aprimora_worker` só se alguma task escrever na
tabela — o worker é enumerado de propósito; `aprimora_migrator` já é coberto por default privileges.

O agente `migrations-checker` (`.claude/agents/`) roda esse checklist; `frota-reviewer` e `frota-test-runner` cobrem revisão e bateria de validação de PR.

### Frontend (`frontend/`)

- `app/(app)/` — portal admin autenticado (layout com Sidebar); `app/cidadao/` — portal público; `app/(plataforma)/` — admin de tenants; `app/login/`, `app/validar/`, `app/alterar-senha-obrigatoria/`.
- `lib/api.ts` (~4.4k linhas) — **cliente único** de toda a API: interfaces TypeScript espelhando os `*Out` do backend + métodos agrupados por domínio. Endpoint novo entra aqui, com o tipo correspondente. Resolve base URL por contexto: `NEXT_PUBLIC_API_URL` no browser, `INTERNAL_API_URL` no SSR.
- `lib/auth.tsx` (admin) e `lib/cidadao-auth.tsx` (cidadão) — providers separados, cookies separados (`aprimora_token` × `aprimora_cidadao_token`); dá para estar logado nos dois ao mesmo tempo. `middleware.ts` faz os guards de rota.
- `components/CrudPage.tsx` — telas de cadastro simples derivam dela. Componentes por módulo em `components/<modulo>/`.
- Ao enviar formulários, normalize `""` → `null` em campos opcionais/datas antes do POST/PUT.

### Adicionando um módulo — o que costuma ser esquecido

1. Registrar **todos** os routers em `main.py` com `prefix="/api/v2"`.
2. Tipos + métodos em `frontend/lib/api.ts`; entrada de menu em
   **`frontend/lib/menus/<modulo>.ts`** — não em `components/Sidebar.tsx`, que desde a F2 só
   consome dali. Item novo também precisa entrar na tabela `PERMISSOES_ESPERADAS` de
   `__tests__/menus.test.tsx`, e o card do hub do módulo, se houver, no mesmo commit da tela
   (a guarda de página órfã reprova o contrário).
3. **Adicionar a rota de topo à regex de `location ~ ^/(...)` em `nginx/default.conf`** — sem isso a página cai no fallback legado e "some" no `:8090`, mesmo funcionando em `:3000`.
4. Migration com o boilerplate de RLS acima.
5. Testes `backend/tests/test_<modulo>_*.py`.
6. **Rota de segmento literal (`/vencidos`, `/relatorio`) tem de ser declarada ANTES da paramétrica
   irmã (`/{id}`)** — o FastAPI casa na ordem de declaração, então a paramétrica engole a literal e
   a requisição morre em **422** sem chegar no handler. Esse defeito ocorreu **três vezes** no
   `transporte_regulado.py` e nenhuma foi pega por teste de service, que não passa por roteamento.
   Hoje `tests/test_guarda_ordem_rotas.py` varre a aplicação inteira e reprova o caso.
7. **O tipo em `api.ts` tem de casar com o `response_model` do endpoint.** `request<T>()` faz cast do
   JSON **sem validar**: o tipo é uma afirmação sobre a resposta, não uma verificação dela. Declarar
   `X[]` onde o backend devolve `Paginated[X]` deixa o `tsc` verde e estoura no navegador com
   `TypeError: ….map is not a function` — e, onde o código faz `data?.length`, a tela diz "nenhum
   registro" com registros no banco, sem erro nenhum no console. Aconteceu por 11 dias no transporte.
   Endpoint paginado → `request<Paginated<X>>` e tela consumindo `.items`. **Não** desembrulhe dentro
   do `api.ts`: o tipo honesto é o que faz o `tsc` reprovar a próxima ocorrência.

## Testes — convenções

`backend/tests/conftest.py` expõe dois engines por um motivo: `admin_session` usa `ged_user` (SUPERUSER, **BYPASSRLS**) só para setup/teardown; `app_session` usa `aprimora_app` (**NOBYPASSRLS**) e é o único jeito de validar RLS de verdade — teste de isolamento escrito com `admin_session` passa por engano. Com `app_session`, o teste é responsável por `SET LOCAL app.tenant_id` em cada transação. A fixture `two_tenants` cria/limpa dois tenants com slug aleatório.

**A suíte inteira exercitava super-usuário, e isso escondeu um 500 em produção.** Em `auth/perms.py`
o bypass de SU **retorna antes** do `getattr(item, action)`, então defeito que só aparece para
usuário comum passa por toda a bateria sem ser visto — foi assim que 10 rotas do transporte com um
`action` inexistente (`"visualizar"`, que não está no `Literal` de `Action` nem em `PermItem`)
ficaram devolvendo `AttributeError` → HTTP 500 para qualquer operador não-SU. Ao gatear endpoint
novo, escreva **pelo menos um teste HTTP com usuário comum**; o padrão de montar esse usuário está
em `test_permissoes_modulo.py::_cria_usuario_comum` e em
`test_transporte_p4_relatorio.py::test_http_usuario_comum_acessa_relatorio_kpis`. Lembre que o
tenant precisa contratar o módulo, senão o gate barra antes com 403 e o teste não chega onde importa.

Dados de teste: e-mails no domínio reservado `.test` (`@e2e.test`, `@ux1smoke.test`), slugs com prefixo identificável (`e2e-`, `sec1-`, `ux1-smoke-`) + sufixo `uuid4().hex[:8]`, cleanup obrigatório no teardown. Testes **não devem assumir banco vazio** — evite contagens globais; ancore em `admin@local.test` no tenant default ou num tenant isolado da fixture.

CI (`.github/workflows/`): `backend-tests.yml` carrega `ci/legacy-schema.sql`, faz `alembic stamp <baseline>` e `upgrade head` — ou seja, **a migration nova é exercitada em banco limpo**. Ao regenerar o dump, atualize o número do `stamp` no workflow. `frontend-tests.yml` roda vitest.

## Docs de referência

`README.md` (arquitetura, tabela completa de migrations, decisões registradas), `RUNBOOK.md` (onboarding de tenant, `must_change_password`/SEC-1, backup por tenant, observabilidade, incidentes comuns), `docs/design-system.md`, `docs/INTEGRACAO-PAGAMENTOS.md`, `docs/runbooks/platform-operator-bootstrap.md`, `docs/GOOGLE-DOCS-OAUTH-SETUP.md`, `docs/BACKLOG-PENDENCIAS.md` (fonte viva de pendências).

`docs/archive/` guarda escopo de PR já mesclado, plano pontual já executado e recap de sessão — histórico, não referência corrente. `CUTOVER.md`/`CUTOVER-INVENTORY.md`, `PROTOCOLO-PLAN.md`, `DEPLOY-PLAN.md`/`DEPLOY-SETUP.md` e `CHATBOT-PLAN.md` foram pra lá em 2026-08-25 (auditoria de docs) — o `CHATBOT-PLAN.md` já se declarava obsoleto, apontando pra `docs/superpowers/specs/2026-08-07-ia-1-assistente-do-processo-design.md` como fonte atual.
