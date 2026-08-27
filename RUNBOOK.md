# Runbook operacional — Aprimora SaaS

> **Status:** vivo · **Autoridade sobre:** Operação: onboarding de tenant, backup, firewall, observabilidade, incidentes.
> **Última verificação:** 2026-08-12 (último commit que tocou este arquivo).
> Índice: [docs/INDEX.md](docs/INDEX.md) · precedência: código > `CLAUDE.md` > este doc.


Procedimentos para operações de produção. Tudo executável como `docker exec aprimora-py-backend ...`.

---

## Painel admin de plataforma

Onboarding e gestão de tenants pela interface, sem mexer no banco.

> **`PLATFORM_ADMIN_EMAILS` foi REMOVIDA em `SEC-01A`.** Ela era o achado
> **F-01**: a autorização cross-tenant era uma comparação de string sobre um
> e-mail, e o e-mail é único apenas **por tenant** — qualquer prefeitura capaz
> de criar um usuário com o e-mail certo virava administradora da plataforma.
> Se a variável ainda existir em algum host, **remova-a**; enquanto existir num
> ambiente é um caminho ativo (T-1 do threat model), mesmo que o código já a
> ignore. A verificação que conta as entradas **sem revelá-las** está em
> `docs/runbooks/platform-operator-bootstrap.md` §1.1.

O acesso hoje exige **duas** coisas, e nenhuma é um e-mail:

1. um **token administrativo RS256** do IdP dedicado (Google Workspace do
   domínio corporativo), com `iss`/`aud` próprios — token municipal não serve;
2. um **principal ativo** em `aprimora_py.platform_principal`, cadastrado pela
   CLI no host.

Configuração por ambiente (nenhuma tem default — ausente ⇒ nega tudo):

```bash
# .env do backend, por ambiente. Nada disso vai para o repositório.
PLATFORM_OIDC_ISSUER=https://accounts.google.com
PLATFORM_OIDC_AUDIENCE=<client id do ambiente>
PLATFORM_OIDC_JWKS_URL=https://www.googleapis.com/oauth2/v3/certs
PLATFORM_OIDC_HOSTED_DOMAIN=<dominio corporativo>
PLATFORM_DB_URL=postgresql+asyncpg://aprimora_platform:<cofre>@<host>/<db>
```

Dois passos que **não** são opcionais e vivem no runbook de operador:
`ALTER ROLE aprimora_platform PASSWORD` (a migration cria o papel com a senha de
dev — §1.2) e o **pré-cadastro do principal de emergência** com
`criar --break-glass`, feito fora de incidente (§5).

**Não ligue `STRICT_TENANT_RESOLUTION=true` sem ler §1.3 do runbook de
operador.** O `TenantMiddleware` roda na frente de `/api/v2/admin/*`; com
resolução estrita, um `Host` que não seja subdomínio de tenant leva 404 antes do
gate — e o console de `SEC-01B`, em origem própria, cai inteiro. Correção é
`SEC-01B`.

Cadastro, revogação, break-glass e inventário
(`platform_principal listar`): **`docs/runbooks/platform-operator-bootstrap.md`**
— é o contrato operacional, e a CLI `python -m app.cli.platform_principal`
cumpre os comandos de lá.

- Painel: `/admin/tenants` (criar/listar/editar/ativar/desativar).
- Criar uma prefeitura gera uma **senha temporária exibida UMA ÚNICA VEZ** na
  resposta; repasse pelo canal acordado (NUNCA email texto-puro) e oriente a
  troca após o 1º acesso. Só o hash bcrypt é persistido.
- API: `POST /api/v2/admin/tenants` (e `GET/PUT/.../ativar/desativar`),
  protegida por `require_platform_admin` (`app/auth/plataforma.py`), sobre a
  conexão dedicada do papel `aprimora_platform`.

**Lacuna conhecida entre `SEC-01A` e `SEC-01B`:** `GET /admin/me` devolve
`is_platform_admin: false` de forma constante — depois de `SEC-01A` é literalmente
verdade que nenhuma sessão municipal é identidade de plataforma. Como o frontend
municipal decide por esse campo, **o link do painel some para todo mundo** e o
console fica inalcançável pela UI até o console próprio de `SEC-01B`. É
fail-closed e esperado; não contornar reativando allowlist.

## Onboarding de um novo tenant (CLI)

A CLI usa o **mesmo serviço** (`services/provisioning_tenant`) do painel:

```bash
docker exec aprimora-py-backend python -m app.cli.tenant create \
  --slug fortaleza \
  --nome "Prefeitura Municipal de Fortaleza" \
  --cnpj 07954605000160 \
  --plano profissional \
  --cor "#0055aa" \
  --admin-email admin@fortaleza.gov.br \
  --admin-cpf 12345678901 \
  --admin-nome "Maria Silva"
```

Saída inclui a senha temporária gerada (exibida uma vez). Em prod, repasse pelo
canal acordado (NUNCA por email texto-puro). Só o hash bcrypt é persistido
(o campo MD5 legado fica vazio).

Pós-criação:
1. Configurar DNS: `fortaleza.aprimora.app` → mesmo IP do produto
2. Compartilhar URL + credenciais com o cliente
3. Acompanhar primeiros logins via `aprimora.access` logs (filtrar `tenant_slug=fortaleza`)

### Antes de criar um grupo NÃO super-usuário

O tenant nasce com um grupo `Administradores` de **nível 0** — super-usuário, que passa por
`utils.sistema_transacao` e ignora `grupo_transacao`. Enquanto todo grupo for nível 0, permissão por
transação não tem efeito prático.

No dia em que criar um grupo operacional (nível ≠ 0), rode antes:

```bash
docker exec aprimora-py-backend python -m app.cli.diagnostico_permissoes --tenant fortaleza
```

Ele lista, por grupo não-SU, quais das 9 transações da migration `0074` (`processo`, `usuario`,
`catalogo`, `assunto`, `manifestante`, `cidade`, `endereco`, `workflow`, `unidadeTrabalho`) não
estão concedidas — são as que a fatia F1 usou para gatear 13 endpoints, entre eles transicionar
workflow e os disparos de job. **Elas não estão concedidas a nenhum grupo**, então um grupo
operacional novo recebe 403 nesses endpoints até alguém conceder.

Duas armadilhas:

- **O nível operacional pode não existir.** O `seed_bootstrap` garante só o valor 0; nenhuma
  migration cria outro. Criar grupo não-SU exige criar o nível antes — a CLI avisa quando só há SU.
- **A CLI não concede nada, de propósito.** Conceder as 9 em bloco daria a um operacional o poder de
  excluir processo, que ele nunca teve. Quem passa a poder o quê é decisão de política de acesso
  (item 1.0.7 do backlog), não de ferramenta.

#### Desde o item 1.0.8 (2026-08-11), a LEITURA também precisa ser concedida

Antes desta data, um grupo operacional sem transação nenhuma ainda **lia** processos, usuários,
auditoria e relatórios: só a escrita era gateada. Hoje 58 GETs exigem a transação correspondente,
sem `action` — ler basta ter a transação, marcada ou não em inserir/atualizar/excluir.

Conjunto mínimo para um operacional de **protocolo** conseguir usar as telas:

| Transação | Por quê, se você for cortar a lista |
|---|---|
| `processo` | processos, PDFs, trilha, volumes, relatórios, busca e os jobs |
| `assunto`, `manifestante` | abertura e consulta de processo |
| `workflow` | tramitação e o editor, se o tenant usar BPM |
| `unidadeTrabalho` | **não é opcional**: alimenta o `UnidadePicker`, e sem ela não se abre processo |
| `usuario` | exibir "quem fez o quê" nas telas de protocolo, não só administrar gente |

`unidadeTrabalho` e `usuario` na lista de um perfil de *protocolo* parecem fora de lugar e não são:
essas duas leituras são consumidas por telas de todos os módulos. Foi exatamente por isso que elas
ficaram sem gate de **módulo** em 2026-07-30 — a razão está registrada em
`tests/test_guarda_modularizacao.py`.

Catálogo de formulário (`/estados`, `/cidades`, `/tipos-*`, `/catalogo/*`, classes CCD, espécies
documentais) **não** exige transação, por decisão registrada: são as listas que preenchem `<select>`
em toda tela, e cobrá-las obrigaria todo grupo a receber `catalogo` só para abrir um formulário.

A leitura da trilha de auditoria pede a transação `auditoria` (migration `0090`), que é do módulo
`administracao`.

### Provisionamento que parou no meio (tenant inerte)

Desde `SEC-RLS-00C` o provisionamento são **dois atos**, em papéis de banco
diferentes: o de **plataforma** cria o tenant e a contratação de módulos
(`aprimora_platform`), o **municipal** cria admin, grupo SU, unidade e catálogos
(papel da aplicação). São duas transações — logo, o ato 1 pode ter sucesso e o 2
falhar.

**Quando isso acontece, nada é apagado.** O tenant fica com `ativo = false`, ou
seja **inerte**: não resolve por subdomínio, ninguém faz login, nada vaza. A
mensagem de erro (na CLI ou no `500` de `POST /admin/tenants`) traz o slug, o id
e o comando de conclusão. Sintoma correlato: `python -m app.cli.tenant list`
mostra o tenant com `Ativo = NÃO` logo depois de um `create` que deu erro.

Concluir — o ato municipal é idempotente, então repetir é seguro:

```bash
docker exec aprimora-py-backend python -m app.cli.tenant retomar \
  --slug fortaleza \
  --admin-email admin@fortaleza.gov.br \
  --admin-cpf 12345678901 \
  --admin-nome "Maria Silva"
```

Se o admin já existir, a senha dele é **preservada** (a saída avisa) — para
trocá-la use o reset de senha do próprio tenant.

**O comando recusa tenant que já foi provisionado**, e a regra é "tem algum
usuário", não "está inativo". Município **suspenso** de propósito
(inadimplência, incidente, retenção legal) também aparece inativo, e retomar um
deles criaria nele um super-usuário novo e desfaria a suspensão. Para reativar
município suspenso o comando é outro, e ele não toca em usuário nenhum:

```bash
docker exec aprimora-py-backend python -m app.cli.tenant activate fortaleza
```

Isso vale inclusive quando o provisionamento tiver falhado **só na ativação**
(ato 3): nesse caso o admin já existe, não há o que semear, e `activate` é
exatamente o que falta.

**Se a decisão for abandonar o tenant inerte em vez de concluí-lo**, saiba que
ele não desaparece sozinho: o ato de plataforma já contratou os módulos, então
sobram linhas em `aprimora_py.tenant_modulo` e o tenant continua aparecendo em
`GET /api/v2/admin/tenants` e em `tenant list`, sempre com `Ativo = NÃO`. Não há
limpeza automática — **nenhum papel de runtime tem `DELETE` em
`aprimora_py.tenant`**, por decisão registrada na migration 0076 (apagar tenant
não é operação de runtime). A remoção é manual, no banco, por quem tem a
credencial administrativa, e o `DELETE` do tenant leva `tenant_modulo` junto
pelo `ON DELETE CASCADE` da 0075. Deixá-lo inerte é seguro; o custo é ruído na
listagem.

Listar tenants existentes:

```bash
docker exec aprimora-py-backend python -m app.cli.tenant list
```

Desativar (impede login, preserva dados):

```bash
docker exec aprimora-py-backend python -m app.cli.tenant deactivate fortaleza
docker exec aprimora-py-backend python -m app.cli.tenant activate fortaleza
```

### Transações sem concessão pós-modularização F1 (migration 0074)

A migration 0074 criou 9 códigos em `utils.transacao` que os routers passaram
a exigir via `require_permission` (Task 8 da fatia F1 de modularização):
`processo`, `usuario`, `catalogo`, `assunto`, `manifestante`, `cidade`,
`endereco`, `workflow`, `unidadeTrabalho`.

**Por que estão sem concessão:** a migration só cria a linha em
`utils.transacao`; ela não concede a transação a nenhum `utils.grupo` (nem
grava `utils.grupo_transacao`) — id de grupo é ambiente-dependente, mesmo
motivo já registrado para `configuracao` na seção anterior. `seed_bootstrap`
liga essas transações a `utils.sistema_transacao` (o ramo de super-usuário
do `load_permissions` consulta essa tabela), mas isso não é o mesmo que uma
concessão de grupo.

**Quem é afetado:** super-usuário (`nivel.valor == 0`) opera por bypass e não
percebe nada. **Usuário não-SU leva 403 permanente** nos 13 endpoints que a
Task 8 moveu de `get_current_user` para `require_permission` sobre
`processo`/`workflow` — inclui `transicionar` em `routers/workflow.py`
(usado por `ProcessoWorkflowPanel.tsx` no frontend) e os 4 disparos de job
em `routers/jobs.py`. Sem concessão, processo/workflow ficam inutilizáveis
para qualquer grupo administrativo que não seja o SU.

**O que fazer após o deploy que subir esta migration:** para cada grupo
administrativo não-SU que precisa operar protocolo/workflow/administração,
conceder as 9 transações acima pela tela **Grupos → Transações** (mesma tela
usada para `configuracao`). Não há automação disso hoje — é passo manual,
por tenant, repetido a cada grupo que precisar.

## Configuração inicial do tenant (PR3b)

O admin **municipal** edita os dados institucionais (nome, sigla, contato,
endereço, horário, logo/cor, mensagem do portal, unidade padrão) e o NUP federal
pela tela **Configurações** (`/configuracoes`), sem mexer no banco.

**Permissão `configuracao:atualizar` é necessária para editar as configurações
institucionais** (gate de `PUT /tenants/me` e do `PUT /tenants/me/nup-config`):

- **Super-usuário (`nivel.valor == 0`) já opera por bypass** — não precisa de
  concessão explícita.
- **Grupos administrativos não-SU precisam receber essa transação** pela tela de
  **Grupos → Transações** (a transação `configuracao` é semeada pela migration
  0023). Sem isso, o usuário não-SU vê a tela em modo leitura e recebe `403` ao
  salvar.

> A transação NÃO é mapeada automaticamente a `sistema_transacao`/`grupo_transacao`
> na migration (id de sistema é ambiente-dependente). É uma concessão operacional
> via UI, por design.

**Reset de senha temporária** (`/usuarios` → "Resetar senha"): gera uma senha
exibida **uma única vez**, persiste só o hash moderno (bcrypt) e zera o MD5
legado — a senha antiga deixa de valer. **Marca `must_change_password=true`
no afetado** (SEC-1 Commit 3) — o usuário será forçado a trocar no próximo
acesso, ver seção *Fluxo obrigatório de troca de senha* abaixo. Não envia
e-mail. Exige `usuario:atualizar` e é restrito ao próprio tenant (sem
cross-tenant); o reset é auditado em `audit_log`.

---

## Fluxo obrigatório de troca de senha (SEC-1)

PR SEC-1 introduziu uma flag `utils.usuario.must_change_password` que força o
servidor/admin a trocar a senha temporária no primeiro acesso, antes de
acessar qualquer rota de negócio. **Não se aplica ao portal do cidadão**
(D-CIDADAO — `usuario_externo` não tem a flag).

### O que é `must_change_password`

Coluna boolean em `utils.usuario`, default `false`. Sinaliza que a senha em
vigor é **temporária** e foi gerada por algum dos fluxos administrativos
(provisionamento, reset, criação) — o usuário precisa concluir a troca antes
de continuar.

### Quando a flag é marcada (`true`)

- **Provisionamento de tenant** (CLI `python -m app.cli.tenant create` ou
  API `POST /admin/tenants`): admin/SU inicial nasce com a flag.
- **Reset administrativo de senha** (`POST /api/v2/usuarios/{id}/resetar-senha`
  via UI `/usuarios` → "Resetar senha"): marca a flag e zera o MD5 legado.
- **Criação de usuário** (`POST /api/v2/usuarios` via UI `/usuarios` → "Novo
  usuário"): nasce com a flag, MD5 legado vazio.
- **Alteração administrativa de senha pelo cadastro do usuário**
  (`PUT /api/v2/usuarios/{id}` com `senha` preenchida — campo "Nova senha
  temporária" no dialog de edição): segue a mesma regra do reset. Zera o MD5
  legado, grava só bcrypt, marca a flag e registra audit
  `usuario.senha_alterada_por_admin`. Vale **também** quando o admin altera
  a própria senha por essa rota — o auto-serviço seguro continua sendo
  `POST /auth/alterar-senha` (que exige a senha atual). Para suporte ao
  usuário, prefira **resetar senha** (rota dedicada, senha aleatória, audit
  específico).

Em todos os casos, a senha temporária é exibida **uma única vez**;
persistimos só o hash bcrypt. **Nunca envie a senha temporária por canal
inseguro** (e-mail texto-puro, chat sem criptografia ponta-a-ponta, etc.) —
use o canal acordado com o cliente.

### Quando a flag é removida (`false`)

- **Troca self-service de senha** (`POST /api/v2/auth/alterar-senha` via tela
  `/perfil` ou `/alterar-senha-obrigatoria`): zera a flag, grava bcrypt,
  limpa MD5 legado. Audit `usuario.senha_alterada` registra
  `must_change_password_cleared: true`.

Não há outra forma de zerar a flag — não há "ignorar" nem "lembrar depois".
Por design.

### Comportamento no login

- Login (`POST /api/v2/auth/login`) **funciona normalmente** mesmo com flag
  ativa — retorna `HTTP 200`, emite JWT e cookie HttpOnly. O endpoint não
  passa pelo guard `get_current_user`.
- O `LoginResponse` inclui `must_change_password: boolean` (SEC-1 Commit 4).
- O frontend (`/login`) usa esse campo para decidir o destino: se `true`,
  envia direto para `/alterar-senha-obrigatoria`; senão `/home`.

### Comportamento em rotas protegidas

- `get_current_user` em `backend/app/auth/deps.py` aplica o gate: se
  `user.must_change_password`, responde **403 + header
  `X-Must-Change-Password: true`**.
- Toda rota de negócio herda o gate automaticamente (via `require_permission`,
  `require_platform_admin`, `require_acesso_processo`, ou `Depends(get_current_user)`
  direto).
- Whitelist autenticada (rotas que **não** são bloqueadas pelo gate):
  - `GET  /api/v2/auth/me`
  - `POST /api/v2/auth/alterar-senha`
  - `GET  /api/v2/permissoes/me`
  - `GET  /api/v2/admin/me`

  Usam a dep `get_current_user_no_password_gate`. Essenciais para o usuário
  flagged conseguir concluir o fluxo.

### Tela `/alterar-senha-obrigatoria`

- Standalone — **não** usa o layout `(app)` com `Sidebar`/`Header`.
- Mensagem: *"Por segurança, altere sua senha temporária antes de continuar."*
- Mount valida `me()`:
  - 401/erro → `/login`.
  - `must_change_password=false` → `/home` (não precisa estar aqui).
  - `true` → render form de troca.
- Após troca bem-sucedida (`onSuccess` do `TrocarSenhaCard`) → `/home`.
- **Botão "Sair"**: chama `POST /auth/logout` e envia para `/login`. Útil
  quando o usuário não tem a senha atual em mãos.

A senha temporária **nunca** é exibida nem persistida (`localStorage` /
`sessionStorage`). O form mantém os campos só em memória React durante a
sessão da tela.

### Portal cidadão fora do fluxo

O cidadão (`UsuarioExterno`) **não** tem a flag e não passa por esse fluxo.
O frontend usa `requestCidadao()` separado do `request()` admin — o
interceptor 403 que detecta `X-Must-Change-Password` opera apenas no path
admin. Cookies separados (`aprimora_token` vs. `aprimora_cidadao_token`)
garantem que o mesmo navegador pode estar logado nos dois sem conflito.

### Header `X-Must-Change-Password=true`

- Emitido pelo backend em qualquer 403 originado no gate de
  `get_current_user`.
- O frontend (`lib/api.ts`) intercepta no wrapper `request()` e, se presente,
  faz `window.location.assign("/alterar-senha-obrigatoria")` (hard nav).
- Whitelist do interceptor (não redireciona se o pathname atual for):
  - `/login`
  - `/alterar-senha-obrigatoria`
  - qualquer rota começando com `/cidadao/`

### Troubleshooting

- **Usuário preso em loop redirecionando para `/alterar-senha-obrigatoria`**:
  verificar que o backend ainda retorna 200 + `must_change_password=true` em
  `/auth/me`. Se sim, a tela deveria carregar. Causas comuns:
  - JS bloqueado / extensões interferindo no `window.location.assign`.
  - Versão de frontend desatualizada (cache antigo do `lib/api.ts`). Forçar
    refresh hard (Ctrl+Shift+R).
  - nginx sem a rota `/alterar-senha-obrigatoria` no regex (502 Bad Gateway).
    Verificar `nginx/default.conf` — o nome deve estar no `location ~ ^/(...)`
    do bloco Python.
- **403 sem header**: o gate não emitiu. Investigar se a rota usa o
  `get_current_user` correto (não a variante sem gate). Não é o caso para
  nenhuma rota fora da whitelist documentada acima.
- **Tela `/alterar-senha-obrigatoria` não carrega**: verificar console do
  browser. Erro típico de 502 = nginx sem a rota (acima). Erro de 401
  significa que a sessão expirou — usuário será redirecionado para `/login`.
- **Reset de senha não força troca**: confirmar que a migration `0030` foi
  aplicada (`alembic current` no backend). Sem a coluna, o serviço
  `resetar_senha_usuario` não pode marcar e o gate nunca dispara.

### Observação de segurança

- **NÃO** envie senha temporária por e-mail texto puro, SMS sem criptografia,
  ou chat público.
- Use o canal acordado institucionalmente (entrega presencial, sistema de
  mensagens criptografado, gerenciador de senhas compartilhado).
- O reset administrativo audita o ator + afetado no `audit_log` (não grava a
  senha em claro nem o hash) — útil para investigar incidentes.
- O admin de plataforma recém-provisionado também nasce flagged. Comunique
  a senha temporária pelo canal seguro e oriente troca imediata no primeiro
  acesso.

---

## Backup da máquina (VPS)

**São duas coisas diferentes e nenhuma substitui a outra.** Esta seção é o
backup operacional — o que existe para o servidor voltar. A seção seguinte,
"Backup por tenant", é uma ferramenta de migração/clonagem de tenant, e **não**
serve como backup: ver o aviso lá.

### Como era até 2026-08-05

Um dump. Manual. De 24 de julho. 43 KB, em `/root/backups`, na mesma máquina do
banco. Sem cron, sem timer, sem cópia externa. Doze dias de dado operacional a
um `DROP` de distância, e nada que sobrevivesse à perda do disco.

Havia um `backup_database` no `scripts/deploy.sh`, desligado por padrão
(`BACKUP_DB=1`) e escrito de um jeito que **fabricava um arquivo de zero byte
quando o `pg_dump` falhava**, engolia o erro e ainda imprimia `✓ Backup saved`.
O detalhe está no docstring de `backend/tests/test_guarda_backup.py`.

### O que existe agora

```bash
scripts/backup-aprimora.sh     # banco + papéis globais + uploads
scripts/backup-verificar.sh    # restaura de verdade num banco descartável
```

O backup grava em `/root/backups/diario/aprimora_<timestampZ>/`, com quatro
arquivos: `banco.dump` (`pg_dump -Fc`), `globais.sql` (`pg_dumpall
--globals-only`), `uploads.tgz` e `SHA256SUMS`. Aos domingos, uma cópia vai
para `semanal/`. Retenção: 14 diários, 8 semanais.

Três propriedades que **não** são detalhe de implementação:

- **Verifica antes de publicar.** Tudo é gerado numa área de espera e só é
  movido para o destino depois de passar em `pg_restore -l`, piso de tamanho e
  checagem dos quatro papéis da família SEC. Um diretório em `diario/` é, por
  construção, um backup que passou. Não existe estado intermediário com nome
  de pronto.
- **Os papéis vêm junto.** Sem `--globals-only`, restore num cluster novo morre
  no primeiro `GRANT ... TO aprimora_app`.
- **Os uploads vêm junto.** Anexo não vive no banco — o caminho é registro, o
  arquivo é disco. Backup só do Postgres restaura processos apontando para
  arquivos que não existem mais.

### Prova de restore

```bash
scripts/backup-verificar.sh                     # o mais recente
scripts/backup-verificar.sh /root/backups/diario/aprimora_<ts>
```

Cria um banco descartável no mesmo cluster, restaura com `--exit-on-error`,
compara a contagem de **todas** as tabelas de `utils`, `protocolos`,
`aprimora_py` e `frota` contra o banco vivo, e derruba o banco de trabalho no
`trap`. Não toca `ged_saas_db` em momento nenhum.

Reprova em três situações, todas exercitadas em 2026-08-05: dump corrompido
depois de gravado (SHA256SUMS), dump que não restaura (`--exit-on-error`) e
dump íntegro de um banco vazio (contagens). Esta última é a que importa — é a
falha que passa por qualquer verificação sintática.

**Backup nunca restaurado não é backup.** Enquanto ninguém rodar isto, "temos
backup" é hipótese, não fato.

### Agendamento

Unidades versionadas em `deploy/systemd/`. Instalação na VPS:

```bash
cp deploy/systemd/aprimora-backup*.{service,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now aprimora-backup.timer aprimora-backup-verificar.timer
systemctl list-timers 'aprimora-*'
```

Backup diário às 03:20 UTC; prova de restore às segundas, 04:10 UTC. `Persistent=true`
nos dois: máquina desligada na hora roda no próximo boot, em vez de pular o dia
em silêncio. Nenhum `ExecStart=-` — falha tem de aparecer em
`systemctl --failed`.

Conferir depois de um incidente:

```bash
systemctl status aprimora-backup.service
journalctl -u aprimora-backup.service --since '7 days ago'
ls -la /root/backups/diario
```

### O que ainda NÃO está resolvido

**Não há cópia fora da máquina.** Backup no mesmo disco protege contra `DROP
TABLE`, migration ruim e apagão de dado — não contra perda do servidor,
ransomware ou o provedor sumir. Enquanto o destino remoto não for definido
(bucket, segunda VPS, storage do provedor), esta é a limitação a ter em mente
ao dizer "temos backup".

---

## Firewall da VPS — a segunda camada das portas

A camada 1 é o `docker-compose.yml`, que publica tudo em `127.0.0.1:` menos a
8090 (`tests/test_guarda_portas_publicadas.py`). A camada 2 são regras de
`DOCKER-USER` aplicadas no boot. Ela existe porque a camada 1 é um arquivo
editável — e porque `docker-compose.override.yml` é gitignored, usa `!override`
e pode republicar em `0.0.0.0` sem passar por guarda nenhuma.

Fonte versionada desde 2026-08-05: `deploy/vps/aprimora-fecha-portas.sh` e
`deploy/systemd/aprimora-fecha-portas.service`. Até então existiam **só na
VPS** — reinstalar o servidor teria perdido a camada em silêncio.

```bash
install -m 755 deploy/vps/aprimora-fecha-portas.sh /usr/local/sbin/
cp deploy/systemd/aprimora-fecha-portas.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now aprimora-fecha-portas
```

O caminho é `/usr/local/sbin` e **não** o repositório, ao contrário das
unidades de backup: firewall de máquina não deve depender de o clone estar
presente nem num commit específico. O preço é a possibilidade de deriva entre a
cópia instalada e a versionada — reinstale ao mexer no script.

Três coisas que essa camada ensinou, e que valem para qualquer bloqueio futuro:

- **`ufw` não alcança porta publicada por container.** O Docker insere DNAT em
  `PREROUTING`, que desvia do `INPUT` inteiro.
- **O DNAT reescreve a porta antes da `DOCKER-USER`.** A regra tem de casar a
  porta de **dentro** do container. É por isso que a lista tem `3000` e não só
  `3100`: o mapeamento é `3100:3000`. Foi por não saber disso que a 3100
  continuou aberta depois da primeira tentativa.
- **`After=docker.service` é obrigatório.** O daemon recria a chain ao subir e
  leva as regras junto; sem isso a unidade fica verde e as portas abertas.

O script descobre a interface pela rota default e **falha** se ela não existir.
Isso não é zelo: regra inserida com `-i <interface inexistente>` é aceita sem
reclamação e nunca casa pacote nenhum — `systemctl status` verde, `iptables -L`
mostrando as regras, e as portas abertas. Verificado por inversão em
2026-08-05.

Conferir:

```bash
systemctl status aprimora-fecha-portas
iptables -L DOCKER-USER -n -v
ip6tables -L DOCKER-USER -n -v          # o IPv6 tem chain própria
```

E de fora da máquina, que é a única prova que conta:

```bash
for p in 5432 8000 3100 6379; do
  timeout 5 bash -c "exec 3<>/dev/tcp/<ip>/$p" 2>/dev/null && echo "$p ABERTA" || echo "$p fechada"
done
```

---

## Backup por tenant

> **Isto não é o backup do sistema.** É uma ferramenta de exportação de um
> tenant — feita para migrar ou clonar, não para restaurar o servidor. A lista
> `TENANTED_TABLES` (`app/cli/backup.py`) tem **26 tabelas**, congeladas na
> Fase 34; o banco tem hoje **55 tabelas com `tenant_id`**. Ficam de fora, entre
> outras, as de transporte regulado, pagamentos, minuta, notificação, workflow e
> `audit_log`. Para backup de verdade, use a seção acima.

### Inspecionar o tamanho

```bash
docker exec aprimora-py-backend python -m app.cli.backup stats --tenant sobral
```

Mostra linhas por tabela + total. Útil pra validar que dados foram backfilled
após migração ou pra prever tamanho do export.

### Exportar dados

```bash
docker exec aprimora-py-backend python -m app.cli.backup export --tenant sobral
```

Gera `/app/uploads/tenants/sobral/backups/backup_sobral_<timestamp>Z.sql`
com:

- `BEGIN` + `SET session_replication_role = 'replica'` (pula FKs durante restore)
- `DELETE FROM <tabela> WHERE tenant_id = X` (ordem inversa — idempotente)
- `INSERT INTO <tabela> ... VALUES (...)` (ordem topológica — pais primeiro)
- `SELECT setval(<sequence>, MAX(id))` (alinha sequences pra novos inserts não colidirem)
- `SET session_replication_role = 'origin'` + `COMMIT`

**Tabelas dump-adas** (27 ao total): a linha do tenant em `aprimora_py.tenant`
mais as 26 tabelas tenanted (16 em `protocolos.*`, 9 em `utils.*`, `aprimora_py.job`).

**NÃO** inclui catálogos globais (`utils.estado/cidade/bairro/nivel/sistema/transacao`,
`protocolos.acao/prioridade/tipo_assinatura`, `public.modulos`). Esses são fixos
(IBGE/sistema) — destino precisa tê-los populados de outro jeito (seed do dump base).

**NÃO** inclui arquivos físicos do storage (`/app/uploads/tenants/<slug>/anexos/`).
Para um backup COMPLETO incluir:

```bash
docker exec aprimora-py-backend tar czf /app/uploads/tenants/sobral/backups/files_sobral_$(date -u +%Y%m%dT%H%M%S).tgz -C /app/uploads/tenants/sobral anexos carimbados
```

### DR drill — validar export sem restaurar

```bash
docker exec aprimora-py-backend python -m app.cli.backup dr-drill --tenant sobral
```

Faz export + parse-check do SQL gerado. Não restaura em nenhum DB. Roda como
smoke periódico (incluir no Celery Beat quando virar produção).

### Restore num banco destino

```bash
# 1. Copia o arquivo para a máquina destino
docker cp aprimora-py-backend:/app/uploads/tenants/sobral/backups/backup_sobral_<ts>.sql ./

# 2. Garante que o destino tem o schema base (Alembic head)
docker exec <destino> alembic upgrade head

# 3. Garante que catálogos globais estão populados (estado, cidade, etc)
#    — em um banco virgem, rodar os seeds equivalentes ao restore-dev-data.sql

# 4. Aplica o backup
docker cp backup_sobral_<ts>.sql <db-destino>:/tmp/
docker exec <db-destino> psql -U ged_user -d ged_saas_db -f /tmp/backup_sobral_<ts>.sql
```

O `DELETE ... WHERE tenant_id = X` no início torna o restore **idempotente**:
rodar duas vezes não duplica linhas. Se quiser restaurar como NOVO tenant_id
(útil pra clonar Sobral pra um novo cliente), editar o arquivo SQL antes —
substituir `tenant_id = 1` por `tenant_id = N`.

---

## Ligar o assistente de IA (IA-1) num ambiente

O assistente responde perguntas sobre o processo aberto. **Sem chave de provedor
ele não existe para o usuário**: o endpoint devolve 503 e o painel não é
renderizado — é o comportamento projetado, não uma falha a investigar.

A chave vai em **`backend/.env`**, que o container enxerga como `/app/.env` pelo
bind-mount `./backend:/app`. O arquivo é gitignored e **não existe no
repositório** — crie à mão, uma vez por ambiente:

```bash
# na VPS, em /root/GedDocPublico
printf 'DEEPSEEK_API_KEY=sk-...
' > backend/.env
chmod 600 backend/.env
docker compose restart backend worker
```

O `restart` não é opcional: `get_settings()` é `lru_cache`, então o processo em
execução não relê o arquivo.

**Não acrescente a chave ao `docker-compose.yml`.** É o instinto certo para
qualquer outro segredo deste projeto e o errado para este: variável definida e
vazia vence o arquivo `.env` na precedência do pydantic-settings, então
`DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:-}` entregaria `""` em todo ambiente que
não a definisse na raiz e **desligaria o assistente onde ele funciona**, sem
erro e sem log. `tests/test_guarda_chave_ia.py` reprova quem tentar.

Conferir se pegou, sem abrir a tela:

```bash
docker exec aprimora-py-backend python -c   "from app.services.ia.llm_client import obter_cliente; c=obter_cliente(); print(type(c).__name__, c._modelo)"
```

Provedores, em ordem de precedência (`services/ia/llm_client.py::obter_cliente`):
`DEEPSEEK_API_KEY` → `deepseek-chat`; `ANTHROPIC_API_KEY` → `claude-opus-5`.

Duas coisas que a operação precisa saber, e que não são técnicas:

- **O conteúdo do processo trafega para o provedor**, inclusive de processo
  `reservado` ou `secreto` que o usuário tenha credencial para ver. Não há
  recusa por nível de sigilo hoje.
- **Nada da conversa é gravado** — nem pergunta, nem resposta. Sair da tela
  apaga. Decisão de LGPD registrada na spec da IA-1.

## Observabilidade

### Logs estruturados

Cada request gera 1 linha JSON em stdout:

```json
{"ts":"2026-05-23T23:33:03","level":"INFO","logger":"aprimora.access",
 "msg":"http_request","request_id":"ab591d5af3a1456a","tenant_id":1,
 "tenant_slug":"sobral","usuario_id":2,"method":"GET","path":"/api/v2/processos",
 "status":200,"duration_ms":61,"client":"127.0.0.1"}
```

Em produção, agregar com Loki/ELK/Cloudwatch via stdout. Para filtrar por tenant:

```bash
docker logs aprimora-py-backend 2>&1 | grep '"tenant_slug":"sobral"'
```

### Sentry (opcional)

Setar `SENTRY_DSN` no env do backend + instalar `sentry-sdk` no Dockerfile.
Cada evento de erro vem automaticamente com tags `tenant_id`, `tenant_slug`,
`request_id`, `user.id` populados pelo `RequestLoggingMiddleware`.

### Healthcheck

```bash
curl -H "Host: sobral.aprimora.local" http://localhost:8090/api/v2/health
# {"status":"ok","version":"0.1.0","db":"ok","db_latency_ms":1,"tenant":"sobral"}
```

Usar no liveness/readiness do orquestrador. `db_latency_ms > 100` é sinal pra
investigar.

---

## Incidentes comuns

### "Tenant não encontrado" no login

Causa: subdomain do Host não bate com nenhum `aprimora_py.tenant.slug` ativo.

Diagnóstico:

```bash
docker exec aprimora-py-backend python -m app.cli.tenant list
docker logs aprimora-py-backend 2>&1 | grep 'http_request.*404' | tail
```

### Cross-tenant 403

Cliente recebe `403 Token de outro tenant`. Causa: JWT do tenant A com Host do
tenant B (provavelmente cache CDN errado, ou usuário trocou subdomain sem
re-login). Mandar usuário fazer logout + login no subdomain correto.

### Worker Celery não processa

```bash
docker logs aprimora-py-worker --tail 50
```

Caveat conhecido (resolvido na Fase 7.1): nunca importar `SessionLocal`
global em tasks. Usar `task_session_scope(tenant_id=...)`.

---

## Dívida técnica (PR3a e correlatos)

Itens conscientemente adiados — revisitar em PRs futuros:

- **Campo `senha` (MD5 legado) em `utils.usuario`:** hoje NOT NULL. O
  provisionamento grava `""` (só bcrypt é credencial). Remover/torná-lo nullable
  quando o fluxo legado MD5 puder ser aposentado.
- **`must_change_password` no 1º acesso:** não implementado (exige flag +
  enforcement no login + UX). A senha temporária é exibida 1x; troca é manual.
- **Domínio neutro da plataforma:** hoje o admin de plataforma autentica no
  subdomínio do seu tenant de origem; avaliar um domínio/admin dedicado para
  operar a plataforma de forma independente de um tenant.
- **Status do tenant:** hoje booleano `ativo`. Evoluir para enum
  (implantação/trial/suspenso/inadimplente/cancelado) só quando houver
  billing/operação que justifique.
- **Enforcement de limites:** `limite_usuarios`/`limite_armazenamento_mb` são
  apenas armazenados; o bloqueio efetivo (quota) fica para PR futuro.
- **Módulos por tenant:** derivados do `plano` (sem tabela `tenant_modulo`);
  customização fina por módulo é PR posterior.

---

## Convenção de dados de teste (E2E / smoke)

Para evitar leftovers poluindo testes de integração:

- **E-mails de teste** devem usar domínio reservado `.test` (RFC 6761) —
  preferencialmente `@e2e.test` (Playwright) ou `@ux1smoke.test` (smoke UX).
  Nunca usar domínios reais (`*.gov.br`, `*.com`, etc.) em dados de teste.
- **Slugs/prefixos** devem ser fáceis de identificar: `e2e-`, `sec1-`,
  `ux1-smoke-`, `dbg-` (debug manual). Sufixo aleatório (`uuid4().hex[:8]`)
  evita colisão.
- **Cleanup obrigatório** no `test.afterAll` (Playwright) ou fixture
  teardown (pytest) quando o teste criar usuários, processos ou serviços.
- **Smoke manual** (terminal interativo, debug) deve fazer cleanup
  explícito ao fim — se abortar, anotar o ID/email para purgar depois.
- **Testes de integração** **não devem assumir** que o banco está vazio ou
  livre de usuários flagged. Evitar contagens globais sensíveis a
  leftovers; quando precisar verificar comportamento de migration ou de
  fluxo administrativo, usar **usuário-âncora** (ex.: `admin@local.test`
  no tenant default) ou **tenant isolado** criado e destruído na fixture.
- **Limpeza pontual em DEV** (uma vez, quando leftovers vivos forem
  detectados):
  ```sql
  -- Subselect dos ids alvos
  WITH alvos AS (
    SELECT id FROM utils.usuario WHERE email ~ '@(e2e|ux1smoke)\.test$'
  )
  DELETE FROM aprimora_py.audit_log WHERE id_usuario IN (SELECT id FROM alvos);
  DELETE FROM utils.usuario_unidade_trabalho WHERE id_usuario IN (SELECT id FROM utils.usuario WHERE email ~ '@(e2e|ux1smoke)\.test$');
  DELETE FROM utils.usuario_grupo            WHERE id_usuario IN (SELECT id FROM utils.usuario WHERE email ~ '@(e2e|ux1smoke)\.test$');
  UPDATE utils.pessoa SET id_usuario_auditoria = NULL
    WHERE id_usuario_auditoria IN (SELECT id FROM utils.usuario WHERE email ~ '@(e2e|ux1smoke)\.test$');
  DELETE FROM utils.usuario WHERE email ~ '@(e2e|ux1smoke)\.test$';
  ```
  Ordem importa: `aprimora_py.audit_log` tem FK em `utils.usuario(id)`; sem
  apagar lá primeiro, o DELETE final falha com `ForeignKeyViolationError`.
  **Nunca rodar em produção** — domínios `.test` são reservados RFC 6761,
  nenhum usuário real os usa.
