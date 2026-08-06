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
    inversão).
  - **F4** (2026-08-06) — fecha a modularização. Era menor do que este documento anunciava, e um
    dos três itens **já estava feito**: `Sidebar.tsx` não é "a antiga" desde a F2 — ela consome
    `lib/menus` (`MENUS`, `menuDoModulo`, `canSeeItem`), não tem `NAV` próprio e é o componente
    vivo do layout. Não havia nada a deletar; a afirmação estava velha. Os outros dois eram reais e
    pequenos: os modelos `ModuloLegado`/`ConfiguracoesModulosLegado` (mapeamento morto das tabelas
    do PHP, zero usos fora de `models/`) saíram do ORM, e `link_url` passou a nascer com
    `/m/<slug>/`.
    O que fica de durável é a **guarda** (`tests/test_guarda_link_url.py`), não a linha corrigida:
    havia **um** escritor de `link_url`, e um só se conserta à mão. O problema é o segundo — a
    P5.3 deixou a "notificação automática por job" do transporte explicitamente em aberto, e esse
    job vai gravar `link_url`. Sem guarda ele nasce legado e ninguém percebe, porque o 308 faz
    funcionar. Duas asserções, ambas invertidas, uma delas controle contra verde por vacuidade.
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

### ~~1.0.01 Postgres da VPS respondendo da internet~~ — FECHADO em 2026-08-05

**O achado mais grave registrado neste documento até hoje.** Apareceu ao conferir um relatório
externo que dizia, genericamente, "fechar portas diretas de banco e backend". A verificação mostrou
que não era genérico:

- `5432`, `8000` e `3100` aceitavam conexão de fora em `103.230.142.69` (só a `8090` deveria).
- Sonda de `SSLRequest` na 5432 respondeu `N`: Postgres real, **sem TLS**.
- A senha estava **literal** no `docker-compose.yml` (`ged_password_secure_local`, não `${VAR:-}`),
  e este repositório é **público**.
- `ged_user` é `SUPERUSER` com `BYPASSRLS` — as camadas 1, 2 e 3 do isolamento multi-tenant são
  todas irrelevantes para quem entra por ali.

Não se tentou autenticar: a correção é a mesma com ou sem a prova, e o servidor tem dados reais de
homologação.

**Isto era anterior ao `SEC-RLS-ROLLOUT`, e não o contrário.** Trocar o papel do runtime não protege
nada enquanto `ged_user` for alcançável direto na 5432.

Conserto em duas camadas:

1. **Compose** — toda porta passou a `127.0.0.1:`, menos a `8090`. É o conserto de verdade, porque
   sobrevive a `docker compose up` e a reboot. Guarda: `tests/test_guarda_portas_publicadas.py`.
2. **Firewall na VPS** — unidade systemd `aprimora-fecha-portas` (`/usr/local/sbin/aprimora-fecha-portas.sh`),
   `After=docker.service`, idempotente, inserindo `DROP` em `DOCKER-USER` para `eth0`. Defesa em
   profundidade; continua válida se alguém republicar uma porta por override.

Duas armadilhas que custaram uma rodada cada, e que valem para qualquer bloqueio futuro:

- **`ufw` não alcança porta publicada por container.** O Docker insere DNAT em `PREROUTING`, que
  desvia do `INPUT`. Por isso a regra vai em `DOCKER-USER`, e não em `ufw`.
- **O DNAT reescreve a porta ANTES da `DOCKER-USER`.** A regra tem de casar a porta de *dentro* do
  container. Com o mapeamento `3100:3000`, bloquear `3100` não fez nada — a 3100 seguiu aberta na
  verificação, e só fechou ao bloquear `3000`. As outras duas funcionaram por acidente, sendo
  `5432:5432` e `8000:8000`.

**Pendente, e é decisão do Jorge:** a senha `ged_password_secure_local` continua no repositório
público e continua sendo a do banco da VPS. Fechar a porta reduz a exposição, não a elimina — quem
tiver alcance à rede interna, ou uma futura porta republicada por engano, entra com uma credencial
publicada. Rotacionar **não** é editar o compose: `POSTGRES_PASSWORD` só age na criação do volume,
então a troca é `ALTER ROLE ged_user PASSWORD ...` mais as URLs de conexão.

### ~~1.0.02 Download de anexo ignorava o sigilo do processo~~ — FECHADO em 2026-08-05

`GET /anexos/{id}/download` e `GET /anexos/{id}/carimbado.pdf` exigiam só `get_current_user` e
chamavam o carregador cru `get_anexo_path`, que filtra tenant, `excluido` e `ativo` e mais nada.
Qualquer autenticado do tenant baixava o anexo de um processo **ultrassecreto** iterando `anexo_id`.

O que torna o caso instrutivo é que **a barreira existia**: `services/sigilo.py` implementa a LAI
com cinco níveis, `assert_acesso_processo` é o guard reaproveitável, e ele já estava aplicado em
quatro lugares — inclusive no download **pela via de assinatura** (`services/assinaturas.py:514`).
A listagem de processos filtra por `nivel_sigilo` desde sempre. Só a via direta de anexo ficou de
fora, e nenhum teste cruzava anexo com sigilo.

Três razões pelas quais isso sobreviveu, todas reaproveitáveis:

- **`require_permission` não cobre sigilo.** São eixos diferentes. Um endpoint pode estar
  corretamente gateado por permissão e módulo e ainda assim entregar documento sigiloso.
- **O endpoint não menciona processo.** A assinatura fala em `anexo_id`; o processo só aparece
  depois do join. Uma varredura por "endpoints de processo" não acha este.
- **Teste de service não pega.** `test_sigilo_enforcement.py` testa serviço e passava; o defeito
  morava na costura router↔service — o mesmo lugar dos três 422 por sombreamento de rota e das dez
  rotas do transporte com `action` inexistente.

Conserto: `get_anexo_path_autorizado` resolve o processo dono pelo vínculo e aplica o guard. Guarda
estrutural proíbe router de chamar o carregador cru. Duas decisões registradas no docstring — a
autorização vem **antes** de resolver o arquivo (senão a mensagem distingue "existe" de "não
existe"), e anexo **sem vínculo ativo é negado** (fail-closed; medido: 16 anexos ativos, 0 sem
vínculo).

**O que este item NÃO fecha:** o eixo de *permissão* sobre anexo continua aberto. O download segue
sem `require_permission` — qualquer autenticado do tenant baixa anexo de processo **ostensivo** que
talvez não devesse ver. É a mesma lacuna do item 1.0.8, e a decisão é do Jorge, porque mexer nisso
muda política de acesso.

### ~~1.0.03 A VPS não tinha backup~~ — FECHADO em 2026-08-05, com uma ressalva aberta

Estado medido antes: **um** arquivo em `/root/backups`, `pre_migration_20260724_031052.sql.gz`,
43 KB, de 24 de julho. `crontab -l` vazio, nenhum timer systemd de backup, nenhuma cópia fora da
máquina. Doze dias de dado operacional em homologação sem rede de segurança nenhuma.

O `backup_database` do `scripts/deploy.sh` existia e estava desligado por padrão. Mais grave que
estar desligado é como estava escrito:

```sh
docker compose exec -T db pg_dump ... > "$BACKUP_FILE" || log "Backup skipped"
log "✓ Backup saved to $BACKUP_FILE"
```

O redirecionamento cria o arquivo **antes** de o `pg_dump` rodar; o `||` engole a falha; e a linha
seguinte anuncia sucesso nos dois casos. Ligar `BACKUP_DB=1` teria produzido, num dia ruim, um
arquivo de zero byte com nome de backup e um log do CI afirmando que ele existe. É a mesma família
do export vazio que `app/cli/backup.py` já barra, e do backup sem contexto de tenant descrito no
docstring de lá: **artefato plausível e inútil, cujo defeito só aparece no dia do restore**.

Entregue: `scripts/backup-aprimora.sh` (banco `-Fc` + `pg_dumpall --globals-only` + uploads,
gerando em área de espera e publicando por `mv` só depois de verificar), `scripts/backup-verificar.sh`
(restore real num banco descartável, comparando as 198 tabelas contra o vivo), unidades systemd
versionadas em `deploy/systemd/`, e `test_guarda_backup.py` com 7 asserções, **todas provadas por
inversão**.

Duas coisas que só apareceram por rodar de verdade na VPS, e nenhuma teria aparecido na leitura:

- **A primeira execução publicou o backup e saiu com exit 2.** `ls "$dir"/aprimora_*` num diretório
  vazio sai com status 2, e sob `pipefail` isso derrubava o script na poda — *depois* de publicar.
  Com o timer, a unidade ficaria vermelha todo dia com o backup perfeito, e a retenção nunca
  rodaria. Corrigido com `nullglob`.
- **`app/cli/backup.py` cobre menos da metade do que parece.** `TENANTED_TABLES` tem 26 tabelas,
  congeladas na Fase 34; o banco tem hoje **55** com `tenant_id`. Transporte regulado, pagamentos,
  minuta, notificação, workflow e `audit_log` ficam de fora. Ele serve para migrar/clonar tenant,
  não como backup — o RUNBOOK agora diz isso em cima da seção.

**A ressalva, que continua aberta e é decisão do Jorge:** não há cópia **fora da máquina**. O que
existe protege contra `DROP TABLE`, migration ruim e apagão de dado; não protege contra perda do
servidor, ransomware ou o provedor sumir. Falta escolher o destino (bucket, segunda VPS, storage do
provedor) — a escolha tem custo e implica onde o dado do município passa a residir, então não é
chamada de agente.

Relacionado, e **já fechado na mesma sessão**: a unidade `aprimora-fecha-portas` (regras de
`DOCKER-USER`, item 1.0.01) existia **só na VPS**. Agora está em `deploy/vps/` +
`deploy/systemd/`, com duas correções que a versão do servidor não tinha — `set -euo pipefail` e
descoberta da interface pela rota default, falhando se ela não existir, porque regra com `-i
<interface inexistente>` é aceita sem reclamar e **nunca casa pacote nenhum** (unidade verde,
`iptables -L` mostrando tudo, portas abertas). O Redis entrou na lista: estava a salvo pelo bind em
`127.0.0.1`, mas fora desta camada. `test_guarda_portas_publicadas.py` agora cruza o compose com a
lista `PORTAS=` e reprova serviço publicado que o firewall não cubra.

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

### ~~1.0.95 `Deploy to VPS` corria em paralelo com os testes~~ — FECHADO em 2026-08-04

Os quatro workflows disparavam juntos em `push` para `main`, então a VPS recebia código **mesmo
quando a suíte reprovava**. Não era hipótese: aconteceu no push `a1a0c8e` (fatia P5.1) — `Backend
tests` vermelho por um `usuario_id=1` cravado num teste, `Deploy to VPS` verde, código na VPS.

O gatilho do deploy passou a ser `workflow_run` sobre o **`Backend tests`**, mais um job `gate` que
confere por API se os outros dois workflows terminaram em `success` **no mesmo SHA**.

Três decisões que não são óbvias ao ler o YAML:

- **Um workflow só no gatilho, não os três.** `workflow_run` com vários workflows dispara uma vez
  por workflow que termina, e não uma vez quando todos terminam — três gatilhos poderiam iniciar
  dois deploys simultâneos. Pior: `concurrency: cancel-in-progress` interromperia um deploy no
  meio. O `Backend tests` é o gatilho por ser o mais lento (~8 min contra ~1 min dos outros).
- **O filtro `paths:` foi removido**, porque `workflow_run` não aceita filtro de caminho. A troca é
  deliberada: o pior caso agora é um build de ~5 min desperdiçado num push só de documentação,
  contra o antigo "meu código não está na VPS e não sei por quê", que é silencioso.
- **`workflow_dispatch` passa direto pelo portão** — continua sendo o escape manual.

**ABERTO, e é outro problema:** o `deploy.sh` faz `git reset --hard origin/main` na VPS, então o que
sobe é o `main` **do momento do deploy**, não o SHA que foi testado. Commit novo que entre em `main`
entre o fim dos testes e o deploy vai junto, sem ter passado pelo portão. Resolver exige o workflow
passar o SHA e o `deploy.sh` fazer checkout dele.

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

- **P5** — Recadastramento. **P5.1 e P5.2 entregues em 2026-08-04**; P5.3 segue aberta (detalhe
  logo abaixo).
- ~~**P6** — Rotas / linhas~~ → **pontos e vagas, entregue em 2026-08-06** (detalhe abaixo). Linha/itinerário continua aberto.
- **P7** — Ocorrências regulatórias
- **P8** — Workflows avançados

> **P5.1 entregue em 2026-08-04** — ciclo, convocação, escalonamento e ajuste de prazo. Spec e
> plano em `docs/superpowers/`. O município cria o ciclo, manda gerar, e vê **quem tem de vir e
> quando**; a tela vive em `/m/transporte/recadastramento`.
>
> Três decisões que valem mais que o código:
>
> - **`Permissionario.situacao` usa masculino (`ativo`) e `Empresa.situacao`, feminino (`ativa`).**
>   Filtrar `"ativo"` nos dois convoca **zero empresas sem erro nenhum**, e um teste que olhasse só
>   o total passaria. O teste afirma sobre cada vínculo em separado; invertido, fica vermelho.
> - **A idempotência da geração mora no banco**, em dois índices únicos parciais, não num
>   `if not exists` — duas execuções concorrentes do endpoint passariam as duas pela checagem.
>   Mesma lógica para o vínculo exclusivo (`CHECK`, não só validação de serviço).
> - **Escalonamento pelo final do CPF/CNPJ**, nunca por `numero_permissao` ou `data_nascimento`:
>   os dois são anuláveis, e empresa não tem nascimento. Documento sujo cai na faixa final em vez
>   de derrubar a geração inteira.
>
> **Editar a janela de um ciclo já gerado NÃO remarca ninguém** — remarcar em massa prazo já
> comunicado é decisão de produto, e a alternativa silenciosa seria pior. Fica registrado como
> limite conhecido, não como defeito.
>
> **P5.2 entregue em 2026-08-04** — atendimento e fechamento. Spec e plano em `docs/superpowers/`.
> Migration `0082` com três tabelas: `recadastramento_item` (catálogo por tenant),
> `recadastramento_marca` (log append-only) e `recadastramento_decisao`. Telas em
> `/m/transporte/recadastramento/itens` e `.../[id]/convocacao/[convocacaoId]`.
>
> Quatro decisões que o código sozinho não explica:
>
> - **Deferir exige completude; indeferir não.** É a assimetria central. Indeferir por falta de
>   documento é o caso real do balcão; exigir completude para indeferir deixaria o sistema só
>   sabendo dizer sim. Travado por `test_indeferir_sem_completude_e_permitido`.
> - **A marcação é log, não estado.** `recadastramento_marca` **não tem** índice único em
>   `(id_convocacao, id_item)`, e a ausência é o desenho: marcar, desmarcar e marcar de novo são
>   três linhas, e a mais recente vence. Um único ali apagaria o rastro de quem voltou atrás.
> - **`marcado is None` não é `False`.** Ninguém-olhou e olhou-mas-não-está-em-ordem são coisas
>   diferentes, e a tela mostra as duas.
> - **`condicional` não é `aprovado`.** A amarra da vistoria exige `aprovado`; aceitar condicional
>   seria decisão de produto.
>
> Duas assunções permissivas, marcadas como reversíveis na spec: regulado **sem veículo** satisfaz
> a amarra por vacuidade (a tela distingue de "todos em dia"), e vistoria **sem `data_validade`**
> conta como válida (cadastro herdado costuma não ter, e bloquear por falta de dado puniria o
> regulado por falha do município).
>
> **Limite conhecido:** editar a `descricao` de um item muda o texto exibido em fechamentos
> antigos. Preservar o texto no momento da marca resolveria, ao custo de duplicar dado.
>
> **P5.3 entregue em 2026-08-05** — atraso, faltosos, suspensão e reativação. Spec e plano em
> `docs/superpowers/`. Migration `0083`: dois tipos novos de decisão (`suspensao`, `reativacao`) e
> `recadastramento_notificacao`. Telas em `.../[id]/faltosos` e os atos no atendimento.
>
> **O atraso NÃO virou coluna.** É derivado (`prazo < hoje AND situação aberta`), calculado na
> consulta. Persistir exigiria job diário e criaria janela em que o banco discorda do calendário;
> pior, o ajuste de prazo da P5.1 teria de lembrar de recalcular, e esquecer seria silencioso. O que
> torna isso seguro é o atraso **não gatear nada** — decisão do Jorge: quem perdeu o prazo continua
> podendo ser atendido, só a suspensão fecha. Se um dia o atraso passar a bloquear, a escolha tem de
> ser reexaminada.
>
> **A suspensão atinge só a convocação** — não muda `Permissionario.situacao`, `Empresa.situacao`
> nem alvará. Há teste só para isso, porque "melhorar" a suspensão para refletir no cadastro
> passaria despercebido e teria efeito no módulo inteiro.
>
> Sem entidade de recurso: `suspensao` e `reativacao` são atos com parecer na mesma trilha
> cronológica de `recadastramento_decisao`. A reativação é o deferimento do recurso e o parecer é o
> julgamento. Consequência: **não há prazo para interpor recurso**. Se o município precisar cobrar
> esse prazo, é fatia própria.
>
> Três coisas que só apareceram lendo o código, e não supondo:
>
> - `SITUACOES_ABERTAS` já fazia a suspensão bloquear checklist e decisão **sem uma linha nova** —
>   mas as mensagens dos 409 mandavam *reabrir*, e para suspensa o caminho é *reativar*.
> - `TIPOS_DECISAO` estava definido e **não era usado por ninguém**; `decidir_recadastramento`
>   validava contra um literal. Agora espelha o CHECK.
> - `recadastramento_convocacao.situacao` **não tem CHECK** — o vocabulário é imposto só pelo
>   serviço. Por isso `suspenso` não exigiu nada do banco. Não foi acrescentado agora para não mudar
>   a premissa da P5.1 num PR que não é sobre isso.
>
> **Ainda aberto do recadastramento:** notificação automática por job (o registro de envio já
> existe, então falta só o gatilho) e o efeito da suspensão sobre alvará.

> **P6 entregue em 2026-08-06 — mas não é o que o roadmap dizia.** Spec e plano em
> `docs/superpowers/`. Migration `0084` com `ponto` e `ponto_ocupacao`; telas em
> `/m/transporte/pontos` e `.../pontos/[id]`.
>
> **"Rotas / linhas" eram duas coisas, e táxi e mototáxi — o volume do balcão — não têm nenhuma
> das duas: têm PONTO.** Uma tabela genérica tentando servir ponto e linha serviria mal aos dois.
> Decisão do Jorge: esta fatia é o ponto. O card do hub virou dois — "Pontos e Vagas" (entregue) e
> "Linhas e Itinerários" (por fazer, distrital e escolar).
>
> Quatro escolhas, todas registradas na spec: vaga **numerada**, ocupante é o **permissionário**,
> ocupação é **log com vigência**, e o ponto **não bloqueia nada**.
>
> **A exclusividade mora em dois índices únicos parciais, não num `if`.** Duas requisições
> concorrentes de "ocupar a vaga 3" passariam as duas por uma checagem de serviço — entre o `SELECT`
> e o `INSERT` não há nada segurando. `test_o_banco_barra_sem_passar_pelo_servico` contorna o
> serviço e insere direto, esperando `IntegrityError`; sem ele, apagar os índices manteria a bateria
> verde.
>
> **Não existe tabela de vaga:** a vaga é o inteiro `numero_vaga`. Uma tabela cujo único conteúdo é
> um número sequencial custaria join em toda leitura e daria o que os índices já dão.
>
> **Não há transferência atômica** — transferir é liberar e ocupar, dois atos. Entre um e outro a
> vaga fica disputável; limite conhecido, não descuido. O conserto, se um dia precisar, é um
> endpoint numa transação só.
>
> **Assunção imposta, marcada para conferir:** um permissionário ocupa no máximo uma vaga. Apertar
> agora e soltar depois é apagar um índice; o inverso exige limpar dado sujo que já entrou.
>
> Duas coisas que a fatia encontrou e consertou fora do próprio escopo:
>
> - **`listar_permissionarios` não tinha busca**, e o seletor de ocupante só enxergaria os 50
>   primeiros — inutilizável em município real. Ganhou `q` (nome OU CPF). De quebra, as condições
>   estavam **duplicadas** entre consulta e contagem: acrescentar `q` a só uma faria a tela mostrar
>   1 resultado dizendo "de 300". É o mesmo defeito que a busca de alvarás corrigiu, na função ao
>   lado.
> - **A guarda de página órfã não pegava o caso principal.** Removendo o card do hub E o item do
>   menu de `/m/transporte/pontos` ela seguia verde, porque o breadcrumb do detalhe cita a lista e a
>   lista cita o detalhe — duas páginas do mesmo recurso referenciando uma à outra parecem citadas,
>   com o recurso inteiro inalcançável. Exatamente o buraco que deixou Alvarás e Relatórios
>   invisíveis por meses. Agora cada rota é conferida contra as fontes de **fora do próprio
>   subdiretório**, com três provas por inversão, uma delas de controle.
>
> **Segunda vez nesta sessão que uma guarda verde não guardava nada** — a primeira foi o teste de
> "liberar não apaga", que passava mesmo com a linha sendo soft-deletada, porque a asserção
> consultava a tabela crua sem filtrar `excluido`. As duas só apareceram por inversão.
>
> **Ainda aberto do P6:** linha/itinerário (distrital, escolar), fila de espera por vaga e
> geolocalização — todos fora de escopo por decisão, e registrados na spec.

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
