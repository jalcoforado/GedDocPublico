# Runbook operacional — Aprimora SaaS

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

Cadastro, revogação e break-glass: **`docs/runbooks/platform-operator-bootstrap.md`**
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

## Backup por tenant

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
