# PR 2c — Escopo Definitivo (Assinatura v2: confiabilidade, CI e experiência de senha)

**Autor:** Jorge + assistente · **Data:** 2026-05-28 · **Status:** escopo fechado (não implementado)

> Continuação do [PR 2b](assinatura-v2-pr2b-escopo.md) (entregue em `070878b`).
> **Prioridade ajustada:** NÃO começar pela validação pública. O 2c consolida a
> Assinatura v2 como feature **operacionalmente confiável e testável**, reduzindo
> dependência de verificação manual, antes de abrir qualquer validação pública.

## 1. Objetivo
- Cobrir os fluxos de UI de assinatura com **teste de componente automatizado**
  (hoje inexistente — frontend só tem `next lint`).
- Rodar o **e2e de assinatura no CI** (ou subconjunto crítico + script local).
- Dar uma **saída clara ao usuário com senha legada (MD5)**, sem nunca permitir
  assinatura via MD5.
- **Documentar** como rodar tudo (backend, frontend, e2e, container, simular
  senha legada, conferir comprovante).

---

## 2. Testes de frontend / componentes

**Estado atual:** `frontend/package.json` não tem framework de teste (Next 15 +
React 19; só `dev/build/start/lint`).

**Estratégia (Vitest + React Testing Library):**
- Devdeps: `vitest`, `@testing-library/react@^16` (suporta React 19),
  `@testing-library/jest-dom`, `jsdom`, `@vitejs/plugin-react`.
- `vitest.config.ts`: `environment: "jsdom"`, `globals: true`, setup file
  (`vitest.setup.ts` com `@testing-library/jest-dom`), alias `@/` → raiz (via
  `vite-tsconfig-paths` ou `resolve.alias`).
- Script `"test": "vitest run"` (+ `"test:watch"`).
- **Mock de `@/lib/api`** (`vi.mock`) — sem rede. Wrapper de teste com
  `QueryClientProvider` + os providers usados (Toast/Confirm) ou mocks leves.
- **Ajuste de robustez p/ testabilidade (pequeno, permitido pelo §6):** extrair
  helpers puros — `statusBadgeInfo(status)` e `validacaoMensagem(v)` — e
  testá-los sem render, reduzindo o acoplamento aos providers.

**Casos mínimos:**
1. status da assinatura renderiza (pendente/assinada/recusada/cancelada);
2. nível/método renderizam;
3. badge de recusa aparece quando `status==='recusada'` (+ motivo);
4. ação **Validar** dispara `api.assinaturas.validar` (mock) e mostra a mensagem;
5. **409** (senha legada): `assinar` lança `ApiError(…, 409)` → mensagem clara exibida;
6. **429** (throttle): `assinar` lança `ApiError(…, 429)` → mensagem de espera;
7. validação **bem-sucedida** → "Assinatura íntegra";
8. validação **inválida** → "Documento alterado após a assinatura".

> Se Vitest/RTL se mostrar inviável (ex.: provider/SSR), alternativa: testes de
> unidade dos helpers puros + e2e ampliado. Justificar no relatório. **Não**
> depender só de verificação manual nesses fluxos.

---

## 3. E2E no CI

**Estado atual:** `tests-e2e/specs/assinatura-v2.spec.ts` (PR2b) roda via
container node na rede do compose. CI (`backend-tests.yml`) só roda pytest.

**Dependência crítica:** o e2e usa o **seed Sobral** (admin@local.test,
manifestante/assunto/unidade/espécie). O pytest-CI carrega só schema
(`ci/legacy-schema.sql`), sem seed → o e2e precisa da **stack real com seed**.

**Estratégia (em ordem de preferência):**
- **A — workflow dedicado `e2e.yml`:** `docker compose up -d` da stack (db+seed,
  backend, nginx, redis; frontend só se algum teste navegar — os atuais são
  API-level e dispensam o frontend), espera health, `npm ci` em `tests-e2e`,
  `npx playwright test`, derruba. Registry npm é acessível no GitHub Actions
  (o bloqueio de TLS é só no host local).
- **B — se a stack+seed ficar cara/instável no CI:** rodar no CI só o
  **subconjunto crítico** (assinar+hash+comprovante, recusar, 429) e manter o
  e2e completo como **manual documentado**.
- **C — script único reproduzível** `scripts/e2e-assinatura.sh` (ou `.ps1`):
  encapsula o `docker run` na rede do compose (o comando que já usamos no PR2b),
  para rodar local/containerizado de forma consistente.

**Cobertura alvo no CI (se viável):** assinar+hash+evidências+comprovante;
recusar; throttle 429; validação autorizada; bloqueio de acesso indevido (guard).

> Decisão humana: aceitar o custo de subir a stack no CI (A) ou ir de subconjunto
> + script (B+C)? Proposta: começar por **C** (script — destrava já) e **A** se o
> seed for reproduzível sem fricção; senão **B**.

---

## 4. Decisão sobre o fluxo de senha legada

**Achado (PR2b):** não há troca de senha self-service; o login já **rehasha
MD5→bcrypt**. A mensagem 409 atual orienta relogin.

**Decisão proposta:** **implementar troca de senha mínima e segura** (é pequeno
e serve direto ao objetivo):
- Backend: `POST /auth/alterar-senha` (autenticado) — valida a senha atual via
  `verify_password`, grava `senha_bcrypt = hash_password(nova)`. Não escreve MD5.
  Regras: exige senha atual correta; nova com tamanho mínimo; auditável.
- Frontend: form simples em `/perfil` (atual / nova / confirmar).
- **Regra inviolável:** assinatura **nunca** via MD5 (mantido do PR2b; o guard
  `needs_rehash → 409` permanece).

> Se na implementação isso se revelar maior que o previsto (ex.: política de
> senha, e-mails), reduz-se ao **botão/orientação** clara apontando relogin e
> registra-se a troca self-service como pendência. A mensagem clara atual
> **permanece** em qualquer caso.

---

## 5. Documentação operacional

Criar/atualizar doc (ex.: `docs/assinatura-v2-operacao.md` ou seção no RUNBOOK):
- rodar **testes backend** (pytest no container);
- rodar **testes frontend** (vitest);
- rodar **e2e** (local + via container na rede do compose, com o comando exato);
- **limitações conhecidas** (TLS no host; e2e API-level sem DOM; 409 MD5 só no pytest);
- **simular usuário com senha legada** (zerar `senha_bcrypt` no DB → próxima
  assinatura cai no 409);
- **conferir o comprovante PDF** (endpoint + o que validar visualmente).

---

## 6. Pequenos ajustes de robustez (permitidos)
Corrigir problemas pequenos achados ao escrever os testes, **desde que NÃO**:
altere o modelo jurídico da assinatura; mude schema sem necessidade; implemente
validação pública; mexa em gov.br/ICP-Brasil; refatore permissões amplamente.

---

## 7. Arquivos prováveis
- Frontend (testes): `frontend/package.json` (+ devdeps/script), `vitest.config.ts`,
  `vitest.setup.ts`, `components/__tests__/AssinaturasProcesso.test.tsx`,
  `app/(app)/para-assinar/__tests__/...test.tsx`; possível extração de helpers
  puros em `components/AssinaturasProcesso.tsx` / um util.
- E2E/CI: `.github/workflows/e2e.yml` (novo) e/ou `scripts/e2e-assinatura.sh`.
- Senha legada: `backend/app/routers/auth.py` (endpoint), `backend/app/schemas/auth.py`,
  `backend/app/services` (se necessário), `backend/tests/test_alterar_senha.py`,
  `frontend/app/(app)/perfil/page.tsx`, `frontend/lib/api.ts`.
- Docs: `docs/assinatura-v2-operacao.md` (ou RUNBOOK).

## 8. Riscos
- **Vitest + React 19 + providers:** mocar Toast/Confirm/QueryClient pode exigir
  ajuste; mitigado pelos helpers puros.
- **Stack+seed no CI:** custo/tempo de subir tudo; mitigado pela divisão A/B/C.
- **`npm install` no host** falha por TLS (`UNABLE_TO_VERIFY_LEAF_SIGNATURE`); no
  CI e em container funciona — a doc deve deixar isso explícito.
- **Endpoint de troca de senha:** garantir verificação da senha atual + auditoria;
  não virar vetor de brute-force (auth obrigatória).

## 9. Fora de escopo (PR 2c)
validação pública anônima; token público de validação; gov.br; ICP-Brasil;
carimbo de tempo externo; assinatura qualificada; hash chain de audit_log;
versionamento completo de GED; reformulação grande de UI; IA.

## 10. Critérios de aceite
- Framework de teste de frontend instalado e rodando; casos do §2 cobertos
  (ou alternativa justificada — **não** só manual).
- E2E de assinatura rodando no CI **ou** subconjunto crítico no CI + script único
  documentado para o restante.
- Fluxo de senha legada melhorado (troca self-service mínima **ou** orientação
  objetiva + pendência registrada); **assinatura nunca via MD5**.
- Documentação operacional publicada.
- Sem regressão (suíte backend + e2e verdes); sem mudanças fora do escopo.

---

> **Parar aqui.** Nenhum código alterado. Aguardando autorização para implementar
> o PR 2c (e a decisão do §3 sobre CI e do §4 sobre troca de senha).
