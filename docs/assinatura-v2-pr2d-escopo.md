# PR 2d — Escopo Definitivo (E2E completo no CI + seed reproduzível)

**Autor:** Jorge + assistente · **Data:** 2026-05-28 · **Status:** escopo fechado (não implementado)

> Objetivo: tornar o e2e da Assinatura v2 executável de forma **confiável no CI**,
> com **seed reproduzível**, reduzindo dependência de execução manual/local —
> base para features sensíveis futuras (validação pública). **Validação pública
> não entra aqui.**

## 1. Diagnóstico do seed atual (por que precisamos de um novo)
- O e2e usa o "seed Sobral": `admin@local.test/admin123` (tenant id=1), catálogos
  `id_manifestante=1`, `id_assunto=1`, `id_unidade=3`, `id_especie=2`, e
  `usar_nup_federal` no tenant.
- `admin@local.test` é **super-usuário**, provisionado via `app/cli/tenant.py`
  (cria tenant + unidade + tipo_manifestante + usuário + **grupo nível 0** +
  `usuario_grupo`). Super-usuário → `load_permissions.is_super_usuario=True` →
  bypassa `require_permission` **e** o guard de sigilo (por isso o e2e valida/
  consulta evidências sem montar credencial fina).
- `seed-phase2.sql` / `seed-phase3.sql` são **pré-multi-tenant** (inserem
  `manifestante` sem `tenant_id`, hoje NOT NULL) → **não rodam** no schema atual.
  O banco dev veio desses seeds + migrations (tenant_id backfilled), não é
  reproduzível a partir deles.
- **Conclusão:** o e2e precisa de um **seed novo, tenant-aware, idempotente e de
  ids fixos**, alinhado ao schema atual.

## 2. Seed reproduzível para e2e (`ci/seed-e2e.sql`)
Criar um SQL idempotente (estilo `seed-phase*`, `INSERT ... ON CONFLICT DO
NOTHING` + `setval`), **ids fixos** (casam com a spec atual), **mínimo**:
- pré-requisitos de permissão: `utils.nivel` (valor=0 "Super Usuário") + um
  `Sistema` com `app='sistemas'`;
- `aprimora_py.tenant` id=1 (slug `sobral`, `usar_nup_federal=true`,
  `codigo_orgao_nup`);
- super-usuário `admin@local.test` (bcrypt de `admin123` + md5 p/ compat) +
  `grupo` nível 0 + `usuario_grupo`;
- catálogos: `categoria` (PF), `tipo_manifestante` id=1, `manifestante` id=1,
  `tipo_unidade_trabalho`, `unidade_trabalho` id=3, `tipo_processo`,
  `assunto` id=1, `especie_documental` id=2 (REQUERIMENTO), `acao` (ABERTURA);
- **opcional** (se algum teste exigir): usuário **legado MD5**
  (`senha_bcrypt=NULL`) e/ou usuário **sem credencial** de sigilo para o teste de
  bloqueio.

Propriedades exigidas: idempotente, determinístico, pequeno, rápido,
independente do dump dev. O `bcrypt` do admin é gerado uma vez e fixado no SQL
(não precisa rodar Python no load).

> **Decisão humana:** o hash bcrypt fixo no SQL (gerado uma vez) é aceitável, ou
> prefere um pequeno *seed Python* (`app/cli/seed_e2e.py`) que calcula o hash e
> faz upsert? (SQL é mais simples no CI; Python reaproveita `hash_password` e
> `cli/tenant.py`.) Proposta: **SQL** pela simplicidade/determinismo no CI.

## 3. Workflow e2e no CI (`.github/workflows/e2e-assinatura.yml`)
**Abordagem recomendada (leve, sem build de imagem):** espelha o
`backend-tests.yml`.
- `services: postgres:16, redis:7`.
- Passos: `pip install -e backend[.dev]` → carregar `ci/legacy-schema.sql` →
  `alembic stamp head` → bootstrap role `aprimora_app` (igual backend-tests) →
  **carregar `ci/seed-e2e.sql`** → subir `uvicorn` em background + esperar
  `/api/v2/health` → `cd tests-e2e && npm install --legacy-peer-deps` →
  `PY_BASE=http://localhost:8000 npx playwright test specs/assinatura-v2.spec.ts`.
- Sem nginx/compose/frontend: a spec é API-level e o throttle 429 é app-level
  (Redis) — não dependem do nginx. Falha clara + upload do report como artifact.

**Alternativa (máxima paridade com local):** `docker compose up` de
db+redis+backend+nginx, carregar o seed, rodar o serviço `e2e` (PY_BASE=
http://nginx). Mais fiel ao local, porém mais lento (build) — manter como plano
B se a paridade de PY_BASE for considerada essencial.

> **Decisão humana:** recomendado = abordagem leve (services + uvicorn,
> PY_BASE=backend). A única diferença para o local é o `PY_BASE` (nginx local vs
> backend no CI); **seed, spec e playwright.config são os mesmos** — não são
> "dois mundos" de lógica. Aceita essa diferença fina, ou exige compose no CI?

## 4. E2E coberto no CI
assinar + hash; consultar evidências; gerar comprovante; recusar; throttle 429;
validação autorizada. **Bloqueio de usuário sem permissão**: incluir **se** o
seed trouxer um usuário não-super com credencial baixa + um processo sigiloso
(senão, documentar que esse caso fica no pytest `test_sigilo_enforcement`/
`test_assinatura_v2`).

## 5. Scripts locais alinhados ao CI
- Artefato compartilhado: **`ci/seed-e2e.sql`** (mesmo arquivo no CI e local).
- `scripts/seed-e2e.{sh,ps1}` (novo) — carrega `ci/seed-e2e.sql` no Postgres da
  stack local (idempotente).
- `scripts/e2e-assinatura.{sh,ps1}` (do PR2c) passa a, opcionalmente, rodar o
  seed antes (flag `--seed`) e segue usando o serviço `e2e` do compose.
- Evitar divergência: mesmos seed/spec/config; só `PY_BASE` muda (documentado).

## 6. Documentação
Atualizar `docs/assinatura-v2-operacao.md`: rodar e2e local (com seed); como o CI
executa (services + seed + uvicorn + playwright); como o seed é carregado;
depurar falhas (artifact do report, logs do uvicorn); limitações conhecidas.

## 7. Fora de escopo (PR 2d)
validação pública anônima; token público; gov.br; ICP-Brasil; carimbo de tempo
externo; assinatura qualificada; hash chain de audit_log; versionamento completo
de GED; mudanças grandes de UI; novas features de assinatura além do necessário
para testar.

## 8. Arquivos prováveis
- `ci/seed-e2e.sql` (novo).
- `.github/workflows/e2e-assinatura.yml` (novo).
- `scripts/seed-e2e.sh` + `.ps1` (novos); ajuste em `scripts/e2e-assinatura.*`.
- `docs/assinatura-v2-operacao.md` (atualização).
- Possível ajuste mínimo na spec/config se for preciso parametrizar `PY_BASE`
  (já lido de env — provavelmente nada).

## 9. Riscos
- **Permissões do super-usuário no seed:** depende de `nivel(valor=0)` + `sistema
  app='sistemas'` existirem; o seed deve criá-los. Errar isso → admin não vira SU
  → 403/404 nos endpoints. Mitigar com um teste/asserção de smoke no início.
- **Ids fixos vs CI fresco:** a spec usa ids fixos (1/1/3/2); ok porque o CI
  parte de banco vazio. Em banco já populado, `ON CONFLICT` evita erro mas pode
  divergir — documentar que o seed e2e pressupõe banco de teste.
- **Custo/tempo no CI:** abordagem leve evita build de imagem; uvicorn em
  background + healthcheck precisa de espera robusta.
- **`legacy-schema.sql` desatualizar:** se o schema mudar, regenerar (já
  documentado no `ci/README.md`).
- **bcrypt fixo no SQL:** se a política de hash mudar, o seed precisa ser
  regerado — documentar.

## 10. Critérios de aceite
- Commits do PR 2c no remoto ✅ (já enviados: `f922d82`, `ee34da4`).
- Escopo do PR 2d documentado (este arquivo).
- **Seed e2e reproduzível** (`ci/seed-e2e.sql`) idempotente/determinístico — ou
  justificativa clara se ainda depender parcialmente do seed atual.
- **Workflow e2e no CI** funcionando — ou, havendo bloqueio real, alternativa
  documentada + plano de resolução.
- Scripts locais alinhados ao fluxo do CI (mesmo seed/spec).
- Testes existentes seguem passando (pytest 132, vitest 17, e2e 3).
- Relatório final: arquivos alterados, testes executados, limitações, próximos passos.

---

> **Parar aqui.** Nenhum código alterado. Aguardando autorização para implementar
> o PR 2d (e as decisões do §2 — seed SQL vs Python — e §3 — CI leve vs compose).
