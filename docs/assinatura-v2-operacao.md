# Assinatura v2 — Operação e Testes

Guia operacional dos testes e fluxos da Assinatura v2 (PR2a/2b/2c).

## Testes backend (pytest)
Rodam no container do backend (deps já no ambiente):
```bash
docker compose run --rm backend sh -c "pip install -e '.[dev]' && pytest tests/ -q"
```
Cobrem (entre outros): hash + evidências + auditoria da assinatura, bloqueio
MD5, throttle, guard de sigilo (`validar`/`evidencias`), comprovante PDF,
regressão de `require_acesso_processo`, e troca de senha (`alterar_senha`).

## Testes frontend (Vitest + RTL)
O frontend usa volume anônimo para `node_modules`; instale e rode dentro do
container (o host pode ter interceptação de TLS no npm):
```bash
docker compose exec frontend npm install --legacy-peer-deps
docker compose exec frontend npm test
```
> `--legacy-peer-deps`: React 19 ainda tem ranges de peer-deps em transição nas
> libs de teste. A mesma flag é usada no CI (`.github/workflows/frontend-tests.yml`).

Cobrem: helpers puros (`statusSolicitacao`/`statusAssinante`/`validacaoMensagem`),
`ValidarAcao` (validação íntegra/divergente), `TrocarSenhaCard` (sucesso/erro) e
tratamento de **409** (senha legada) e **429** (throttle) no fluxo de assinar.

## E2E de assinatura (Playwright)

### Local / containerizado
Via serviço `e2e` do compose (rede interna, `PY_BASE=http://nginx`). Os scripts
carregam o **mesmo `ci/seed-e2e.sql`** do CI antes de rodar (idempotente):
```bash
docker compose up -d                  # stack de pé
scripts/e2e-assinatura.sh             # seed + e2e (bash)
scripts\e2e-assinatura.ps1            # seed + e2e (PowerShell)
# só o seed:
scripts/seed-e2e.sh                   # carrega ci/seed-e2e.sql no Postgres local
# pular o seed:
NO_SEED=1 scripts/e2e-assinatura.sh
```
Cobre via HTTP: assinar + hash + evidências + comprovante, recusar, throttle 429.

### No CI (`.github/workflows/e2e-assinatura.yml`)
Abordagem leve (sem nginx/compose): services **Postgres + Redis**, carrega
`ci/legacy-schema.sql` + `ci/seed-e2e.sql`, sobe o backend via **uvicorn** e roda
o Playwright com `PY_BASE=http://localhost:8000`. Diferença vs. local: só o
`PY_BASE` (backend direto no CI; nginx no local) — **seed, spec e
playwright.config são os mesmos**. O backend no CI usa `JWT_SECRET_SOURCE=env`
e `TENANTS_STORAGE_ROOT=/tmp/...` (o runner não tem `/app`).

### O seed e2e (`ci/seed-e2e.sql`)
Idempotente, tenant-aware, ids fixos (tenant=1 sobral, admin@local.test
super-usuário com bcrypt **fixo de teste**, manifestante=1, assunto=1, unidade=3,
especie=2, acao ABERTURA). Cria só os pré-requisitos estáticos; a spec cria
processo/anexo/solicitação dinamicamente. **bcrypt embutido = exclusivo de teste.**
Roda com `session_replication_role = replica` para suspender triggers legados do
PHP (ex.: trigger de `utils.sistema` → `sistema_chamados.*`) durante o seed.

## Validação pública por código/token (PR2e)

Permite a um terceiro **sem login** validar uma assinatura pelo `codigo_validacao`
impresso no comprovante (texto + QR). O endpoint é anônimo e tenant-scoped pelo
subdomínio (TenantMiddleware), então o lookup é `(codigo, tenant_id)` — sem
bypass de RLS.

```
GET /api/v2/publico/validacao/{codigo}              → JSON minimizado
GET /api/v2/publico/validacao/{codigo}/comprovante.pdf → PDF público (com QR)
```

- **Respostas neutras e indistinguíveis** (404 `{valido:false}`) para token
  inexistente, revogado, processo sigiloso/não-ostensivo, anexo desentranhado,
  assinatura não-`assinada` ou tenant inativo — não vazam existência.
- **Revogação automática é lazy**: o estado atual (sigilo, desentranhamento,
  status) é re-checado a cada consulta. Revogação **manual**:
  `POST /api/v2/assinaturas/{id}/revogar-validacao-publica` (autenticado, com
  guard de sigilo).
- **Minimização (LGPD)**: a resposta pública só traz signatário, data, hash,
  algoritmo, versão e nº do processo (se ostensivo). Nunca IP/UA/método/
  evidências/CPF/matrícula/e-mail/dados do cidadão.
- **Rate-limit**: borda no nginx (`limit_req zone=validacao_publica` no path
  `/api/v2/publico/`) + app (Redis, `validacao_publica_throttle`, fail-open). A
  auditoria das respostas neutras é **deduplicada por IP** (no máx. 1 linha por
  janela) para não inundar o `audit_log` sob enumeração.
- **URL/QR**: derivada de `PUBLIC_BASE_URL` (se definido) ou
  `https://{slug}.{base_domain}/validar/{codigo}`. Defina `PUBLIC_BASE_URL` em
  produção (HTTPS público).
- O `codigo_validacao` é exposto ao servidor autenticado via **evidências** e
  impresso no **comprovante interno** (QR), para ele compartilhar/imprimir.

Para obter o código: assine → `GET /api/v2/assinaturas/{id}/evidencias` →
`codigo_validacao`. Página pública (frontend): `/validar` e `/validar/{codigo}`.

### Ressalvas operacionais (PR2e)

1. **`codigo_validacao` é um segredo compartilhável.** Trate-o como um **token
   opaco compartilhável**: quem possui o código/QR consegue consultar a
   validação pública. Porém a resposta é **minimizada** — não expõe evidências
   internas, IP, user agent, dados do cidadão, CPF, matrícula, e-mail nem o
   conteúdo do documento. Distribua o código apenas a quem deve poder validar.

2. **`PUBLIC_BASE_URL` é obrigatório em produção.** Antes de gerar comprovantes
   em produção, `PUBLIC_BASE_URL` precisa estar configurado com a **URL pública
   HTTPS correta** do tenant/sistema, para evitar QR Code ou link inválido no
   comprovante. Em dev, na ausência da variável, a URL é derivada do subdomínio
   (`https://{slug}.{base_domain}/validar/{codigo}`).

## Limitações conhecidas
- **TLS no host:** `npm install` no Windows host pode falhar
  (`UNABLE_TO_VERIFY_LEAF_SIGNATURE`); use o container (acima) ou o CI.
- **E2E API-level:** os specs usam o fixture `request` (sem browser/DOM);
  renderização de UI é coberta pelo Vitest, não pelo e2e.
- **409 MD5 no e2e:** não há como criar usuário só-MD5 via API; coberto no
  pytest (`test_md5_only_bloqueado`) e no Vitest (render do erro).
- **Compose completo no CI:** adiado — o e2e no CI usa a abordagem leve
  (Postgres+Redis+uvicorn). Subir nginx/compose/frontend no CI (para testes
  browser reais) fica para um PR futuro.
- **`agendamento` stub:** o dump (`ci/legacy-schema.sql`) tem a view
  `utils.servicosportais` que referencia `agendamento.*`; os workflows criam um
  stub mínimo desse schema antes de carregar o dump.

## Simular usuário com senha legada (para ver o 409)
O login rehasha MD5→bcrypt automaticamente; então simule **após** obter o token:
```bash
# 1) logue para obter um token (isso popula senha_bcrypt)
# 2) zere o bcrypt no banco para forçar o caminho legado:
docker exec -e PGPASSWORD=ged_password_secure_local ged-saas-project-db-1 \
  psql -U ged_user -d ged_saas_db \
  -c "UPDATE utils.usuario SET senha_bcrypt = NULL WHERE id = <ID>;"
# 3) chame POST /assinaturas/{id}/assinar com o token → 409 (credencial legada)
```
A saída esperada é o 409 com a orientação de atualizar a senha. Atualizar a
senha em `/perfil` (ou relogar) repopula o bcrypt e libera a assinatura.

## Validar o comprovante PDF
```bash
# autenticado (cookie/bearer), baixar:
GET /api/v2/assinaturas/{assinatura_anexo_id}/comprovante.pdf
```
Verificar: começa com `%PDF-`; contém processo/anexo, assinante, data/hora,
hash SHA-256 + algoritmo, versão, método/nível, resultado da validação e o
aviso “assinatura eletrônica interna com evidências — não é ICP-Brasil”.
O acesso respeita o sigilo do processo (404 para quem não tem credencial).
