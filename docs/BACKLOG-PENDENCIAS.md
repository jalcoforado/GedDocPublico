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
  - **F3** (2026-08-03) — o prefixo `/m/<slug>` nas URLs, 24 redirects **308**, guard de módulo,
    token `m` no nginx e o `?next=` no login. As telas de módulo saíram de `app/(app)/<rota>` para
    `app/(app)/m/<slug>/`; na raiz ficaram só as transversais da D5. `ROTA_MODULO` continua vivo, e
    não por inércia: é a fonte dos redirects, e `notificacao.link_url` é registro permanente.
    Guardas em `frontend/__tests__/rotas-modulo.test.ts` (57 asserções, quatro provadas por
    inversão). Falta a **F4**: `public.modulos`/`configuracoes_modulos` fora do ORM, `Sidebar.tsx`
    antiga deletada, `link_url` nascendo já prefixado.
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

### ~~1.0.6 `/notificacoes/whatsapp-test` sem autorização~~ — FECHADO em 2026-08-03

*(Levantado em 2026-07-30 pelo review da fatia F1. Fechado por `fix/whatsapp-test-autolimitado`.)*

- **O que era:** `POST /api/v2/notificacoes/whatsapp-test` disparava WhatsApp para **telefone
  arbitrário do payload** com a credencial paga do tenant, exigindo só estar autenticado. Vetor de
  custo e de assédio, não de vazamento.
- **As duas saídas que este item propunha estavam ambas erradas**, e vale registrar por quê: elas
  partiam de que o endpoint era administrativo ("validar config Zenvia em prod", como diz o
  docstring). Não é. O **único chamador** é `frontend/app/(app)/perfil/notificacoes/page.tsx`, a
  página de preferências do próprio usuário — qualquer pessoa salva o telefone e clica em testar.
  Gatear com transação ou com super-usuário do tenant tiraria isso de todo usuário comum no dia em
  que existir o primeiro grupo não-SU: trocaria um defeito de segurança por um de produto.
- **O que se fez:** tirar o **destino** das mãos do chamador, não restringir quem chama.
  `WhatsAppTestRequest.telefone` foi removido; o destino é sempre o telefone do perfil, resolvido no
  servidor por `Destinatario(id_usuario=...)`. Mais limite de **3 por hora por usuário** — só tirar o
  destino não bastava, porque `PUT /notificacoes/telefone` é livre e "troco meu número e testo de
  novo" continuaria queimando credencial. O limite conta por **usuário**: por telefone seria
  contornável pelo mesmo caminho, por tenant viraria negação de serviço entre colegas.
- **Efeito colateral que quase passou:** trocar `telefone` por `id_usuario` fez o motor aplicar a
  **preferência de canal**, que o caminho antigo pulava sem querer (o motor só consulta preferência
  para destinatário com `id_usuario`). Como `DEFAULT_PREFS["whatsapp"]` é `False`, conferir o
  telefone antes de ligar o canal — que é exatamente quando se testa — teria ficado impossível. Daí
  o `enviar(..., ignorar_preferencias=True)`, que é **só** para envio que o próprio destinatário
  pediu agora; envio automático continua respeitando o opt-out.
- Guardas em `backend/tests/test_notificacoes_whatsapp_teste.py` (5 testes, prova por inversão feita:
  5 vermelhos contra o comportamento antigo). O endpoint continua em `ENDPOINTS_TRANSVERSAIS` — não
  ganhou gate de módulo nem de permissão, e isso é decisão, não esquecimento.

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

### ~~1.0.85 SEC-RLS-00D — `UPDATE` em `aprimora_py.tenant` precisa ser grant POR COLUNA~~ — FEITO

*(Levantado pela revisão de segurança de `SEC-RLS-00C` (2026-08-02). Não era regressão: o grant era
anterior e aquele PR não o alterou. O que ele mudou foi a razão escrita, que descrevia o uso e não o
alcance.)*

> **Fechado em 2026-08-02, migration `0080_grant_por_coluna_em_tenant.py`.**
> `REVOKE UPDATE ON aprimora_py.tenant FROM aprimora_app` + `GRANT UPDATE (<13 colunas>)`. Conferido
> no catálogo depois de aplicar: `role_table_grants` não mostra mais `UPDATE` de tabela para
> `aprimora_app`, e `column_privileges` mostra 13 colunas onde mostrava 24.
>
> **A lista não é a whitelist do service copiada.** O levantamento de caminhos de escrita municipal
> em `Tenant` achou três, e a whitelist só cobre o primeiro:
> 1. `services/tenant_config.atualizar_config_institucional` (`PUT /tenants/me`) — os 11 campos de
>    `_CAMPOS_INSTITUCIONAIS`;
> 2. `routers/tenant.py::update_nup_config` (`PUT /tenants/me/nup-config`) — `codigo_orgao_nup` e
>    `usar_nup_federal`, **mesmo papel de banco, fora da whitelist**. Derivar a lista só de
>    `_CAMPOS_INSTITUCIONAIS` teria derrubado esse endpoint no dia do `SEC-RLS-ROLLOUT`;
> 3. `cli/tenant.py::_set_active` (`tenant activate|deactivate`) — gravava `ativo` e `atualizado_em`
>    por `database.SessionLocal`, o pool MUNICIPAL. **Não foi acomodado no grant**: ativar município
>    é ato de plataforma (é o que `POST /admin/tenants/{id}/ativar` já faz). A CLI passou a abrir a
>    sessão de plataforma, como `create`/`retomar` desde o `SEC-RLS-00C`.
>
> **A guarda é o que dá valor ao item**, e foi o que a revisão do `00C` pediu:
> `tests/test_grant_por_coluna_tenant.py` compara em três pontas o catálogo do banco, a constante
> `COLUNAS_MUNICIPAIS_DE_TENANT` (`services/tenant_config.py`) e os campos de
> `TenantInstitucionalUpdate`/`TenantNupConfigUpdate`. Tem denylist explícita das colunas de
> plataforma — sem ela a comparação de conjuntos seria satisfeita ampliando os dois lados — e
> controle positivo em cada negativa, porque em Postgres a negativa por privilégio de coluna devolve
> **a mesma frase** da negativa por privilégio de tabela (`permission denied for table tenant`).
> Prova por inversão executada: contra o estado anterior, 8 vermelhos e 2 verdes (os 2 medem o que a
> 0080 não tira).
>
> Continua valendo o item 1.0.86: só produz efeito quando `APP_DATABASE_URL` estiver definida.
> O texto abaixo é o registro original do problema.

- O `SEC-RLS-00C` tirou de `aprimora_app` o `INSERT` em `aprimora_py.tenant` e `tenant_modulo`
  porque essas tabelas **não têm RLS** e ali o `GRANT` é a única barreira. O `UPDATE` em `tenant`
  ficou, com uso legítimo e diário: `services/tenant_config.atualizar_config_institucional`, o admin
  do município editando sigla, endereço, telefone, texto do portal e unidade padrão.
- **O grant, porém, é de tabela inteira.** `information_schema.column_privileges` devolve `UPDATE`
  para `aprimora_app` nas **24** colunas de `aprimora_py.tenant`, incluindo `ativo`, `plano`, `slug`,
  `limite_usuarios` e `limite_armazenamento_mb`. É a mesma estrutura de risco do `INSERT`: um defeito
  de service no runtime municipal poderia elevar o próprio plano, reativar-se depois de suspenso ou
  **desativar outro município**. A whitelist de campos do service é barreira de aplicação, não de
  banco.
- **Ao retomar:** `REVOKE UPDATE ON aprimora_py.tenant FROM aprimora_app` seguido de
  `GRANT UPDATE (<colunas institucionais>) ON aprimora_py.tenant TO aprimora_app`, com a lista de
  colunas derivada de `_CAMPOS_INSTITUCIONAIS` em `services/tenant_config.py` — e uma guarda que
  reprove divergência entre as duas listas, senão campo institucional novo passa a dar
  `permission denied` em produção sem ninguém entender por quê.
- Como todo o resto desta família, só tem efeito quando `APP_DATABASE_URL` estiver definida (ver
  1.0.86).
- Sem prazo. Depende do `SEC-RLS-ROLLOUT` para ter efeito prático.

### 1.0.86 A família `SEC-RLS-*` só produz efeito quando `APP_DATABASE_URL` for definida

*(Registrado em 2026-08-02, na revisão de `SEC-RLS-00C`, para que a narrativa dos PRs de segurança
não seja lida como "está fechado em produção".)*

- `printenv` no container do backend devolve apenas `DATABASE_URL=…ged_user…`. `APP_DATABASE_URL`
  está **vazia**, então `runtime_database_url` cai em `DATABASE_URL` e a API conecta como `ged_user`,
  que tem `rolbypassrls = t`. Nenhum `REVOKE` das migrations 0076/0078/0079 tem efeito nesse papel.
- Isso é a **sequência correta** — revogar antes de trocar o papel, para que a troca não derrube
  nada —, e é justamente o que o `SEC-RLS-ROLLOUT` promove, um degrau por vez (worker → app; o
  migrator está bloqueado por posse de schema, ver o adendo §12.2 do ADR-016).
- O que exige cuidado é a **redação**: os testes provam as propriedades **sob `aprimora_app`**, papel
  que produção ainda não usa. Onde se escrever "a brecha fechou", leia-se "fecha quando
  `APP_DATABASE_URL` for definida". O que já é verdade hoje, sem depender do rollout, é que o banco
  está preparado e que a regressão tem guarda.

### 1.0.9 Resíduos da F2 — navegação e admin (todos Minor, nenhum bloqueante)

*(Levantados pelo review final da fatia F2 (2026-07-31, PR #17) e deixados de fora por decisão, não
por esquecimento. Agrupados aqui para não se perderem.)*

- ~~**Deep link não volta depois do login.**~~ **FECHADO na F3 (Tarefa 1, 2026-08-03.)** O
  middleware grava `?next=` e o login restaura, com allowlist contra *open redirect* —
  `//evil.example` começa com `/` e ainda assim sai do domínio, e é o único dos oito casos que
  reprova uma implementação ingênua. `must_change_password` mantém precedência. Texto original:
  `frontend/middleware.ts` clonava a URL e trocava o pathname
  por `/login`, **perdendo o destino original** — nunca houve `next=`. Quem tentava abrir
  `/frotas/veiculos` sem sessão ia parar no launcher. **Não era regressão** (antes ia parar em
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

> **Atualizado em 2026-08-01, pela fatia de costura de navegação** (spec e plano em
> `docs/superpowers/`). "Entregues e no ar" era verdade só para o backend. Três coisas mudaram, e a
> terceira segue aberta:
>
> - **A navegação até Alvarás e Relatórios não existia.** As telas estavam prontas desde P2/P4, mas
>   nenhum `href` no frontend apontava para elas: nem o hub, nem o menu, nem o Ctrl+K. Só se chegava
>   digitando a URL. A fatia ligou as duas e removeu do hub os cards de Documentos e Vistorias, que
>   não são destinos — existem só dentro do detalhe do veículo.
> - **Três rotas estavam inalcançáveis** (`vistorias/vencidas`, `alvaras/vencidos`,
>   `alvaras/relatorio`): declaradas depois da paramétrica irmã, o FastAPI casava a paramétrica
>   primeiro e devolvia 422. Consertadas, e agora travadas por
>   `tests/test_guarda_ordem_rotas.py`, que varre a aplicação inteira. Na primeira execução a guarda
>   acusou **zero** rotas sombreadas fora do transporte — a dívida estava contida aqui.
> - **ABERTO — teto de 50 registros nas telas do transporte.** O commit `628ca34` (2026-07-20) passou
>   13 endpoints a devolver `Paginated`, e o `lib/api.ts` seguiu declarando array por onze dias. Como
>   `request<T>()` faz cast sem validar, o `tsc` ficava verde e o navegador estourava com
>   `TypeError: ….map is not a function` — e, onde o código fazia `data?.length`, a tela dizia
>   "nenhum registro" com registros no banco. Os 12 métodos agora declaram `Paginated<T>` e as telas
>   consomem `.items`. **Consequência que não foi resolvida:** essas telas não têm UI de paginação e o
>   `page_size` padrão é 50, então exibem no máximo 50 registros. Não é regressão (antes exibiam zero
>   ou estouravam), mas é teto real. Resolver exige decidir UI de paginação — decisão de produto.
> - ~~**ABERTO — a busca de alvarás é client-side sobre a lista já truncada.**~~ **FECHADO em
>   2026-08-04.** `GET /transporte-regulado/alvaras` passou a aceitar `q` (substring em
>   `numero_alvara`, `lower(...) LIKE lower(...)`, idioma de `routers/_crud.py`), e a tela manda o
>   termo para o servidor com debounce de 300 ms em vez de filtrar `items`. Dois achados de
>   passagem: (1) o termo já estava na `queryKey` **sem ir para a API**, então cada tecla
>   invalidava o cache e refazia a mesma requisição; (2) as condições do service estavam
>   **duplicadas** entre a consulta e a contagem — filtro acrescentado a só uma das cópias faria
>   `total` divergir de `items`. Agora são montadas uma vez. O estado vazio também distingue "não
>   há alvarás" de "a busca não achou": a segunda mensagem não oferece "cadastrar", que convidaria
>   a duplicar um alvará existente. Cinco testes de service + um HTTP que prova a FIAÇÃO (um `q`
>   declarado no router e esquecido na chamada ao service passaria em toda a bateria de service).
>   Provados por inversão: sem o filtro, 4 dos 5 ficam vermelhos.
>
> - ~~**ABERTO — falta guarda para a classe de defeito do contrato de paginação.**~~ **FECHADO em
>   2026-08-04** (detalhe no fim deste item). A ordem de rotas
>   ganhou `tests/test_guarda_ordem_rotas.py`, que varre a aplicação inteira e travou a classe de
>   defeito das 422 por sombreamento de rota. O contrato `Paginated` (item acima, teto de 50) não
>   ganhou guarda equivalente: nada reprova hoje o próximo `response_model=Paginated[...]` no backend
>   cuja contraparte em `frontend/lib/api.ts` declare array simples em vez de `Paginated<...>` — e foi
>   exatamente essa classe de defeito que produziu `TypeError: ….map is not a function` no navegador
>   por onze dias, com o `tsc` verde o tempo todo. Duas formas possíveis de guarda, nenhuma construída
>   ainda: (1) um teste/script que compara os `response_model=Paginated[` do backend com os
>   `request<Paginated<` do `api.ts` e reprova divergência; (2) validar o envelope `{items, total,
>   page, page_size}` dentro do `request<T>()` genérico, em vez de confiar no cast estático.
>
>   **FECHADO em 2026-08-04 pela opção (1):** `backend/tests/test_guarda_contrato_paginado.py`
>   varre `app.routes` (o objeto real, não o fonte) e cruza com as chamadas GET de `api.ts`. Pega
>   as duas direções — endpoint paginado tipado como array, e cliente esperando envelope de rota
>   que não pagina. No estado atual: **zero divergências**, 6 endpoints pulados por não serem
>   consumidos pelo frontend.
>
>   Duas coisas a saber antes de mexer nela. **O container do backend monta só `./backend`**, então
>   `frontend/lib/api.ts` não existe lá; o CI roda pytest no runner com o repositório inteiro. A
>   guarda **pula fora do CI e FALHA com `CI=1`** — sem essa assimetria explícita ela sumiria em
>   silêncio no único lugar onde roda. E o extrator é **varredura por caractere, não regex**: a
>   primeira versão usava `request<(.+?)>\(` com `re.S`, e o `.+?` atravessava linhas e comentários
>   até achar um `>(` qualquer, porque `>` também fecha genérico aninhado (`Paginated<X>>`) — o
>   "tipo" capturado continha blocos inteiros do arquivo e a guarda ficava verde comparando lixo.

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
