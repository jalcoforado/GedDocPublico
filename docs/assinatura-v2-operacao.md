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
Via serviço `e2e` do compose (rede interna, `PY_BASE=http://nginx`):
```bash
# stack de pé + seed Sobral
docker compose up -d
# script padronizado:
scripts/e2e-assinatura.sh                 # (bash)
scripts\e2e-assinatura.ps1                # (PowerShell)
# ou direto:
docker compose --profile test run --rm e2e npx playwright test specs/assinatura-v2.spec.ts
```
Cobre via HTTP: assinar + hash + evidências + comprovante, recusar, throttle 429.

## Limitações conhecidas
- **TLS no host:** `npm install` no Windows host pode falhar
  (`UNABLE_TO_VERIFY_LEAF_SIGNATURE`); use o container (acima) ou o CI.
- **E2E API-level:** os specs usam o fixture `request` (sem browser/DOM);
  renderização de UI é coberta pelo Vitest, não pelo e2e.
- **409 MD5 no e2e:** não há como criar usuário só-MD5 via API; coberto no
  pytest (`test_md5_only_bloqueado`) e no Vitest (render do erro).
- **Stack completa no CI (workflow e2e):** adiada — hoje o CI roda pytest +
  vitest; o e2e roda local/containerizado pelo script.

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
