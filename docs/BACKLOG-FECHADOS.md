# Backlog — itens fechados

> **Status:** registro · **Autoridade sobre:** nada.
> **Última verificação:** 2026-08-27.
> Índice: [docs/INDEX.md](INDEX.md) · aberto: [BACKLOG-PENDENCIAS.md](BACKLOG-PENDENCIAS.md)

Itens de curto prazo já resolvidos, tirados de [BACKLOG-PENDENCIAS.md](BACKLOG-PENDENCIAS.md)
em 2026-08-27. Saíram de lá por custo de leitura: o backlog é consultado para
saber **o que falta**, e 23 KB de coisa resolvida no meio disso é ruído.

Não viraram lixo. O que cada um registra — o diagnóstico, por que o defeito não
tinha sintoma, e a guarda que nasceu dele — é a parte reutilizável. Vários dos
testes `test_guarda_*` existem por causa de um item desta lista.

Item que fechou **com ressalva aberta** não está aqui: continua no backlog
aberto, porque ressalva aberta é item aberto.

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

### ~~1.0.04 O cadastro público de cidadão gravava a senha em MD5~~ — FECHADO em 2026-08-06

`services/cidadao_auth.py::cadastrar` gravava `senha=hash_md5(payload.senha)` ao lado do bcrypt,
"espelhando `Positiv\Hash`" — compatibilidade com o portal PHP. MD5 sem sal de senha escolhida por
pessoa é reversível por rainbow table em tempo de consulta: na prática a senha estava em claro, num
banco compartilhado, para servir um sistema que este projeto decidiu não sustentar.

Três coisas tornam isto pior do que a soma das partes, e valem como padrão a procurar em outro
lugar:

- **Era a última exceção, não a regra.** Provisionamento, criação de usuário, reset e troca já
  gravavam `senha=""` desde o SEC-1. Sobrou exatamente um caminho — e o mais exposto de todos:
  cadastro público, sem convite e sem servidor no meio. Um caminho esquecido numa migração que
  "terminou" não se parece com defeito; parece com o código antigo que ninguém tocou.
- **O piso de senha estava invertido.** O cadastro de cidadão exigia **4** caracteres; a troca de
  senha do servidor municipal exigia **6**. A porta da rua era mais fraca que a de dentro. E o 6
  estava escrito à mão em dois lugares (`schemas/auth.py` e `services/conta.py`), que é como dois
  números que deveriam ser um só acabam divergindo.
- **O rehash só acrescentava.** O login convertia MD5→bcrypt mas **não apagava** o MD5, então toda
  linha convertida seguia guardando o hash reversível ao lado do bcrypt, para sempre. `conta.py` e
  `usuario_senha.py` já zeravam; o login, não.

Entregue: `SENHA_MINIMA = 8` como número único (NIST SP 800-63B §5.1.1.2), aplicado ao cadastro de
cidadão, ao `nova_senha` e ao `conta.py`; cadastro gravando só bcrypt; login **de cidadão e de
admin** apagando o MD5 no ato da conversão; `lib/senha.ts` no frontend com a mesma unificação.
`test_guarda_md5.py` (3 asserções) e `test_senha_sem_md5.py` (5), com as **seis** assertivas
estruturais provadas por inversão.

A guarda foi escrita duas vezes. A primeira, em regex, deu cinco falsos positivos de duas espécies:
leu o próprio docstring como código, e confundiu `provisionar_tenant(senha=<em claro>)` — argumento
para uma função que aplica bcrypt lá dentro — com gravação na coluna. Regex não distingue essas
coisas; `ast` distingue. **Guarda que grita no caso legítimo é desligada por quem tropeça nela**, e
aí não guarda mais nada.

**O que NÃO foi feito, de propósito:** `verify_md5` continua vivo, e nenhuma linha existente foi
convertida em massa. Apagar a verificação hoje trancaria para fora todo usuário cujo banco só tem
MD5 e que ainda não fez login. A rampa é o próprio login, um usuário por vez. O dia em que
`verify_md5` puder morrer é o dia em que `SELECT count(*) FROM utils.usuario WHERE senha <> ''`
(e o mesmo em `usuario_externo`) der zero nos ambientes vivos — é uma medição, não um teste, e por
isso não tem guarda que a antecipe.

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

### ~~1.0.65 Falha da F1 que só aparece em banco limpo~~ — DIAGNOSTICADA E FECHADA

*(Aberto em 2026-07-30. **Fechado em 2026-08-11** — o conserto é de 2026-07-30, no commit `9992e44`;
o que faltava era alguém voltar e fechar o item.)*

**A causa, exata:** `_cria_usuario_comum` em `tests/test_permissoes_modulo.py` fazia `scalar_one()`
sobre `utils.nivel WHERE valor <> 0`. Esse nível existe no banco de dev **por herança do legado**,
mas o `seed_bootstrap` garante somente o valor 0 (Super Usuário) e nenhuma migration o cria — então
em banco limpo (CI, instalação nova) a query não acha linha e estoura `NoResultFound`. Virou
get-or-create.

**Verificação (2026-08-11):** run `31452170050` do `Backend tests` em `main` (`04c54e6`) — os 7
testes de `test_permissoes_modulo.py` passam e o run inteiro tem **zero** `FAILED`.

Duas coisas que ficam:

- **É a mesma raiz do item 1.0.7**, visto do outro lado: o sistema nunca teve um nível não-super, e
  quem escreve teste ou seed assume que ele existe porque nesta máquina existe. Um apareceu como
  teste vermelho no CI; o outro é o buraco de autorização latente.
- **A classe de defeito continua ativa.** Ao escrever a fixture da fatia IA-1 (2026-08-11) tropecei
  no mesmo padrão e só não quebrei porque copiei o get-or-create daquele arquivo. Suposição sobre
  dado que só o ambiente local tem é o modo de falha recorrente deste repositório — o mesmo do
  Critical do review final da F1 (contratação ausente em banco limpo).

<details>
<summary>Registro original, de quando ainda não se sabia a causa</summary>

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

</details>

### ~~1.0.8 O buraco de autorização — leitura aberta a qualquer autenticado do tenant~~ — FECHADO em 2026-08-11

*(Aberto de propósito pela fatia `feat/leitura-por-modulo` (2026-07-30), que fechou o item 1.0.5.
Fechado pela fatia `feat/1-0-8-leitura-com-permissao`; escopo em
`docs/superpowers/specs/2026-08-11-1-0-8-leitura-com-permissao-escopo.md`.)*

- **O que era:** a contratação de módulo responde *"o tenant tem este módulo?"*. Ela nunca respondeu
  *"este usuário pode ler isto?"* — e ninguém mais respondia. Qualquer autenticado do tenant lia
  `/processos`, `/usuarios`, `/grupos`, `/audit`, os relatórios e os PDFs.
- **Medição por introspecção da app real, 2026-08-11 — antes:** 107 GETs com permissão, **72 só com
  `require_modulo`** e **15 só autenticados**. Depois: sobram **18** catálogos de formulário e **11**
  rotas de si-mesmo, todos como decisão registrada em `LEITURA_SEM_PERMISSAO_DECIDIDA`
  (`tests/test_guarda_modularizacao.py`), cada entrada com a razão ao lado.
- **58 GETs** ganharam `require_permission("<codigo>")` **sem `action`** — a forma de leitura —,
  **somando** ao gate de módulo, não o substituindo. O código de cada rota foi **herdado dos irmãos
  de escrita do mesmo router**, não inventado.
- **A fatia entrou INERTE, e isso era o ponto.** Não existe grupo não-super-usuário (medido nos dois
  ambientes pelo item 1.0.7) e o SU passa por cima do gate: ninguém perdeu acesso no dia em que
  entrou. Era a janela mais barata que ia existir — depois do primeiro grupo Operacional, a mesma
  mudança seria 403 em massa para aquele grupo.
- **Transação nova `auditoria`** (migration `0090`, módulo `administracao`): `/audit` não tinha irmão
  de escrita e nenhum dos 24 códigos existentes lhe cabia.
- **O que isto CRIA, e é a contrapartida honesta:** o item 1.0.7 deixa de ser hipotético. Quem criar
  o primeiro grupo Operacional precisa conceder também a leitura — inclusive `unidadeTrabalho` e
  `usuario`, que alimentam o `UnidadePicker` e a exibição de "quem fez o quê" em telas de
  **protocolo**. O conjunto sugerido está no RUNBOOK, seção "Antes de criar um grupo NÃO
  super-usuário", e a CLI `app.cli.diagnostico_permissoes` mostra o que falta.

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

~~**ABERTO, e é outro problema:**~~ **FECHADO em 2026-08-16.** O `deploy.sh` fazia
`git reset --hard origin/main` na VPS, então subia o `main` **do momento do deploy**, não o SHA
testado: commit que entrasse em `main` entre o fim da suíte e o deploy ia junto, sem ter passado
pelo portão. Dito de outro modo, **o portão aprovava um SHA e a VPS recebia outro** — e o deploy
ficava verde nos dois casos.

- O workflow passa `DEPLOY_SHA` (o `head_sha` do run que abriu o portão) e o `pull_code` reseta
  nesse commit. Sem a variável — invocação manual no servidor — o comportamento antigo continua.
- Guarda nas **duas** pontas (`test_guarda_portao_de_deploy.py`): quem passa e quem consome.
  Remover qualquer uma reabre o buraco, e nenhuma das duas remoções teria sintoma.
- **A primeira rodada depois desta mudança ainda ignora o `DEPLOY_SHA`**, e isso não é bug: o
  `pull_code` sobrescreve o próprio `deploy.sh` enquanto o bash já o executa, e o `exec` de
  re-execução só vem depois do pull. O pinning vale da segunda rodada em diante — mesma armadilha
  já registrada no `CLAUDE.md`.
- **Não verificado em execução real**, porque verificar exige um deploy. A prova aqui é estrutural
  (guarda invertida) mais `bash -n` e validação do YAML.

### ~~1.1.4 21 testes de RLS vermelhos só na máquina — deriva de GRANT~~ — FECHADO em 2026-08-14

Convivíamos com ~21 falhas locais em `test_rls_isolation`, `test_rls_papeis_minimos`,
`test_rls_bypass_caracterizacao`, `test_grant_por_coluna_tenant` e `test_pr3b_config_inicial`, todas
verdes no CI. Todas diziam a mesma coisa — `permission denied for table X` sob `aprimora_app` — e
foram tratadas como ruído de ambiente por semanas.

**Medição (2026-08-13), que é o que faltava:**

| | `protocolos` | `utils` | `aprimora_py` |
|---|---|---|---|
| local | 81 de 86 sem DML | 86 de 86 | 17 de 18 |
| VPS | 0 | 0 | 6 de 18 ← as revogadas de propósito |

**Causa:** o `scripts/bootstrap-db.sh` só aplica o GRANT-cobertor quando ele mesmo carrega o dump na
mesma execução. O `else` que o pula está **certo** (SEC-01A: repetir o cobertor desfaria os `REVOKE`
das 0076/0079/0080). Mas isso significa que **banco criado antes de o passo existir nunca recebe o
cobertor, e re-rodar o bootstrap não conserta — por decisão, não por bug.**

**Conserto:** `app.cli.reparar_grants` — o cobertor seguro de repetir, porque reafirma na mesma
transação todas as revogações declaradas pelas migrations. O passo 4b do bootstrap passa a chamá-lo
em banco existente. Depois de aplicar, o local ficou idêntico à VPS e os 21 testes passaram.

Três coisas a levar adiante:

- **A VPS estava correta.** Isto era higiene de dev, não bloqueio do `SEC-RLS-ROLLOUT`. Foi medido
  antes de escrever qualquer código, e valeu a pena: a hipótese inicial era o oposto.
- **Mas a razão de não doer é o F-12.** O runtime conecta como `ged_user` (`BYPASSRLS`), então
  nenhum destes grants é exercitado fora dos testes. Num ambiente com essa deriva, o dia em que
  `APP_DATABASE_URL` for definida não degrada nada: para tudo de uma vez.
- **O custo real foi o vermelho virar paisagem.** 21 falhas permanentes são o esconderijo perfeito
  para a 22ª. `tests/test_guarda_reparar_grants.py` troca isso por uma falha só, que diz o que
  fazer.

### ~~1.1.5 Suíte não estava verde antes do F1~~ — FECHADO em 2026-08-14

As duas falhas nomeadas — `test_jwt_compat.py::test_emitted_token_has_required_claims` e
`test_pr5a_dashboard_servicos.py::test_http_dashboard_com_perm_acessa` — **passam**. Medido em
2026-08-14: `pytest tests/test_jwt_compat.py::... tests/test_pr5a_dashboard_servicos.py` fecha em
**24 passed**, e a suíte inteira em **1304 passed / 0 failed**.

Nenhum dos dois foi consertado por um PR que citasse este item; eles saíram do vermelho de carona
em outras fatias. Por isso o item sobreviveu meses depois de ter deixado de ser verdade — ninguém
volta a um item que não está bloqueando nada.
