# Backlog de pendências

**Levantado em:** 2026-07-28 · **Método:** verificação direta no código e no `git`, não em memória de sessão.

> **Leia isto primeiro (você, agente):** nenhum item deste documento está autorizado a ser
> iniciado. O processo do repositório é **escopo fechado em doc → autorização humana →
> implementar → testes → autorização → commit**. Este arquivo existe para que a próxima sessão
> não precise redescobrir o estado; ele **não** é uma lista de tarefas a executar.
>
> Cada item traz a **evidência** que sustenta a afirmação. Antes de agir sobre qualquer um,
> reconfirme a evidência — o repositório se move.

## Estado de referência

> **Atualizado em 2026-07-30.** O bloco abaixo descrevia o estado de 28/07; o que mudou está logo
> em seguida.

- `main` em `eb93bd1`, CI verde nos três workflows, VPS de homologação no ar e populada nos
  quatro módulos (protocolo, pagamentos, frota, transporte regulado).
- Migrations até **0072** (head único).
- **Não há branch pendente de merge.** Verificado com `git branch --merged origin/main`: as
  branches de feature antigas já estão dentro de `main`, incluindo `feat/frota-operacional-completo`
  e `feat/transporte-p4-alvaras-complementacoes` (registros anteriores davam essas duas como
  "aguardando decisão de merge" — está desatualizado).

**Estado em 2026-07-31:**

- `main` em `c19f359`. **A modularização está completa até a interface**, em três fatias, todas
  mergeadas com CI verde e deployadas na VPS:
  - **F1** (`c4dcb53`) — catálogo, contratação por tenant, bloqueio de **escrita**. Migrations até
    **0075** (head único): 0073 catálogo+contratação, 0074 as 9 transações que faltavam, 0075 FK de
    `tenant_modulo` com `ON DELETE CASCADE`.
  - **Leitura por módulo** (`a7867c9`, item 1.0.5) — `require_modulo(slug)` em 69 GETs; 7
    transversais permanecem sem gate, com a razão registrada na guarda.
  - **F2** (PR #17, `c19f359`) — a interface: menus por módulo, launcher `/modulos`, login
    aterrissando nele, switcher no Header, cabeçalho de módulo na Sidebar, aba Módulos no admin,
    Ctrl+K ciente de módulo e permissão.
- **F3 (prefixo `/m/<slug>` + redirects 308) não está planejada.** O mapa `pathname → módulo` que a
  F2 criou (`frontend/lib/modulos.ts`) é o que vai gerar os redirects.
- **Cuidado ao validar módulos na homologação:** o seed contrata os **cinco** módulos no tenant
  `sobral`. O caso de "tenant com um módulo só" — onde estava o defeito crítico da F2 — **não é
  exercitado** por navegação normal. Use a aba Módulos do admin de plataforma para descontratar.
- **Ambiente local do Jorge:** o antivírus AVG intercepta HTTPS e **nenhuma imagem docker rebuilda
  nessa máquina** (npm e PyPI falham com erro de certificado). O frontend local roda por um contorno
  — build no host copiado para dentro do container — que morre se o container for **recriado**
  (`docker compose up -d`), não sobrevive a isso. CI e VPS não são afetados.
- **Ambiente local do Jorge:** o antivírus AVG intercepta HTTPS e **nenhuma imagem docker rebuilda
  nessa máquina** (npm e PyPI falham com erro de certificado). O frontend local roda por um contorno
  — build no host copiado para dentro do container — que morre se o container for **recriado**
  (`docker compose up -d`), não sobrevive a isso. CI e VPS não são afetados.

> **Atualizado em 2026-07-28 (quatro itens fechados, removidos conforme a seção 4):**
>
> - **PR #12 — UI da conciliação bancária: mergeado** (`e19e551`) e deployado. A Onda B de
>   pagamentos está fechada ponta a ponta. Detalhes na descrição do PR e em `CLAUDE.md`.
> - **"59 ocorrências de TODO/FIXME": não existem.** A contagem era artefato de medição — uma
>   busca *case-insensitive* por `todo` casa com a palavra portuguesa "todo/todos", onipresente
>   num repositório em pt-BR. Contagem correta (`grep` sensível a maiúsculas por `TODO`/`FIXME`/
>   `XXX`/`HACK`): **4 no backend, 0 no frontend**. Desses 4, **3 são a palavra "TODOS" em caixa
>   alta** dentro de docstrings (`dashboard.py:1032`, `pagamentos_autorizacao.py:119`,
>   `limpar_jobs_antigos.py:33`). Sobra **um TODO real**: `backend/app/routers/minutas.py:269`
>   — "Pull DOCX, extract text, update corpo_html" —, que já é o item **2.4** deste documento.
>   Não há dívida oculta em marcadores; não repetir esta varredura.
> - **Limite de upload divergente: corrigido** (PR #13, `bf3d972`). O portal anunciava e validava
>   25 MB contra os 20 MB do backend — um anexo de 22 MB subia inteiro antes de ser recusado.
>   Alinhado em 20 (decisão do Jorge; o nginx permite 50m, então a escolha não era imposta por
>   infra). Três testes travam o número, a recusa acima e a aceitação abaixo, e foi verificado
>   que falham se a constante voltar para 25.
> - **Issue #3 — chave Fernet: resolvida** (PR #14, `eb93bd1`), issue fechada. Saiu do
>   `docker-compose.yml` para o `.env` da raiz, com `${VAR:?msg}` fazendo o compose abortar
>   sem ela. A rotação **saiu de graça**: a VPS não tinha nada cifrado (0 credenciais Google,
>   0 nos quatro campos `*_cif`), então a reencriptação que o item previa não se aplicava.
>   Local manteve a chave antiga de propósito — tem 30 credenciais Google cifradas com ela.
>   **Essa janela barata fecha quando entrar o primeiro dado bancário real em produção.**
>
> **Consequência:** a seção 1 ficou reduzida a itens que dependem de decisão humana, e a
> **spec municipal de pagamentos que define a Onda C não está versionada** — os códigos
> `RF-*`/`RN-*` aparecem por todo o backend, mas nenhum `.md` do repositório os contém.
> Escopar a Onda C exige que essa spec seja fornecida; sem ela, qualquer documento de escopo
> seria requisito inventado, não a especificação da prefeitura.

---

## 1. Curto prazo — itens concretos em aberto

### 1.0 Deriva de `APP_NAME` no ambiente de dev — RBAC apontando para o sistema errado

*(Descoberto em 2026-07-28, durante a fatia F1 da modularização.)*

- `utils.sistema` tem **duas** linhas: `Aprimora` (`app = 'aprimora'`, id 1) e `Sistemas`
  (`app = 'sistemas'`, id 2).
- O container `aprimora-py-backend` em execução tem `APP_NAME=aprimora`, mas o
  `docker-compose.yml` **versionado** e o default de `backend/app/config.py` dizem `sistemas`.
- Todo o RBAC do ambiente local (grupos, `usuario_grupo`, `sistema_transacao`) foi construído sob
  `aprimora`. **Um `docker compose up -d` que recrie o container realinha para `sistemas` e derruba
  as permissões do admin local** — `load_permissions` filtra grupos por `Sistema.app == app_name`.
- É a mesma classe de bug que o `CLAUDE.md` registra como já tendo causado 403 geral em todo tenant
  provisionado.
- **Consequência já visível:** explica a falha de
  `tests/test_pr5a_dashboard_servicos.py::test_http_dashboard_com_perm_acessa`, que estava sendo
  tratada como "pré-existente inexplicada".
- Não investigado: qual é o estado na VPS de homologação. **Verificar lá antes de decidir o
  conserto** — se produção estiver sob `sistemas`, o errado é só o container local; se estiver sob
  `aprimora`, a correção envolve migrar dados.

### 1.0.5 Leitura de módulo sem gate de permissão — FECHADO (contratação; autorização segue item 1.0.8)

*(Descoberto em 2026-07-29, pela varredura de endpoints da fatia F1 da modularização. Fechado em
2026-07-30 pela fatia `feat/leitura-por-modulo`, escopo em
`docs/superpowers/specs/2026-07-30-leitura-por-modulo-escopo.md`.)*

- A varredura original cobriu **136 endpoints** sob `/api/v2`. Destes, **76 GETs pertenciam a um
  módulo e não tinham gate nenhum** — só `get_current_user`. Não era esquecimento pontual: os
  routers da geração protocolo seguiam *escrita gateada, leitura liberada a qualquer autenticado do
  tenant*.
- **O que a fatia fechou:** nasceu `require_modulo(slug)` (`backend/app/auth/modulos.py`), que
  resolve `tenant_id` do caller e barra com 403 se o módulo não estiver contratado — **sem olhar o
  usuário** (não consulta grupo, transação nem nível; propriedade central, com teste que trava:
  `test_usuario_sem_permissao_continua_lendo`). Aplicada a **69** dos 76 (58 `protocolo`, 11
  `administracao`); os 7 restantes ficaram transversais, sem gate, com a razão registrada em
  `backend/tests/test_guarda_modularizacao.py::ENDPOINTS_LEITURA_SEM_GATE` (`/busca`, `/usuarios`,
  `/usuarios/{id}`, `/unidades-trabalho`, `/unidades-trabalho/{id}`, `/audit`, `/organograma` — os
  quatro últimos por consumo cruzado comprovado entre módulos, os dois primeiros por decisão humana
  de que o recurso é do sistema).
- A tabela `ROTAS_POR_MODULO` (mesmo arquivo) é a fonte versionada de qual módulo cada rota exige,
  checada contra a implementação real por introspecção no CI — substitui a lista solta que este item
  citava antes.
- **O que NÃO fechou, e não é a mesma coisa:** a contratação responde "o tenant tem o módulo?", não
  "este usuário pode ler isto?". Todo autenticado do tenant continua lendo `/usuarios`, `/grupos`,
  `/audit` etc. — isso é o item **1.0.8**, aberto de propósito por esta fatia.

### 1.0.6 `/notificacoes/whatsapp-test` sem autorização — qualquer autenticado do tenant dispara

*(Levantado em 2026-07-30 pelo review da fatia F1. **Não é regressão da F1**: `main` tem o mesmo
`Depends(get_current_user)` e nada mais — verificado em `git show main:`. A F1 chegou a fechar de
passagem e devolveu ao original, porque o único código de permissão disponível acoplava o endpoint
ao módulo errado.)*

- `POST /api/v2/notificacoes/whatsapp-test` (`backend/app/routers/notificacoes.py:164`) dispara envio
  de WhatsApp para **telefone arbitrário do payload**, usando a credencial paga do tenant. Exige
  apenas estar autenticado — o usuário de menor privilégio do tenant consegue. É vetor de custo e de
  abuso, não só de vazamento.
- **Por que a F1 não fechou:** o único código de transação vizinho é `configuracao`, que pertence ao
  módulo `administracao`. Gatear com ele daria 403 no endpoint para tenant que tem `protocolo` e não
  tem `administracao` — trocaria um defeito por outro. Não existe transação de notificação em
  `utils.transacao` (verificado por query), e criar uma exige migration **mais** concessão aos grupos
  existentes, senão o endpoint passa a dar 403 para todo mundo.
- **O sujeito certo não existe ainda:** o correto seria "super-usuário **do tenant**".
  `require_platform_admin` é sujeito errado (é da plataforma, opera sobre outros tenants) e
  `require_permission` precisa de um código que ainda não há.
- **Ao retomar:** decidir entre (a) criar a transação `notificacao` vinculada ao módulo `comum` e
  conceder aos grupos administrativos na mesma migration, ou (b) introduzir a dependência de
  super-usuário do tenant, que serve a outros endpoints de operação além deste. A (b) é mais
  trabalho e resolve uma classe; a (a) fecha só este.
- Enquanto aberto, o endpoint está listado em `ENDPOINTS_TRANSVERSAIS` em
  `backend/tests/test_guarda_modularizacao.py` — ou seja, a guarda **não** vai reclamar dele. A
  vigilância é este item, não o teste.

### 1.0.65 Falha da F1 que só aparece em banco limpo — ainda NÃO diagnosticada

*(Aberto em 2026-07-30, depois do merge da F1. **É o item mais urgente desta seção.**)*

O job `Backend tests` do CI não conseguiu reportar em nenhuma das duas primeiras tentativas depois do
merge: morreu por timeout em 15 min e depois em 30 min. A causa do travamento foi corrigida em
`eea6876` (ver adiante), e o log parcial mostrou o ponto onde estava:

```
tests/test_permissoes_matriz.py ..........   [ 47%]
tests/test_permissoes_modulo.py ...F
##[error]Process completed with exit code 143
```

- **Há um `F`** — falha real — em `tests/test_permissoes_modulo.py`, arquivo criado pela própria F1.
  O pytest foi morto (SIGTERM) antes de imprimir a asserção, então **a mensagem é desconhecida**.
- **Passa localmente**: a suíte aqui fecha em `2 failed / 863 passed`, e as duas são as
  pré-existentes do item 1.1.5. Logo, é falha que só o banco limpo do CI expõe — mesma classe do
  Critical que o review final pegou (contratação ausente em banco limpo).
- **Hipótese descartada:** deriva de `APP_NAME`. O `backend-tests.yml` **não** seta a variável, então
  o CI roda consistente com o default (`sistemas`) e o `ci/seed-e2e.sql` cria a linha
  `utils.sistema` correspondente. Testar com `APP_NAME=sistemas` no container local só quebra a
  consistência local e produz uma falha diferente — não reproduz o CI.
- **Como retomar:** rodar `gh run list --workflow="Backend tests" --branch main` e ler o run mais
  recente. Com o travamento corrigido, o pytest agora **imprime** a falha em vez de ser morto. Se o
  run mais recente ainda não existir, `gh workflow run backend-tests.yml`.
- Reproduzir localmente exigiria montar um banco do zero pelo caminho do CI (dump de
  `ci/legacy-schema.sql` → `alembic stamp 0020` → `upgrade head` → `ci/seed-e2e.sql` →
  `seed_bootstrap`) e apontar **as duas** conexões (`PYTEST_DB_HOST` e `DATABASE_URL`) para ele —
  ver a armadilha das duas conexões no `CLAUDE.md`.

### 1.0.66 A suíte de backend cresceu para além do teto do CI

O job levava 13–14 min contra um teto de 15; os ~40 testes da F1 empurraram por cima e o teto subiu
para 30 (`c51e8a4`). **Subir de novo não é o conserto** — está escrito no próprio workflow. A suíte é
serial de propósito: compartilha um único Postgres e os testes de RLS dependem disso. Paralelizar
exige um banco por worker (`pytest-xdist` + schema/database por processo), ou fatiar o job.

### 1.0.7 As 9 transações da 0074 não estão concedidas a nenhum grupo

*(Levantado em 2026-07-30 pelo review final da F1. Decisão: **fica documentado, não automatizado** —
ver abaixo por que uma migration de concessão não é escrevível sem definir política de acesso.)*

A migration `0074` criou 9 transações (`processo`, `usuario`, `catalogo`, `assunto`, `manifestante`,
`cidade`, `endereco`, `workflow`, `unidadeTrabalho`) e a Task 8 gateou 13 endpoints sobre `processo`
e `workflow` — entre eles `routers/workflow.py:479` (transicionar, usado pelo
`ProcessoWorkflowPanel.tsx`) e os 4 disparos de job em `routers/jobs.py`. Nenhuma dessas transações
tem linha em `utils.grupo_transacao`.

- **Não afeta ninguém hoje**, e não por sorte: `is_super_usuario` é `nivel.valor == 0`
  (`services/permissoes.py:92`), o ramo de SU lê `utils.sistema_transacao` e **não**
  `grupo_transacao`, e no banco existem **zero** grupos com `nivel.valor <> 0` (verificado por
  query). Todo grupo do sistema é super-usuário.
- **Aparece no dia em que o primeiro grupo "Operacional" (nível 1) for criado.** Nesse momento, quem
  cria o grupo escolhe as transações dele — é o passo já documentado em `RUNBOOK.md`.
- **Por que não virou migration:** concessão em bloco **abriria** acesso em vez de preservar. As 9
  transações são novas, então nenhum grupo as tinha; endpoints antigos gateados em `processo,excluir`
  já eram 403 para não-SU antes da branch. Conceder tudo daria a um Operacional o poder de excluir
  processo, que ele nunca teve. Escrever a migration correta exige decidir, código por código e ação
  por ação, quem passa a poder o quê — isso é política de acesso, decisão do dono do produto.
- **A verificar antes de criar grupo não-SU na VPS:** a apuração acima é do banco **local**. Rodar lá
  `SELECT count(*) FROM utils.grupo g JOIN utils.nivel n ON n.id=g.id_nivel WHERE n.valor <> 0` — se
  houver grupo não-SU, existe usuário real perdendo acesso nesses 13 endpoints, e aí a concessão
  deixa de ser hipótese.

### 1.0.8 O buraco de autorização — leitura de módulo segue aberta a qualquer autenticado do tenant

*(Aberto de propósito pela fatia `feat/leitura-por-modulo` (2026-07-30), que fechou o item 1.0.5.
Prometido duas vezes no escopo aprovado
(`docs/superpowers/specs/2026-07-30-leitura-por-modulo-escopo.md`, seção "A decisão" e seção "Fora
de escopo") como item de backlog próprio; criado agora no review final.)*

- "Fechar a leitura" eram **dois** problemas distintos: o buraco da **modularização** (tenant sem o
  módulo contratado lê os dados dele) e o buraco de **autorização** (qualquer autenticado do tenant
  lê `/usuarios`, `/grupos`, `/audit` e os demais, independente de ter a transação concedida). A
  fatia de 2026-07-30 fechou só o primeiro, com `require_modulo` — que **deliberadamente não olha o
  usuário**.
- **Por que ficou de fora, e não é omissão:** fechar o segundo exigiria trocar (ou somar)
  `require_permission("<transacao>")` nos GETs, o que muda política de acesso — cada usuário passaria
  a precisar da transação concedida ao grupo dele. Hoje isso seria **inócuo**: todo grupo do sistema é
  super-usuário (`nivel.valor = 0`, verificado por query, item 1.0.7), então ninguém perderia acesso
  na prática. Mas no dia em que o primeiro grupo "Operacional" (nível 1) for criado, os GETs hoje
  liberados virariam 403 em massa para esse grupo até alguém conceder as transações — evento
  disruptivo se acontecer sem aviso.
- **Essa concessão é decisão do dono do produto**, já registrada como item 1.0.7 (as 9 transações da
  0074 sem linha em `utils.grupo_transacao`) justamente por essa razão: é política de acesso, não
  refactor.
- **Ao retomar:** não é "aplicar `require_permission` nos GETs" isoladamente — isso pressupõe que as
  transações certas já estão concedidas aos grupos certos, que é o próprio item 1.0.7. Os dois
  precisam andar juntos, e o gatilho para priorizar é a criação do primeiro grupo não-SU (ver
  "a verificar" no item 1.0.7).
- Sem prazo.

### 1.0.9 Resíduos da F2 — navegação e admin (todos Minor, nenhum bloqueante)

*(Levantados pelo review final da fatia F2 (2026-07-31, PR #17) e deixados de fora por decisão, não
por esquecimento. Agrupados aqui para não se perderem.)*

- **Deep link não volta depois do login.** `frontend/middleware.ts` clona a URL e troca o pathname
  por `/login`, **perdendo o destino original** — nunca houve `next=`. Quem tenta abrir
  `/frotas/veiculos` sem sessão vai parar no launcher. **Não é regressão** (antes ia parar em
  `/home`), mas incomoda mais agora que a porta de entrada é a tela de escolha.
- **`api.adminTenantModulos` / `api.adminTenantContratarModulos` ficaram na raiz** do objeto `api`,
  em vez de `api.admin.tenants.modulos` / `.definirModulos`, onde já vivem `detalhe`/`editar`/
  `ativar`/`desativar` do mesmo recurso.
- **Abas do admin de tenant sem semântica completa:** `role="tablist"`/`role="tab"` sem
  `aria-controls`, sem `role="tabpanel"` no conteúdo, sem navegação por setas nem roving tabindex.
  Leitor de tela anuncia "aba" e não encontra painel associado.
- **O card do launcher aponta para a `raiz` fixa do módulo**, que pode ser uma tela fora do menu
  daquele usuário — `administracao` leva a `/usuarios` (`perm: usuario`), `protocolo` a `/processos`
  (`perm: processo`). Não dá 403 (leitura não é gateada por permissão — ver 1.0.8), mas é incoerente.
  Alternativa: `raiz` = primeiro item visível do menu daquele módulo para aquele usuário.
- **Fixtures duplicadas nos testes de backend:** `tests/test_leitura_por_modulo.py` é a quarta cópia
  do padrão de provisionamento+token+cleanup do diretório. Pede um `conftest`.

### 1.1.5 Suíte não estava verde antes do F1

Duas falhas confirmadas como anteriores à branch `feat/modularizacao-f1` (verificado por
`git stash`): `test_jwt_compat.py::test_emitted_token_has_required_claims` e
`test_pr5a_dashboard_servicos.py::test_http_dashboard_com_perm_acessa` (esta última explicada pelo
item 1.0 acima). O CI em `main` reporta verde, então a divergência é entre ambiente local e CI —
provavelmente a mesma deriva de env.

> **Correção de 2026-07-30:** "o CI em `main` reporta verde" era verdade quando isto foi escrito, mas
> deixou de ser depois do merge da F1 — ver item 1.0.65. Não tratar mais essas duas falhas como "o
> CI está verde, é só ambiente local" sem antes conferir o run mais recente.

> **Nota histórica.** Até 2026-07-29 esta seção terminava com a linha "Nenhum — os quatro itens
> desta seção foram fechados em 2026-07-28". A execução da fatia F1 da modularização abriu os sete
> itens acima e a linha virou o oposto do que o arquivo mostra, então foi substituída por esta nota.
> Os quatro itens fechados em 28/07 continuam descritos na nota do topo do arquivo.

---

## 2. Módulos com escopo declarado e não implementado

### 2.1 Pagamentos — Onda C

- **Evidência de que não existe nada:** `grep` por `xlsx|csv|export|relatorio` nos quatro routers
  (`pagamentos_cadastros.py`, `pagamentos_caixa.py`, `pagamentos_conciliacao.py`,
  `pagamentos_debitos.py`) retorna **zero** ocorrências.
- **Escopo previsto:** relatórios de exceção, export PDF/XLSX/CSV, integrações contábil e bancária,
  API idempotente.
- O próprio spec municipal joga **PDF/OCR de extrato e API bancária real** para uma "3ª etapa" —
  não confundir com o que a Onda C entrega.
- Contexto: Ondas A e B estão inteiras em produção (migrations 0063→0072).

### 2.2 Transporte Regulado — P5 a P8

P0–P4 entregues e no ar (permissionário, empresa, veículo, vistorias, alvarás com documentos,
responsáveis, vínculo veicular, auditoria, relatórios). Faltam:

- **P5** — Recadastramento
- **P6** — Rotas / linhas
- **P7** — Ocorrências regulatórias
- **P8** — Workflows avançados

### 2.3 Frota — backlog de telemetria

Frota-1..6 + a fatia Operacional (manutenção, abastecimento, vistoria, ocorrências, visão
gerencial) estão em `main` e no ar. O que resta é uma **iniciativa nova**, não uma continuação:

- **Geolocalização / rastreamento GPS em tempo real** — não existe. Depende de telemetria
  (rastreador embarcado ou provedor externo), ingestão de posições e provável armazenamento de
  série temporal. **Decisão de arquitetura pendente:** provider externo × hardware próprio.
- **Rotas / trajetos do veículo** — não existe; depende do item acima. Distinto de "rotas/linhas"
  do Transporte Regulado (P6), que é outro domínio.
- **Consumo (km/l e eficiência)** — parcial. Abastecimento já registra litros, custo e média R$/l;
  faltam km/l e "km rodado por período", explicitamente adiados na visão gerencial
  (`/frotas/relatorios`). Depende de séries de odômetro — ou do GPS, para km mais preciso.

### 2.4 Minutas / Google Docs — sincronização de volta

- `sincronizar_google_doc()` em `backend/app/services/google_docs_service.py` é **v1**: cria o Doc
  e exporta PDF na finalização, mas **não reimporta** o conteúdo editado para `corpo_html`.
  Faria falta um pipeline DOCX → HTML → sanitização.
- Sem re-autenticação automática quando o usuário revoga o acesso do app no Google — a próxima
  operação simplesmente falha.
- Sem coordenação de edição concorrente e sem contagem de páginas (o Google não expõe o metadado;
  a alternativa é exportar PDF e contar).

### 2.5 Chatbot / assistente conversacional

- **Evidência:** `backend/app/services/ia/` **não existe**. Zero linhas escritas.
- [`CHATBOT-PLAN.md`](../CHATBOT-PLAN.md) segue como rascunho, travado em **seis decisões humanas**
  (seção 3 do plano): D1 público-alvo do MVP, D2 provider, D3 grounding (tool-calling com catálogo
  fixo × SQL livre), D4 profundidade da validação factual, D5 execução inline SSE × Celery,
  D6 escopo de ações (só leitura × mutação de estado).
- Restrição inegociável já registrada no plano: o bot roda sob o mesmo RLS multi-tenant e o mesmo
  sigilo gradual — nunca pode responder o que o usuário não veria pela UI.

---

## 3. Dívida de produção

### 3.1 Object storage (gatilho definido)

- Decisão registrada no `README.md`: manter filesystem local
  (`/app/uploads/tenants/{slug}/...`, bind volume) enquanto é dev + piloto Sobral; migrar para
  **S3-compatible com versioning + Object Lock/WORM + lifecycle espelhando a TTD** antes do
  **2º tenant em produção** ou antes de entrar documento real com valor probatório.
- **Por quê:** o eixo crítico do domínio não é escala — é durabilidade e integridade legal (guarda
  por décadas, Lei 11.419/2006) e isolamento dos *bytes* entre tenants. RLS protege o banco, não o
  disco.
- Continua reversível a baixo custo porque `backend/app/services/anexos.py` é o **único** ponto que
  toca o disco (`resolve_anexo_path()` / `tenant_anexos_dir()`). A migração seria uma interface
  `StorageBackend` (put/get/delete/exists) com impl LocalFS atual + seleção por env.
- Escolha de provedor (MinIO self-hosted × cloud nacional × S3) é decisão de **compliance**, não
  técnica.

---

## 4. Como manter este documento

Ao concluir um item, **remova-o daqui** e registre o resultado onde ele pertence (README, RUNBOOK,
ou o doc de escopo do módulo). Este arquivo é uma lista de pendências, não um histórico — histórico
é o `git log`.
