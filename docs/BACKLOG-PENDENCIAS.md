# Backlog de pendências

> **Status:** vivo · **Autoridade sobre:** O que está em aberto. Fonte viva — toda evidência aqui leva data.
> **Última verificação:** 2026-08-27 (último commit que tocou este arquivo).
> Índice: [docs/INDEX.md](INDEX.md) · precedência: código > `CLAUDE.md` > este doc.


**Levantado em:** 2026-07-28 · **Método:** verificação direta no código e no `git`, não em memória de sessão.

> **Leia isto primeiro (você, agente):** nenhum item deste documento está autorizado a ser
> iniciado. O processo do repositório é **escopo fechado em doc → autorização humana →
> implementar → testes → autorização → commit**. Este arquivo existe para que a próxima sessão
> não precise redescobrir o estado; ele **não** é uma lista de tarefas a executar.
>
> Cada item traz a **evidência** que sustenta a afirmação. Antes de agir sobre qualquer um,
> reconfirme a evidência — o repositório se move.
>
> **Varredura completa mais recente: 2026-08-14.** Quatro itens foram remedidos nela e os quatro
> estavam errados; a causa comum e as regras que saíram dali estão na seção 4, em "Toda evidência
> leva data".

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
- ~~**Ambiente local do Jorge:** o antivírus AVG intercepta HTTPS e nenhuma imagem docker rebuilda
  nessa máquina.~~ **RESOLVIDO em 2026-08-07** — a imagem rebuilda. O parágrafo aparecia **duas
  vezes, idêntico**, e nenhuma das duas cópias tinha sido atualizada; ambas foram substituídas por
  esta linha em 2026-08-14.

**Estado em 2026-08-14** (varredura completa do arquivo — ver a nota de método na seção 4):

- `main` em `84d3f04`. Migrations até **0091** (head único, 92 arquivos; em 2026-08-24 já vamos em
  **0097**, ver o bloco P8 na seção 2.2).
- CI verde nos três workflows; suíte de backend em **1304 passed / 0 failed / 47 skipped**.
- Entregue desde o último bloco: modularização F1–F4, leitura por módulo, item 1.0.8 (58 GETs com
  `require_permission`), assistente IA-1 sobre DeepSeek, Pagamentos Onda C fatia C1 inteira
  (C1.1 → C1.3), reparo de grants de baseline (item 1.1.4).
- **Branch remota não é sinal de trabalho pendente.** `git branch -r --no-merged origin/main` lista
  ~10 branches, e isso é artefato do merge por **squash**: o commit da branch nunca fica alcançável
  a partir de `main`, mesmo com o conteúdo todo lá dentro. Conferir por conteúdo, nunca por
  alcançabilidade — e as remotas antigas podem ser apagadas.

> **Atualizado em 2026-07-28 (quatro itens fechados, removidos conforme a seção 4):**
>
> - **PR #12 — UI da conciliação bancária: mergeado** (`e19e551`) e deployado. A Onda B de
>   pagamentos está fechada ponta a ponta. Detalhes na descrição do PR e em `CLAUDE.md`.
> - **"59 ocorrências de TODO/FIXME": não existem.** A contagem era artefato de medição — uma
>   busca *case-insensitive* por `todo` casa com a palavra portuguesa "todo/todos", onipresente
>   num repositório em pt-BR. Contagem correta (`grep` sensível a maiúsculas por `TODO`/`FIXME`/
>   `XXX`/`HACK`): **4 no backend, 0 no frontend**. Desses 4, **3 são a palavra "TODOS" em caixa
>   alta** dentro de docstrings. Sobra **um TODO real**, em `routers/minutas.py`
>   — "Pull DOCX, extract text, update corpo_html" —, que já é o item **2.4** deste documento.
>   Não há dívida oculta em marcadores; não repetir esta varredura.
>   *(Remedido em 2026-08-14: hoje são **2** no backend e **0** no frontend — um é a palavra
>   portuguesa em `cli/backup.py`, o outro é o mesmo TODO real, agora em `minutas.py:303`. A
>   conclusão do item se manteve; os números e a linha, não. Este é o motivo de a nota de método
>   pedir data em toda contagem.)*
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

### 1.0 Deriva de `APP_NAME` — MEDIDO em 2026-08-14; a descrição de 07-28 estava vencida

*(Descoberto em 2026-07-28, durante a fatia F1. **Remedido em 2026-08-14, e quase nada do texto
original continuava verdadeiro** — o item pedia "verificar na VPS antes de decidir o conserto", e
foi essa verificação que o desmontou.)*

O que o item afirmava e **não** é mais verdade: que o local tinha duas linhas em `utils.sistema`,
que o container rodava com `APP_NAME=aprimora`, e que um `docker compose up -d` derrubaria as
permissões do admin. Também não é mais verdade a "consequência já visível": a suíte fecha
1304/0 hoje, `test_pr5a_dashboard_servicos` incluído.

**Estado real, medido:**

| | `utils.sistema` | `APP_NAME` | veredito |
|---|---|---|---|
| local | 1 linha: id 1 `sistemas`, 25 transações | `sistemas` | alinhado |
| VPS | 2 linhas: id 2 `aprimora` **0 transações**; id 3 `sistemas` 25 | `sistemas` | roda no certo |

Na VPS há um `Administradores` duplicado, um em cada sistema, com o **mesmo** `admin@local.test`
nos dois. Em execução está tudo correto — mas a linha órfã é uma armadilha, e ela não falha do
jeito que o item supunha. `APP_NAME=aprimora` não daria 403 em tela nenhuma: o admin continua
super-usuário (o nível é 0), e o ramo de SU lê `utils.sistema_transacao` **daquele** sistema, que
tem zero linhas. O resultado é **catálogo vazio** — todas as telas somem, e nada vai para o log.
Um erro barulhento seria melhor.

**O que foi feito:** `app.cli.diagnostico_permissoes` passou a abrir com a seção "Sistema ativo",
que confronta `APP_NAME` com `utils.sistema` e aponta linha órfã, `app` ambíguo, ausência de
correspondência e catálogo vazio. A lógica é uma função pura (`avaliar_sistema`) com teste de
tabela — teste que lesse o banco passaria verde para sempre no dev local, que tem uma linha só e
alinhada, sem nunca exercitar um caso ruim.

**O que continua aberto, e é decisão sua:** apagar a linha `aprimora` (id 2) e o grupo órfão na
VPS. É mutação de dados em homologação, não faço sem sua palavra. Enquanto ela existir, a
armadilha existe — agora com um espelho que a mostra.

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
  > *Remedido em 2026-08-14:* `ENDPOINTS_LEITURA_SEM_GATE` está **vazia** desde o item 1.0.8 — os
  > 7 ganharam gate. E `test_usuario_sem_permissao_continua_lendo`, citado logo acima como a guarda
  > da propriedade central, **não existe mais**: o 1.0.8 o partiu em
  > `test_require_modulo_nao_olha_o_usuario` (a propriedade, agora com controle de vacuidade) e
  > `test_usuario_sem_permissao_agora_leva_403` (o comportamento novo). A propriedade continua
  > travada; o nome, não.
- A tabela `ROTAS_POR_MODULO` (mesmo arquivo) é a fonte versionada de qual módulo cada rota exige,
  checada contra a implementação real por introspecção no CI — substitui a lista solta que este item
  citava antes.
- **O que NÃO fechou, e não é a mesma coisa:** a contratação responde "o tenant tem o módulo?", não
  "este usuário pode ler isto?". Todo autenticado do tenant continua lendo `/usuarios`, `/grupos`,
  `/audit` etc. — isso é o item **1.0.8**, aberto de propósito por esta fatia.

### 1.0.66 A suíte de backend cresceu para além do teto do CI — METADE ERA DUPLICATA

O job levava 13–14 min contra um teto de 15; os ~40 testes da F1 empurraram por cima e o teto subiu
para 30 (`c51e8a4`). **Subir de novo não é o conserto** — está escrito no próprio workflow.

Este item passou semanas propondo `pytest-xdist` com banco por worker — trabalho grande, arriscado,
e que mexeria justamente nos testes de RLS, que dependem do Postgres compartilhado. **Ninguém tinha
medido onde o tempo ia.** Medido em 2026-08-16, job `95111304477`:

| passo | tempo |
|---|---|
| bootstrap inteiro (dump + migrations + seeds) | **35 s** |
| `Run pytest` | 8 min 49 s |
| `Coverage report` | **10 min 11 s** ← a mesma suíte de novo, instrumentada |

O passo de cobertura rodava `pytest tests/` **inteiro pela segunda vez**. Mais da metade do job era
duplicata, e o bootstrap — o suspeito óbvio — era 3% dele.

**Fechado em 2026-08-16** juntando cobertura na mesma execução: ~19 min → ~10 min, sem tocar em
paralelismo. Os dois runs já fechavam `1378 passed`, então o `|| true` do passo antigo não
mascarava nada. Guarda em `tests/test_guarda_suite_unica_no_ci.py`, com controle para que apagar a
cobertura não passe verde — duplicar a suíte **não quebra nada**, só custa, e por isso volta em
silêncio.

**Continua aberto** o crescimento em si: ~10 min contra teto de 30 dá folga por um bom tempo, mas a
suíte segue serial por dependência real (um Postgres, RLS). Quando voltar a apertar, aí sim vale
`pytest-xdist` com banco por worker — e a lição aqui é medir os passos antes de escolher o remédio.

### 1.0.7 As 9 transações da 0074 não estão concedidas a nenhum grupo

*(Levantado em 2026-07-30 pelo review final da F1. Decisão: **fica documentado, não automatizado** —
ver abaixo por que uma migration de concessão não é escrevível sem definir política de acesso.)*

A migration `0074` criou 9 transações (`processo`, `usuario`, `catalogo`, `assunto`, `manifestante`,
`cidade`, `endereco`, `workflow`, `unidadeTrabalho`) e a Task 8 gateou 13 endpoints sobre `processo`
e `workflow` — entre eles `routers/workflow.py:479` (transicionar, usado pelo
`ProcessoWorkflowPanel.tsx`) e os 4 disparos de job em `routers/jobs.py`. Nenhuma dessas transações
tem linha em `utils.grupo_transacao`.

> ⚠️ **ATUALIZAÇÃO 2026-08-11 — a premissa "zero grupos não-SU" CAIU no ambiente de dev.**
> O `seed_demo_operacional` (pagamentos) **cria o nível "Operacional" (valor 1) sob demanda** e um
> grupo por transação de pagamentos. Medido com a CLI nova: o banco local tem **5 grupos não-SU**
> (`Demo — Autorizar Pagamento`, `Demo — Gestão da pasta`, `Demo — Pagar — Tesouraria`,
> `Demo — Solicitar Pagamento`, `Demo — Validar Pagamento`), **todos sem nenhuma das 9**. O gatilho
> que este item descrevia como futuro já disparou.
>
> **Na VPS ainda não** (medido em 2026-08-11): 0 grupos não-SU, 2 grupos totais, e `utils.nivel` só
> tem `Super Usuario=0` — o seed operacional não rodou lá. Ou seja, o item continua latente **em
> produção de homologação** e já é real em dev; roda o seed de pagamentos na VPS e vira real lá
> também.
>
> **Ferramenta:** `docker exec aprimora-py-backend python -m app.cli.diagnostico_permissoes
> --tenant sobral` lista, por grupo não-SU, o que falta. **Ela não concede nada** — conceder é a
> decisão de política descrita abaixo, e continua sendo do dono do produto.

- **Não afeta ninguém hoje**, e não por sorte: `is_super_usuario` é `nivel.valor == 0`
  (`services/permissoes.py:92`), e o ramo de SU lê `utils.sistema_transacao` e **não**
  `grupo_transacao` — então todo grupo super-usuário passa independentemente destas 9. O que mudou é
  que já existem grupos não-SU (ver acima); eles simplesmente não usam os endpoints gateados nesses
  códigos, porque são grupos de demonstração de pagamentos.
- **Aparece de verdade quando um grupo não-SU precisar de uma tela gateada nessas 9 transações.**
  Nesse momento, quem cria/edita o grupo escolhe as transações dele — passo já documentado em
  `RUNBOOK.md`, e agora conferível pela CLI acima.
- **Por que não virou migration:** concessão em bloco **abriria** acesso em vez de preservar. As 9
  transações são novas, então nenhum grupo as tinha; endpoints antigos gateados em `processo,excluir`
  já eram 403 para não-SU antes da branch. Conceder tudo daria a um Operacional o poder de excluir
  processo, que ele nunca teve. Escrever a migration correta exige decidir, código por código e ação
  por ação, quem passa a poder o quê — isso é política de acesso, decisão do dono do produto.
- ~~**A verificar antes de criar grupo não-SU na VPS**~~ — **feito em 2026-08-11**, resultado no
  aviso acima. A CLI `diagnostico_permissoes` substitui a query manual e cobre os dois ambientes.

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

### 1.1.6 A suíte deixa tenants para trás — 4.032 no banco local em uma semana

*(Descoberto em 2026-08-14 pela varredura deste arquivo, medindo outra coisa.)*

`aprimora_py.tenant` tem **4.033** linhas no dev local. Uma é `sobral`; as outras 4.032 casam o
padrão de teste (prefixo + `uuid4().hex[:8]`) e foram criadas entre **2026-08-07 e 2026-08-14** —
ou seja, **uma semana** de execuções da suíte.

Distribuição por prefixo (topo): `p52` 845, `p51` 429, `vis` 403, `alv` 377, `doc` 247,
`alvdoc` 221, `alvresp` 195, `alvren` 182, `exc12` 156, `gdocs` 155, `ia1` 133.

- **Não é a fixture `two_tenants`** — ela apaga no teardown, e a lista de tabelas dela é explícita.
  São os testes que criam tenant por conta própria, majoritariamente do transporte regulado.
- **O CI não sofre**: banco novo a cada run, nada acumula. Só banco de dev de vida longa acumula —
  e é exatamente onde ninguém olha.
- **Custo:** ~~a suíte levou 34 min numa medição e 2 h 16 noutra~~ — **essa inferência não se
  sustentou.** Uma terceira medição deu **7 h 22**, e medir a limpeza isoladamente mostrou que ela
  custa ~0 (15,2 s contra 14,9 s no mesmo módulo, dentro do ruído). As três rodadas foram
  concorrentes com outro trabalho na máquina, então **o tempo de suíte aqui não mede nada** e não
  deve ser usado como argumento. O que continua verdade é o custo estrutural: E
  `python -m app.cli.diagnostico_permissoes` **sem `--tenant`** percorre todos os tenants: hoje são
  4.033 iterações para um relatório que interessa sobre um.
- **Isto é insumo do item 1.0.66** (a suíte estourou o teto do CI): antes de partir para
  `pytest-xdist` com banco por worker, vale medir quanto do tempo é lixo acumulado.
**Entregue em 2026-08-14 — a realimentação e a vassoura, não o conserto:**

- **`app.cli.limpar_tenants_de_teste`** apaga o acumulado. `--dry-run` é o padrão; apagar exige
  `--apagar`. O classificador (`eh_tenant_de_teste`) é função pura com 27 testes, e a maior parte
  deles cobre o **falso positivo** — nome de município que se pareça com lixo de teste —, porque
  deixar lixo custa espaço e apagar tenant real custa o tenant. Deleta com
  `session_replication_role = replica`: `aprimora_py.tenant` recebe **97 FKs, 95 delas
  `NO ACTION`**, e ordenar 96 tabelas topologicamente seria uma lista que envelhece a cada
  migration.
- **O contador na `conftest.py`** imprime, ao fim de cada sessão, quantos tenants ela deixou para
  trás. **Relata, não reprova** — reprovar deixaria a suíte inteira vermelha antes de os 69
  arquivos serem convertidos, e vermelho permanente é exatamente o que escondeu o item 1.1.4.
  `PYTEST_FALHA_SE_VAZAR_TENANT=1` exige zero, para quem estiver convertendo.
- **Ensaio do mecanismo** (2026-08-14, com `ROLLBACK`): 4.032 tenants e **63.221** linhas
  dependentes em 96 tabelas, sem nenhum erro de FK. Maiores: `tenant_modulo` 20.060,
  `utils.usuario` 4.523, `audit_log` 4.098.

**O conserto, entregue em 2026-08-16:** `_limpa_tenants_do_modulo`, fixture `autouse` de escopo de
**módulo** na `conftest.py`. Apaga os tenants criados durante o módulo — `id >` o maior id de
entrada, então nunca alcança `sobral` nem tenant preexistente.

- **Uma fixture no conftest, e não teardown em 69 arquivos.** Editar 69 arquivos entregaria a mesma
  propriedade com 69 chances de esquecer uma — e teste que esquece o teardown continua **verde**,
  logo o esquecimento não teria sintoma. `autouse` não tem como ser esquecida.
- **Escopo de módulo por custo, não por gosto.** Apagar varre as 96 tabelas com `tenant_id`, e nem
  todas têm índice por ele: por função seriam ~96 × 1.300 varreduras; por módulo, ~96 × 100, com os
  ids em lote. Correção não é problema porque **nenhuma fixture deste conftest vive além da
  função** (conferido uma a uma).
- **Falha de limpeza não derruba o módulo** — o contador de sessão continua denunciando o que
  sobrou, e teste vermelho por causa da faxina seria pior que o vazamento.
- `PYTEST_NAO_LIMPAR_TENANT=1` desliga, para depurar olhando o que o teste deixou.
- Medido: `test_transporte_p5_2_atendimento.py` (28 testes) vazava 28 tenants e passou a vazar
  **zero**; lote de 6 arquivos, 85 testes, também zero.

**O acumulado de 4.032 continua no banco local** — decisão do Jorge em 2026-08-14 de receber a
ferramenta sem executá-la. A fixture impede o crescimento; quem apaga o que já está lá é
`limpar_tenants_de_teste --apagar`.

**Achado de carona, já consertado:** a rodada de validação cruzou a meia-noite e cinco testes de
frota caíram com `date(2026, 8, 16) == date(2026, 8, 15)`. Não tinha relação com a limpeza —
`HOJE = date.today()` era avaliado no import e comparado, horas depois, com data gerada pelo
servidor. Era **flake permanente**, não regressão: qualquer rodada que atravesse a meia-noite
reprova, e no CI (20 min) isso é ~1,4% das execuções. As seis asserções contra data server-side
passaram a usar `date.today()` na hora, e `HOJE` ficou só para deslocamentos, com a razão escrita
ao lado da definição nos quatro arquivos.

> **Nota histórica.** Até 2026-07-29 esta seção terminava com a linha "Nenhum — os quatro itens
> desta seção foram fechados em 2026-07-28". A execução da fatia F1 da modularização abriu os sete
> itens acima e a linha virou o oposto do que o arquivo mostra, então foi substituída por esta nota.
> Os quatro itens fechados em 28/07 continuam descritos na nota do topo do arquivo.

---

### Itens já fechados

Os 9 itens de curto prazo que fecharam entre 2026-08-03 e 2026-08-14 saíram
daqui para [BACKLOG-FECHADOS.md](BACKLOG-FECHADOS.md) — cada um com o diagnóstico
e a lição que produziu, que é a parte que continua valendo.

Ficaram nesta lista os fechados que deixaram **ponta solta** (o 1.0.03, cujo
backup ainda não sai da máquina): item com ressalva aberta não é item fechado.



## 2. Módulos com escopo declarado e não implementado

### 2.1 Pagamentos — Onda C — C1 ENTREGUE; C2 ENTREGUE em 2026-08-24

**Este item afirmou por semanas que "não existe nada", e estava errado desde a C1.1.** A frase
vinha de um `grep` feito uma vez e nunca refeito; quando a C1.3 foi desenhada, os endpoints da
C1.1 já existiam há dias — sem nenhuma tela que os chamasse, que é a razão de ninguém ter notado.
Fica registrado como o padrão a vigiar: **evidência datada envelhece em silêncio**, e "nenhuma
ocorrência" é a afirmação mais fácil de manter parada.

O que está no ar:

- **C1.1** (`8e4434d`, PR #15) — export CSV da lista de débitos. Nasceu **sem UI**: o endpoint
  existia e nenhuma tela o oferecia. A C1.3 foi quem pendurou o botão.
- **C1.2** (`cbb207d`, PR #16) — relatório de exceções. A RN-15 (autorização acima do saldo) era
  detectada por `LIKE` no texto da justificativa do histórico.
- **C1.3** (`e8be143` + `2311239`, PR #39) — duas coisas. A RN-15 virou **coluna estruturada**
  (`ordem_pagamento.excecao_saldo` + `justificativa_excecao`, migration `0091`, com backfill que
  extrai o texto já gravado), deixando de depender de casar prosa. E as quatro listagens que
  faltavam ganharam export: painel de caixa (CSV+PDF), extrato de conta (CSV), lançamentos de
  extrato (CSV) e ordens de pagamento (CSV+PDF) — todas com botão na tela, no mesmo PR.

~~O que falta — **C2, e continua bloqueado em spec externa**~~ → **C2 entregue em 2026-08-24.** O
bloqueio caiu por decisão do Jorge: formato próprio + adaptador no lugar de contrato externo. Spec
em `docs/superpowers/specs/2026-08-24-pagamentos-c2-integracoes-design.md`; contrato público em
`docs/INTEGRACAO-PAGAMENTOS.md`. O que entrou (migrations 0099–0103):

- **C2.2 — importador de extrato OFX/CNAB240** no pipeline existente de `importar_extrato`
  (dispatch por `formato`): parser OFX 1.x SGML + 2.x XML (scanner próprio, sem dependência),
  parser CNAB240 FEBRABAN (fixture como spec executável até chegar arquivo real do banco), dedupe
  por `(conta, id_externo)` (0099) — sem `id_externo` NUNCA pula: coincidência de data/valor vira
  AVISO de possível duplicata no relato, decisão do tesoureiro. Upload + relato na tela.
- **C2.1 — export contábil neutro `neutro-csv-v1`** com lotes imutáveis (0101): 5 tipos de evento
  do domínio real (`debito_empenhado`, `liquidacao`, `pagamento` com RN-15, `estorno_parcela`,
  `cancelamento_debito`), `id_evento` estável `tipo:id_origem`, reemissão devolve o mesmo lote
  (hash conferido), retardatário entra no lote seguinte; `ContabilAdapter` plugável para o dia em
  que o sistema contábil do piloto for definido. Tela de lotes.
- **C2.3 — API externa M2M** (0102/0103): realm próprio por API key (`X-Api-Key`, prefixo público
  + segredo bcrypt, escopos leitura/escrita, tenant DA CHAVE — divergência com o Host → 401),
  escrita idempotente (`Idempotency-Key`; replay devolve a resposta gravada; payload divergente
  409), leitura por cursor (`alterado_desde` para ETL), gate de módulo `pagamentos` do tenant,
  rate limit 120 r/m na borda. **Paridade entre portas é regra**: o liquidar M2M espelha
  `confirmar_liquidacao` exatamente (RN-01 é de `autorizar_lote`, que o M2M não expõe — um review
  pegou a porta M2M mais estrita que a interna e ela foi corrigida). Tela de gestão de chaves
  (segredo mostrado uma única vez).

Pendências registradas da C2:

- **Decisão de design a confirmar com o Jorge se a API crescer**: débito criado via M2M usa
  `sistema.id_usuario_criador` como solicitante (409 se ausente) — atribuição de autoria por
  máquina, decidida em implementação.
- A busca da chave por prefixo usa policy espelhada no precedente de `aprimora_py.tenant`
  (0103) para sobreviver ao `SEC-RLS-ROLLOUT`; teste sob `aprimora_app` trava o comportamento.
- Corrida de idempotência (dois requests simultâneos da mesma chave) coberta por unique + leitura
  de código; sem teste de concorrência real.
- `_motivo_de_descricao` trunca motivo que contenha ": " (primeira ocorrência); `numero_ne`
  preenchido depois do export não re-exporta o débito como `debito_empenhado` (limitação
  documentada no service).
- Tela de lotes mostra "Usuário #id" (schema sem nome do usuário); GET
  `/pagamentos/sistemas-integrados/{id}` sem teste HTTP direto.
- `possiveis_duplicatas` varre o histórico inteiro da conta a cada import — escalabilidade a
  observar; timing oracle no prefixo inexistente (prefixo é público — revisitar se mudar).

Continua fora (a "3ª etapa" do spec municipal): API bancária/PIX, remessa/retorno CNAB de
pagamento, PDF/OCR de extrato, adaptador contábil específico, XLSX (decisão C1 mantida).

- **XLSX não foi entregue e é decisão, não esquecimento.** CSV abre no Excel e não adiciona
  dependência; o PDF existe só onde há leitura de conferência (painel e ordens), e é gerado **a
  partir do mesmo CSV**, para que os dois números nunca divirjam.
- O próprio spec municipal joga **PDF/OCR de extrato e API bancária real** para uma "3ª etapa" —
  não confundir com o que a Onda C entrega.
- Contexto: Ondas A e B estão inteiras em produção (migrations 0063→0072).

**F2 do refactor de fluxo entregue em 2026-08-25** (branch `pagamentos/f2-ajustes-versionamento`;
spec `docs/superpowers/specs/2026-08-06-pagamentos-fluxo-design.md` §4.3/§4.5/§9-F2; plano
`docs/superpowers/plans/2026-08-25-pagamentos-f2-ajustes-versionamento.md`; migrations **0105-0106**).
O pedido de ajuste deixou de ser uma string:

- **`pedido_ajuste` como entidade** — motivo, descrição, responsável por **transação RBAC** (não
  pessoa), tipo MATERIAL/NAO_MATERIAL, prazo, situação ABERTO→RESPONDIDO→RESOLVIDO/CANCELADO.
  Vários pedidos por etapa; o reenvio exige todos respondidos ou cancelados e os resolve. O
  backfill da 0105 criou pedido sintético para todo débito que já estava em `AJUSTE_*` (cobrindo
  o vocabulário da F1, `AJUSTE_SOLICITADO`, e o pré-F1, `DEVOLVIDO`/`SUSPENSO`).
- **Versionamento material** — `CAMPOS_MATERIAIS` com guarda que obriga classificar coluna nova
  de `Debito`; alteração material em `AJUSTE_*` congela snapshot em `debito_versao` e incrementa
  `versao`; no reenvio, materialidade (`versao > versao_debito` do pedido) manda o débito de
  volta ao **gestor** e **invalida as aprovações** (`id_gestor_decisor`/`id_validador` zerados,
  histórico `APROVACOES_INVALIDADAS`); não material volta à etapa que pediu. A 0106 alargou
  `debito_historico.acao` (varchar 30 + CHECK com todas as ações em uso).
- **`anexo_debito`** — documentos do débito reaproveitando o armazenamento de `protocolos.anexo`
  (helper de persistência extraído; autorização pelo vínculo do tenant ANTES de resolver o
  caminho; carregador cru segue proibido em router). Upload/lista/download/remoção no detalhe.
- **Histórico com as três dimensões** — `debito_historico` ganhou `versao_debito` e os pares
  `situacao_*_anterior/nova`, preenchidos por `_registrar_transicao`.
- **UI** — seções Pendências (responder/cancelar, reenvio bloqueado com motivo enquanto houver
  pedido aberto), Versões e Documentos no detalhe; bloco "Pendências para você responder" na
  caixa (`minha-fila.pendencias_ajuste`, filtrado pelas transações do usuário).

Pendências registradas da F2 (menores, nenhuma bloqueante):

- Versão criada via edição não amarra `id_pedido_ajuste` (com N pedidos abertos a amarração é
  ambígua) — decidir vínculo explícito se a tela de responder passar a editar campos.
- Linha `APROVACOES_INVALIDADAS` não preenche os pares de fila/pagamento (deliberado: não é
  transição); sem teste dedicado para "todos os pedidos cancelados → retorno padrão" e para
  pendência de débito excluído (lógica correta por leitura).
- "Usuário #id" na lista de anexos e afins — os schemas Out não trazem nome do usuário (mesma
  dívida da tela de lotes da C2); resolver num ajuste de schema único.
- Bloqueio de reenvio no frontend olha todos os pedidos ABERTOS (não só da etapa) — equivalente
  hoje por invariante do backend; comentar/ajustar se um dia houver ajustes concorrentes de
  etapas diferentes.
- Do review final: snapshot de `debito_versao.dados` grava Decimal como float (exibição ok,
  auditoria ideal preservaria a string); `PUT /debitos/{id}` segue sem `lock_version` (corrida
  edição×reenvio possível — as decisões todas têm lock, a edição não); downgrade da 0106 apaga
  fisicamente as linhas `REENVIADO`/`APROVACOES_INVALIDADAS` (necessário para restaurar o CHECK,
  mesmo padrão das 0086/0087).
**F3 do refactor de fluxo entregue em 2026-08-26** (branch `pagamentos/f3-ordem-cronologica`;
spec §4.3/§4.4/§5/§7.5; plano `docs/superpowers/plans/2026-08-26-pagamentos-f3-ordem-cronologica.md`;
migrations **0107-0111**). A lacuna legal fechou:

- **Fila cronológica** (`posicao_cronologica`): posição ganha na **liquidação** (marco =
  `data_liquidacao` + hora do registro, imutável — reliquidar com data divergente é 409; mudança
  legítima só pela edição material, que regrava com `MARCO_REGRAVADO`), apurada por
  unidade+fonte+categoria+exercício, posição **calculada** por window function (nunca armazenada).
  `contrato.categoria` backfillada para `SERVICOS` e obrigatória em contrato novo; débito sem
  contrato informa a categoria na solicitação (0108).
- **Elegibilidade síncrona** (`avaliar_elegibilidade`, pura + `reavaliar_*`): 5 condições da spec
  §5.2, reavaliadas em autorização, ajuste, fornecedor, bloqueio de saldo e pagamento/estorno —
  sem job. Trilha honesta: a linha `AUTORIZADO` não crava fila; quem grava a fila é a reavaliação.
  Disponibilidade sem dupla contagem (soma de volta a reserva do próprio débito).
- **409 ao preterir** em liberar E pagar, com a lista dos preteridos; **exceção cronológica**
  formal (justificativa+fundamento+autoridade+data+documentos, append-only) é o único caminho de
  furar a ordem — e **não mascara bloqueio real** (a situação sai da avaliação; fornecedor
  irregular continua visível).
- **UI**: tela `/m/pagamentos/fila` (menu "Ordem cronológica", leitura para todos os perfis),
  seção "Fila cronológica" no detalhe com dialog de exceção, categoria na tela de contratos.

Pendências registradas da F3 (menores):

- Guarda de ordem sem teste de concorrência dirigido (pior caso analisado: 409 espúrio,
  conservador); sem teste do desempate por id no 409; `_tem_bloqueio` duplica a vigência de
  `bloqueado_conta` (DRY); `total_grupo` do GET /fila muda de semântica para débito terminal;
  checagem 422 de categoria duplicada (defesa em profundidade).
- `id_usuario_registro` da exceção = a própria autoridade (um 3º registrante não existe no rito).
- F4 (tesouraria: lote/retenções/central) e F5 (remoção do `status` legado) continuam **não
  autorizadas** — o `status` derivado segue vivo e sincronizado até a F5.

### 2.2 Transporte Regulado — P5 a P8

P0–P4 entregues e no ar (permissionário, empresa, veículo, vistorias, alvarás com documentos,
responsáveis, vínculo veicular, auditoria, relatórios). Faltam:

- ~~**P5** — Recadastramento~~ → **P5.1 e P5.2 entregues em 2026-08-04, P5.3 em 2026-08-05, Fase C
  (gate de renovação + job + e-mail no ato) em 2026-08-23** (detalhe abaixo).
- ~~**P6** — Rotas / linhas~~ → **pontos e vagas, entregue em 2026-08-06; linha/itinerário (P6b),
  entregue em 2026-08-21** (detalhe abaixo).
- ~~**P7** — Ocorrências regulatórias~~ → **entregue em 2026-08-23** (detalhe abaixo).
- ~~**P8** — Workflows avançados~~ → **entregue em 2026-08-24** (detalhe abaixo).

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
> **Fase C entregue em 2026-08-23** — as duas pendências acima fecharam. Spec e plano em
> `docs/superpowers/sdd/2026-08-23-transporte-p5-pendencias/`; design em
> `docs/superpowers/specs/2026-08-23-transporte-p5-pendencias-design.md`.
>
> - **O efeito da suspensão sobre alvará é um gate, e só na renovação.** `renovar_alvara` recusa com
>   409 quando o titular (permissionário OU empresa) tem convocação `suspenso` não excluída de
>   qualquer ciclo, e a mensagem manda para a reativação — não para a reabertura. **Emitir alvará
>   novo (`criar_alvara`) continua livre**, de propósito: o gate é só da renovação, e há teste
>   anti-deriva (`test_suspenso_ainda_emite_alvara_novo`) porque "melhorar" isso para também barrar
>   emissão é a deriva mais provável do próximo PR.
> - **A notificação automática por job existe** (`app.tasks.notificar_recadastramento`, migration
>   `0094`), com três janelas MUTUAMENTE EXCLUSIVAS pelo prazo (`atraso` / `lembrete` / `convocacao`)
>   — não uma cadeia de fallback, porque cadeia quebraria a idempotência ao rodar duas vezes no
>   mesmo dia. Dedupe por `(id_convocacao, gatilho)`; convocação suspensa não entra no filtro
>   (`SITUACOES_ABERTAS`); sem e-mail do titular → pula SEM registrar, para ser reavaliada assim que
>   o cadastro for corrigido. A migration `0094` também é os primeiros GRANTs do papel
>   `aprimora_worker` no módulo — só a lacuna que a `0078` não alcançou
>   (`recadastramento_ciclo`/`convocacao`/`notificacao`, `permissionario`, `empresa`), e
>   `id_usuario` de `recadastramento_notificacao` virou NULLABLE (NULL = envio do job, sem operador).
> - **Suspensão e reativação também mandam e-mail, mas no ATO, não pelo job** — saem do ROUTER, após
>   o commit (padrão pós-commit da P7: `try/except` + `db.rollback()` no except; falha de e-mail
>   nunca desfaz o ato), ao TITULAR, **com o parecer no corpo** — diferente do e-mail neutro do job,
>   porque aqui o destinatário é o próprio suspenso e o parecer é o julgamento dele. Registra
>   `RecadastramentoNotificacao(gatilho='suspensao'|'reativacao', id_usuario=<operador>)`. Sem
>   e-mail → só loga, sem registro e sem erro — mesma regra de recuperação do job.

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
> **Ainda aberto do P6:** fila de espera por vaga e geolocalização — fora de escopo por decisão, e
> registrados na spec.

> **P6b (linha/itinerário) entregue em 2026-08-21.** Spec e plano em `docs/superpowers/sdd/`.
> Modelo `LinhaTransporte` com `paradas` e `horarios` filhos; telas em `/m/transporte/linhas` e
> `.../[id]`. Fecha o card "Linhas e Itinerários" que a P6 deixou tracejado.
>
> Três decisões-chave, todas no banco, não só no serviço:
>
> - **Operador ao-menos-um é `CHECK` no banco**, não validação de schema: linha distrital ou
>   escolar exige empresa **ou** permissionário responsável, e a dupla ausência é rejeitada pela
>   própria tabela — duas gravações concorrentes que passassem pela validação do serviço ainda
>   esbarrariam no `CHECK`.
> - **`ordem` das paradas não tem índice único.** Empate de ordem é estado válido (reordenação em
>   lote passa por um estado intermediário com duplicata); o que a leitura garante é o desempate
>   estável por `(ordem, id)`, não a unicidade do valor.
> - **Horário único vive num índice único parcial**, e a prova é por inversão:
>   `test_o_banco_barra_sem_passar_pelo_servico`-símile insere direto contornando o serviço e
>   espera `IntegrityError` — sem o índice, apagar a checagem do serviço manteria a bateria verde.
> - **Suspensão/gate: nenhum.** A linha não bloqueia nada — nem recadastramento, nem alvará, nem
>   checklist de outro domínio. Decisão deliberada, para não repetir a amarra que o ponto (P6) já
>   registrou como "não bloqueia nada".

> **P7 (Ocorrências regulatórias) entregue em 2026-08-23.** Spec e plano em
> `docs/superpowers/sdd/2026-08-21-transporte-p7-ocorrencias/`. Modelo `OcorrenciaTransporte` +
> `OcorrenciaAndamento` (trilha) + `OcorrenciaTipoTransporte` (catálogo por tenant); superfície
> municipal em `/m/transporte/ocorrencias` e `.../tipos`; realm do cidadão em
> `/cidadao/denuncias` e `.../nova`, fechando o card "Ocorrências" que era o último tracejado do
> hub do transporte regulado.
>
> Cinco decisões-chave, todas registradas na spec:
>
> - **Alvo mora em regra de serviço, não em CHECK.** Uma denúncia do cidadão nasce sem alvo formal
>   — ele não sabe quem é o permissionário ou a empresa, só o que viu. `exigir_alvo` só é cobrado
>   na hora de decidir como **procedente**: aí sim tem de apontar para um permissionário ou empresa
>   do próprio tenant, senão **409**. A tela municipal replica essa exigência no cliente para não
>   gastar round-trip, mas o servidor é quem decide.
> - **A trilha é append-only, e a decisão é um ato dela, não um campo da ocorrência.**
>   `OcorrenciaAndamento` acumula registro→apuração→desfecho como linhas, no mesmo desenho de
>   `recadastramento_decisao` (P5.2) e `recadastramento_marca` — histórico que se apaga não é
>   histórico.
> - **Catálogo de tipos é por tenant** (`OcorrenciaTipoTransporte`, `tenant_id` + índice único
>   parcial em `nome`), não vocabulário global fixo: cada prefeitura nomeia suas próprias categorias
>   de fiscalização e denúncia.
> - **O portal do cidadão é outro realm com schema fechado.** `DenunciaCidadaoOut` **não herda** de
>   `OcorrenciaOut` — não expõe trilha, parecer nem alvo formal, só o que o denunciante tem direito
>   de ver. Autenticação é o cookie `aprimora_cidadao_token` de sempre (`api.cidadaoDenuncias.*`),
>   e a mudança de situação dispara notificação por e-mail em linguagem neutra (nunca "sua denúncia
>   contra Fulano foi arquivada" — o cidadão não tem acesso ao alvo que ele mesmo talvez nem tenha
>   apontado).
> - **Ocorrência não é gate de nada** — não bloqueia recadastramento, alvará nem cadastro, o mesmo
>   não-bloqueio que ponto (P6) e linha (P6b) já registraram. Uma ocorrência procedente é fato
>   registrado, não suspensão automática; se algum dia acionar suspensão, é decisão de produto à
>   parte, não efeito colateral de registrar.
>
> No frontend, a Tarefa 8 fechou a costura: o card "Ocorrências" do hub (`lib/transporte-hub.ts`)
> e o item de menu (`lib/menus/transporte.ts`) ganharam `href`/`ready`, e
> `__tests__/transporte-hub.test.tsx` marca o hub do transporte regulado como **100% ligado** — o
> último card tracejado desde P0 saiu da lista. A subpágina `/m/transporte/ocorrencias/tipos`
> ganhou link próprio (botão "Tipos de ocorrência" na listagem), sem o que a guarda de página órfã
> (`__tests__/rotas-modulo.test.ts`) reprovava mesmo com a tela pronta — o mesmo defeito que a P5.3
> registrou para o detalhe do alvará.

> **P8 entregue em 2026-08-24** — workflows avançados (integração BPM). Spec em
> `docs/superpowers/specs/2026-08-23-transporte-p8-workflows-design.md`, plano em
> `docs/superpowers/plans/2026-08-23-transporte-p8-workflows.md`. O motor BPM (Fases 19–21) passa a
> comandar o estado de ocorrência, alvará e convocação de recadastramento.
>
> O que entrou:
>
> - **Motor polimórfico** (`workflow_instance` com `entidade_tipo` e `entidade_id`, migration 0095):
>   os atos existentes viraram **fachadas** (`transporte_workflow.py` + `transporte_regulado.py`)
>   que delegam a transição ao engine e gravam a `situacao` da entidade como cache do estado — o
>   contrato HTTP não mudou.
> - **Definições-semente por tenant** (slugs `transporte-ocorrencia`, `transporte-alvara`,
>   `transporte-recadastramento`): espelham as máquinas de estado anteriores — dia 1 idêntico ao
>   dia 0. Instanciação **lazy** para o estoque: o primeiro ato cria a instância já no estado
>   equivalente à situação atual.
> - **Migrations 0096–0097:** os CHECKs de situação de ocorrência/convocação saem do banco — o
>   guardião passa a ser o DSL da definição (`workflow_definition.dsl`). O alvará ganha a coluna
>   `situacao` (0097, default `vigente`; "vencido" continua derivado de `data_validade`).
> - **Ato novo: revogação de alvará** (POST `/alvaras/{id}/revogar`) com motivo obrigatório,
>   registrado no `workflow_transicao_log`.
> - **Mudança de política aprovada:** reativação de convocação retorna ao estado de **origem**
>   (`convocado` ou `em_analise`), não mais sempre a `convocado`. Teste dos dois caminhos em
>   `test_suspender_e_reativar_respeita_o_estado_anterior`.
> - **Painel `WorkflowTimeline` (só leitura)** nas três telas, sobre o GET novo
>   `/transporte-regulado/workflow/{entidade_tipo}/{entidade_id}` (`entidade_tipo` ∈ ocorrencia |
>   alvara | convocacao).
>
> Pendências registradas para fatia futura:
>
> - A transação `workflow` (edição de DSL) mora no módulo `protocolo` — editar DSL de transporte
>   exige contratar o módulo protocolo; mover para `comum` é decisão futura do Jorge.
> - Notificação de alerta de SLA para tipos de transporte não dispara: a linha de alerta é criada, mas
>   o aviso por e-mail é processo-only; implementar quando algum tenant configurar `sla_dias` no tipo.
>   Hoje o alerta de transporte também NÃO aparece em painel nenhum — a listagem de alertas faz
>   `INNER JOIN` em `processo`, então uma instância `entidade_tipo != 'processo'` cai fora; o que o
>   painel mostra é só o "(excedido)" derivado por comparação de data, não o alerta gravado.
> - `reabrir_recadastramento` grava `situacao` direto sem tocar a instância (`workflow_instance`);
>   self-heal lazy acontece no ato seguinte — candidata a fachada futura, para ser explícita.
> - Cobertura HTTP do GET de workflow "com instância" existe só para ocorrência; o endpoint é
>   type-agnostic e o risco é baixo, mas um caso HTTP para alvará ou convocação fecharia barato.
> - Seleção da instância mais recente (quando existem múltiplas) usa `ORDER BY iniciada_em DESC`
>   sem teste multi-instância.
> - Índice antigo `ix_workflow_instance_processo_ativa` (0008) coexiste com o novo único
>   polimórfico; aposentá-lo é fatia futura (docstring da 0095).
> - `SITUACOES_ABERTAS_OCORRENCIA`/`SITUACOES_ABERTAS` seguem hardcoded no service — entidade num
>   estado custom do tenant (fora da semente) leva 409 em anotar/vincular/marcar/excluir mesmo
>   estando "aberta" no DSL dele. Configurável de verdade exige derivar "aberto" do próprio DSL
>   (ex.: `final: false`), não de uma tupla fixa no Python.
> - Edição de DSL cria versão nova e desativa a antiga (fluxo normal do CRUD de workflow), mas a
>   instância ativa de uma entidade em estoque fica presa à versão velha — um alvará `vigente` pode
>   viver anos sem nunca migrar. Alcançar esse estoque exige `migrar_instance`, que hoje mora no
>   router de workflow (módulo protocolo), não em transporte.
> - Soft-delete de entidade não finaliza a instância de workflow (`excluir_ocorrencia` deixa a
>   instância ativa); com `sla_dias` configurado no estado, o beat de SLA segue alertando uma
>   ocorrência já excluída — falta encerrar (ou pausar) a instância no mesmo ato do soft-delete.

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

### 2.5 Chatbot / assistente conversacional — IA-1 ENTREGUE; busca continua fora

**A fatia IA-1 está em `services/ia/`**: assistente sobre UM processo já aberto, dentro de
`/m/protocolo/processos/[id]`. Spec em
[`docs/superpowers/specs/2026-08-07-ia-1-assistente-do-processo-design.md`](superpowers/specs/2026-08-07-ia-1-assistente-do-processo-design.md).
As seis decisões do `CHATBOT-PLAN.md` foram respondidas para esta fatia — público: servidor interno;
provider: `claude-opus-5`; grounding: **contexto fechado, sem tool-calling**; validação: prompt de
recusa + números calculados em Python; execução: SSE inline; ações: só leitura.

**A decisão que mais importa, e que diverge do plano de maio:** o plano previa tool-calling com
catálogo de ferramentas. Para esta fatia é a escolha errada — com tool-calling o guard de sigilo tem
de valer em *cada* ferramenta, para sempre, inclusive na que alguém acrescentar em seis meses (é a
costura onde o download de anexo ficou aberto sete meses, item 1.0.02). Injetando o processo já
resolvido e já autorizado no prompt, **o modelo não tem o que chamar**: o isolamento vira propriedade
da arquitetura em vez de disciplina recorrente.

**O que continua aberto, e por quê:**

- **A busca (`buscar_processo`, `meus_processos`) ficou fora de propósito, e o item 1.0.8 é o
  motivo.** Hoje o eixo de permissão não é aplicado na leitura, mas isso é *latente*: o menu é
  filtrado por permissão, então quem não tem acesso nunca vê o link e alcançar o dado exige saber a
  URL. **Um chatbot com busca remove exatamente esse atrito** — entrega numa frase o que hoje exige
  conhecer a rota. O bot não cria o buraco; converte um buraco latente num explorável. O item 1.0.8
  registra como gatilho de priorização "a criação do primeiro grupo não-SU"; **o chatbot com busca é
  um segundo gatilho**, e fechar 1.0.8 (junto com 1.0.7) é pré-requisito dele.
- **Sem persistência de conversa.** Nada de `ia_sessao`/`ia_mensagem`/`ia_trace` — seriam repositório
  novo de conteúdo ligado a processo sigiloso, com retenção e direito de eliminação a definir.
  Consequência aceita: não dá para medir custo por tenant ainda.
- **Sem conteúdo de anexo.** Só metadado; ler PDF é outra fatia e outro risco.
- **Sem portal do cidadão.** Outro provider de auth, outra noção de "meus processos", e é justamente
  quem não tem credencial de sigilo. Fatia própria, não um `if`.
- **`ANTHROPIC_API_KEY` não está definida em ambiente nenhum.** Por desenho isso não quebra nada: o
  endpoint devolve 503, a tela não aparece, e a suíte passa sem chave, sem rede e sem o pacote
  instalado (o `import anthropic` é lazy e os testes injetam dublê).

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

### Fechado sai daqui — mas com ressalva aberta, não sai

Item resolvido vai para [BACKLOG-FECHADOS.md](BACKLOG-FECHADOS.md) com o
diagnóstico e a lição intactos. Este arquivo é consultado para saber **o que
falta**; em 2026-08-27 ele tinha 23 KB de coisa já resolvida no meio disso.

A exceção é a que importa: **fechado com ressalva aberta continua aqui.** O
1.0.03 (backup da VPS) é o caso — o backup existe, mas não sai da máquina. Ponta
solta não é conclusão, e mover o item enterraria a ponta junto com ele.

### Toda evidência leva data — a regra saiu de quatro erros seguidos

Em 2026-08-13/14, quatro itens foram remedidos e **os quatro estavam errados**:

| item | o que afirmava | o que era |
|---|---|---|
| 2.1 | "evidência de que não existe nada: `grep` retorna zero" | a Onda C existia desde a C1.1, três semanas antes |
| 1.1.4 | (não existia) | 21 testes vermelhos tratados como ruído por semanas |
| 1.0 | duas linhas em `utils.sistema`, `APP_NAME=aprimora`, teste falhando | uma linha, alinhada, teste passando |
| 1.1.5 | duas falhas pré-existentes | as duas passam |

O padrão não é descuido. **Nenhum dos quatro tinha data na evidência** — a medição foi feita uma
vez e escrita no presente do indicativo, como se fosse propriedade do sistema. Um `grep` que
devolveu zero em 28/07 continua parecendo verdade em 14/08, e "zero ocorrências" é justamente a
afirmação que menos chama atenção ao envelhecer: nada nela dá erro.

Daí três regras:

1. **Contagem, `grep` e "não existe" vão com a data da medição, no corpo do item.** Sem data, a
   afirmação não é evidência — é lembrança.
2. **Reconfirme antes de agir, e escreva o resultado mesmo quando confirma.** O aviso no topo do
   arquivo já pedia isso; o que faltava era registrar a reconfirmação, para a próxima sessão saber
   quando a evidência foi olhada pela última vez.
3. **Item que deixa de ser verdade não avisa.** Os quatro saíram do vermelho de carona em outras
   fatias, sem nenhum PR citando o item. Ninguém volta a um item que não está bloqueando nada — por
   isso a varredura precisa ser periódica, e não sob demanda.
