# TECH-2 — Estabilizar testes e dependências

> Documento **somente de escopo**. Nada será implementado sem autorização.
> Estado base: `origin/main` em `353a669` (TECH-1 publicado).
> Meta: `pytest` completo sem ignore, `vitest` verde, `tsc=0`, testes
> idempotentes e independentes de leftovers de E2E.

## 1. Resumo executivo

Duas ressalvas conhecidas, ambas pré-existentes ao TECH-1:

| # | Sintoma | Causa-raiz | Corte |
|---|---|---|---|
| **A** | `test_jwt_compat.py` falha na coleção (`ModuleNotFoundError: 'jwt'`) | **Imagem Docker do backend stale** — `pyproject.toml` e `Dockerfile` já estão corretos, mas o `pip install -e ".[dev]"` foi cacheado em build que pré-datava a seção `[dev]` | Rebuild da imagem (não muda código) |
| **B** | `test_backfill_existing_users_are_false` falha quando há leftovers de E2E no tenant default | Query do teste é **global** — conta usuários em todos os tenants com `must_change_password=true`. E2E (SEC-1, UX-1) e smoke manuais geram usuários flagged que ficam vivos quando o cleanup é abortado | Reescrever o teste para escopo determinístico (usuário-âncora ou exclusão de domínios `.test`) |

Ambos são **fix de teste/build, não de runtime**. Nenhum afeta produção.

## 2. Diagnóstico A — Falha PyJWT

### 2.1. Estado do código (✅ correto)

- [backend/pyproject.toml:32](backend/pyproject.toml#L32) — `PyJWT==2.10.1` está em
  `[project.optional-dependencies].dev`, junto com `pytest==8.3.4`,
  `pytest-asyncio==0.25.0`, `pytest-cov==6.0.0`.
- [backend/Dockerfile:16](backend/Dockerfile#L16) — `RUN pip install --upgrade pip
  && pip install -e ".[dev]"` instala explicitamente o extra `dev`. Comentário no
  arquivo confirma a intenção: *"Inclui dev deps (pytest, pytest-asyncio, pytest-cov,
  PyJWT) para rodar testes dentro do container"*.

### 2.2. Estado da imagem em execução (❌ stale)

`docker compose exec backend pip show PyJWT` ⇒ **`Package(s) not found: PyJWT`**.
`docker compose exec backend pip list | grep pytest` ⇒ **`pytest 9.0.3`** (pinned
em 8.3.4) e `pytest-asyncio 1.4.0` (pinned em 0.25.0).

Ambas as discrepâncias apontam pro mesmo culpado: **cache de camada Docker**.
O Dockerfile copia `pyproject.toml` ANTES de instalar, então qualquer build
anterior à introdução da seção `[dev]` (commit `fdd8696`, 27-mai-2026)
cacheia uma camada de `pip install` SEM as dev deps. Builds posteriores
reaproveitam essa camada se o checksum do `pyproject.toml` colide
casualmente, ou se foram rodados com cache.

### 2.3. Função do teste

[backend/tests/test_jwt_compat.py:1-5](backend/tests/test_jwt_compat.py#L1-L5) é
explícito sobre o porquê de usar **PyJWT, não `python-jose`** (que já é runtime
do projeto):

> *We use PyJWT (independent of python-jose) as a stand-in for the PHP-side
> firebase/php-jwt 5.0.0 decoder: both implement RFC 7519 HS256.*

O teste prova que o token emitido pelo `app.auth.jwt.encode_token`
(via `python-jose`) é estruturalmente válido por **outra implementação**
do HS256 (PyJWT) — proxy para o decode do PHP. **Não dá pra remover PyJWT
sem perder essa cobertura de interoperabilidade**, que é o ponto da Fase 0
do Strangler Fig.

### 2.4. Correção proposta (mínima, sem mudar código)

**Plano A (recomendado):** `docker compose build backend --no-cache` (ou
forçar rebuild da camada de pip install via `RUN pip install ... && \
echo "rebuild-$(date)"` — mais hacky). Resultado esperado:
- PyJWT instalado.
- `pytest==8.3.4` reinstalado conforme pin.
- `test_jwt_compat.py` passa a coletar e rodar (2 testes esperados).
- Imagem ganha alguns MB de dev deps (já estava no projeto, só não estava
  instalada).

**Plano B (alternativo, mais robusto a longo prazo):** adicionar um
`.dockerignore` que não inclua o `pyproject.toml`, ou mudar a ordem do
Dockerfile pra `COPY pyproject.toml` ser sucedido por `RUN pip install`
sempre que muda — já é assim, então só rebuild resolve.

**Plano C (não escolher):** trocar PyJWT por jose. Custaria a cobertura
de interop independente.

### 2.5. Risco

Baixo. Rebuild de imagem é operação rotineira de dev. Os pacotes recém-instalados
(`pytest 8.3.4`, `pytest-asyncio 0.25.0`) estão um patch atrás do que está
rodando hoje (`9.0.3`, `1.4.0`). Se algum teste depender de comportamento
do pytest 9 ou pytest-asyncio 1.x, **pode haver regressão** — vale rodar
a suite após o rebuild antes de declarar vitória.

## 3. Diagnóstico B — `test_backfill_existing_users_are_false` sensível a leftovers

### 3.1. Que o teste verifica hoje

[backend/tests/test_sec1_must_change_password_schema.py:91-117](backend/tests/test_sec1_must_change_password_schema.py#L91-L117):

```python
async def test_backfill_existing_users_are_false(admin_engine):
    """Todos os usuários existentes ficaram com must_change_password=false
    após o backfill (D-BACKFILL — usuários legados não são forçados)."""
    total = ...SELECT COUNT(*) FROM utils.usuario
            WHERE ativo = true AND excluido = false
    flagged = ...SELECT COUNT(*) FROM utils.usuario
              WHERE ativo = true AND excluido = false
                AND must_change_password = true
    assert total > 0
    assert flagged == 0
```

**Intenção original:** validar que a migration `0030_add_must_change_password`
fez backfill correto (todos os usuários **pré-existentes** ficaram com `false`).

**Problema:** a query é **global e atemporal**. Conta tudo que estiver
ativo no momento, em qualquer tenant. SEC-1 introduziu fluxos que **legitimamente**
criam usuários flagged (POST `/usuarios`, reset, provisionamento), e E2E exercita
esses fluxos. Quando cleanup do spec é abortado, o usuário flagged sobrevive e
o teste falha.

### 3.2. Inventário dos leftovers atuais

`SELECT email, tenant_id, must_change_password, ativo, excluido FROM utils.usuario WHERE email LIKE '%@e2e.test' OR email LIKE 'sec1-%' OR email LIKE 'dbg%-%'`
retorna ~30 linhas. Padrões:

| Padrão | Origem | Estado atual | Quantos contam pro teste? |
|---|---|---|---|
| `sec1-${suf}@e2e.test` (cleanup OK) | `sec-must-change-password.spec.ts` (afterAll funcionou) | `ativo=false, excluido=true` | **0** (filtrados) |
| `sec1-manual2@e2e.test` | smoke manual abortado | `ativo=true, excluido=false, flag=true` | **1** |
| `dbg2-mq37q2lv@e2e.test`, `dbg3-...`, `dbg4-...` | smoke manual SEC-1 (3 leftovers) | `ativo=true, excluido=false, flag=true` | **3** |
| `${cpf}@ux1smoke.test` | `ux1-smoke.spec.ts` | varia | **0–N** dependendo do cleanup |

Total atualmente contado pelo teste: **4 leftovers** vivos, todos com domínios
`.test` e/ou prefixos `sec1-` / `dbg`. O fluxo de produção real **nunca**
geraria emails assim.

### 3.3. Por que cleanup do spec não cobre tudo

O spec SEC-1 ([tests-e2e/specs/sec-must-change-password.spec.ts:214-217](tests-e2e/specs/sec-must-change-password.spec.ts#L214-L217))
faz `test.afterAll(deletarUsuario)`. Funciona em runs completos. Mas:
- Abort manual (Ctrl+C, fechar terminal) pula o `afterAll`.
- Smoke manual (`dbg-*`) não tem afterAll — é manual, sem framework.
- `ux1-smoke.spec.ts` cria com domínio `@ux1smoke.test` (não `@e2e.test`)
  — se o cleanup falhar lá, o filtro por `@e2e.test` não pega.

### 3.4. Correção proposta (mínima)

**Plano A (recomendado): pin no usuário-âncora.** Reescrever o teste pra
verificar que **um usuário conhecido pré-migração** continua `false`:

```python
async def test_backfill_existing_users_are_false(admin_engine):
    """Migration 0030 fez backfill: o usuário-âncora (admin@local.test,
    presente no provisionamento inicial e portanto pré-migração) tem
    must_change_password=false. Sanity check de D-BACKFILL."""
    async with _sm(admin_engine)() as s:
        row = (
            await s.execute(
                text(
                    "SELECT must_change_password FROM utils.usuario "
                    "WHERE email = 'admin@local.test' AND tenant_id = 1 "
                    "  AND ativo = true AND excluido = false"
                )
            )
        ).scalar_one_or_none()
    assert row is False, (
        "D-BACKFILL violado: admin@local.test (pré-migração) deveria estar "
        "com must_change_password=false."
    )
```

Vantagens:
- Determinístico — independe de quantos usuários existem ou se há leftovers.
- Direto ao ponto — testa exatamente o que a migration prometeu (existing
  users went to false).
- Robusto a evolução do projeto (novos tenants, novos usuários).

Desvantagem:
- Depende de `admin@local.test` existir no tenant default em dev.
- Se algum reset administrativo for feito nele, o teste flagga corretamente
  (semântica preservada).

**Plano B (alternativa): exclude E2E patterns.** Manter contagem global,
mas excluir domínios `.test` e prefixos `dbg*`:

```python
flagged = ...
    AND must_change_password = true
    AND email NOT LIKE '%@e2e.test'
    AND email NOT LIKE '%@ux1smoke.test'
    AND email NOT LIKE 'dbg%-%'
```

Vantagens: mantém a contagem agregada (mais informativa).
Desvantagens: lista de exclusão precisa ser mantida; vazamento de e-mail real
com padrão `dbg-*` é improvável mas conceitualmente possível.

**Plano C (não recomendar):** desabilitar o teste / mover para skip.
Perde a cobertura. Não atinge o critério "sem ignore".

**Recomendo o Plano A.**

### 3.5. Cleanup dos leftovers vivos (uma vez)

Independente do Plano A/B do teste, recomendo **purgar** os 4 leftovers vivos
antes de fechar o TECH-2:

```sql
-- Cuidado: rodar apenas em DEV.
DELETE FROM utils.usuario_grupo
  WHERE id_usuario IN (
    SELECT id FROM utils.usuario
      WHERE email LIKE '%@e2e.test' OR email LIKE 'dbg%-%@%'
  );
DELETE FROM utils.usuario
  WHERE email LIKE '%@e2e.test' OR email LIKE 'dbg%-%@%';
```

(Verificar se há FKs adicionais; ajustar ordem se necessário.) Risco em dev:
nenhum. Em prod: nunca rodar — domínios `.test` são RFC 6761 reservados,
nenhum usuário real os usa.

## 4. Diagnóstico C — Hygiene Playwright (opcional, fora do mínimo)

### 4.1. Padrão atual nos specs

| Spec | Domínio de e-mail | Tem afterAll cleanup? |
|---|---|---|
| `sec-must-change-password.spec.ts` | `@e2e.test` (prefix `sec1-`) | ✅ `deletarUsuario` |
| `ux1-smoke.spec.ts` | `@ux1smoke.test` | (auditar — fora do escopo de leitura agora) |
| `auth.spec.ts` | (não cria usuário) | — |
| `cidadao-flow.spec.ts` / `balcao-flow.spec.ts` / `portal-cidadao-wizard.spec.ts` / `assinatura-v2.spec.ts` / `prazos.spec.ts` / `routing.spec.ts` | (auditar caso a caso) | — |

### 4.2. Proposta (mínima, opcional)

**Não ampliar o escopo TECH-2 para padronizar todos os specs**. Mas vale
**registrar** no RUNBOOK uma convenção:
- Domínio `.test` reservado para test users (RFC 6761).
- Prefixo de slug + sufixo aleatório evita colisão.
- `afterAll` obrigatório (soft delete).
- Quem rodar smoke manual deve fazer cleanup explícito.

Se a equipe quiser ir além, dá pra propor depois (TECH-3 hipotético):
tenant isolado pra E2E, snapshot/restore do DB, etc.

## 5. Tabela de testes impactados

| Teste | Estado | Após TECH-2 |
|---|---|---|
| `test_jwt_compat.py::test_emitted_token_has_required_claims` | ❌ coleta falha | ✅ roda após rebuild da imagem |
| `test_jwt_compat.py::test_token_rejected_with_wrong_secret` | ❌ idem | ✅ idem |
| `test_sec1_must_change_password_schema.py::test_backfill_existing_users_are_false` | ❌ falha por leftovers | ✅ passa com Plano A (usuário-âncora) |
| Restante da suite pytest (334 testes) | ✅ | ✅ inalterado |
| `vitest` (243 testes) | ✅ | ✅ inalterado |
| `tsc --noEmit` | ✅ 0 erros | ✅ inalterado |
| Playwright SEC-1 (5 testes) | ✅ | ✅ inalterado (specs não são tocados) |

## 6. Plano de execução

Ordem recomendada:

1. **Família A — PyJWT (rebuild)**
   - `docker compose build backend --no-cache` (apenas o serviço backend; ~3-5 min).
   - `docker compose up -d backend` para subir o container novo.
   - Validar: `docker compose exec backend pip show PyJWT` ⇒ encontrado;
     `pytest --version` ⇒ 8.3.4.
   - Rodar `pytest tests/test_jwt_compat.py` ⇒ esperar 2 passes.
   - **Risco residual:** se a downgrade de pytest (9 → 8) ou pytest-asyncio
     (1.x → 0.25) quebrar algum outro teste, registrar e ajustar pin.
2. **Família B — `test_backfill` (1 arquivo)**
   - Reescrever o teste conforme Plano A (usuário-âncora `admin@local.test`).
   - Rodar `pytest tests/test_sec1_must_change_password_schema.py` ⇒ 6 passes.
3. **Cleanup dos leftovers vivos (SQL único)**
   - Executar `DELETE` dos 4 usuários `*@e2e.test`/`dbg*-*@*` ativos no
     tenant default. **Apenas dev**.
4. **Suite completa**
   - `pytest tests/` ⇒ esperar **341/341** (334 + 2 jwt + 5 reescrito-mas-mesmo-nome,
     mantendo 6 do schema test).
   - `vitest run` ⇒ 243/243.
   - `tsc --noEmit` ⇒ 0.
5. **(Opcional) Parágrafo no RUNBOOK** com a convenção de domínio `.test` e
   responsabilidade de cleanup.

## 7. Estimativa de impacto

| Família | Arquivos | Linhas Δ | Runtime |
|---|---|---|---|
| A — PyJWT | 0 (só rebuild) | 0 | inalterado |
| B — `test_backfill` | 1 (`tests/test_sec1_must_change_password_schema.py`) | ~15 (reescrita do método) | inalterado |
| Cleanup SQL | 0 (execução pontual) | 0 | dev DB perde 4 leftovers de teste |
| RUNBOOK | 1 (opcional) | ~15 | n/a |
| **TOTAL** | **1–2 arquivos** | **~15–30 linhas** | **inalterado** |

## 8. Fora de escopo (reafirmado)

- ❌ Mudança em runtime do backend, frontend ou cliente.
- ❌ Mudança em payload, endpoint, schema, regra de negócio.
- ❌ Refactor amplo da suite de testes.
- ❌ Padronização de **todos** os specs Playwright (cada um auditado em TECH-3
  hipotético, se for o caso).
- ❌ Tenant dedicado para E2E (mudança grande de infraestrutura).
- ❌ Snapshot/restore do DB entre runs.
- ❌ Migração para nova lib de teste.
- ❌ Mudança no Dockerfile além do que é necessário pra dev deps (já está
  correto).
- ❌ Mudança em CI (não há CI versionado nesse repo neste momento, pelo que
  vejo; se houver, fica para próxima iniciativa).

## 9. Critérios de aceite

1. `pytest tests/` (suite completa) ⇒ **sem ignore**, todos os testes
   coletados e passando. Mínimo: `test_jwt_compat.py` e
   `test_backfill_existing_users_are_false` em verde sem ressalva.
2. `vitest run` ⇒ **243/243 verde** (zero regressão).
3. `tsc --noEmit` ⇒ **0 erros** (zero regressão).
4. **Zero arquivos** alterados em `backend/app/**`, `backend/alembic/**`,
   `frontend/app/**`, `frontend/components/**`, `frontend/lib/**`.
5. Único arquivo de teste alterado: `backend/tests/test_sec1_must_change_password_schema.py`
   (Família B).
6. Nenhum `@pytest.skip`, `pytestmark = skip`, ou `--ignore=` adicionado em
   pyproject.toml.
7. Imagem `aprimora-py-backend` rebuilt com `pip install -e ".[dev]"` produzindo
   PyJWT instalado e pytest na versão pin.

## 10. Decisões em aberto

1. **Plano A (usuário-âncora) vs Plano B (exclude patterns) para Família B?**
   Recomendo A. Aguardo aval.
2. **Executar o cleanup SQL dos 4 leftovers vivos como parte do TECH-2?**
   Recomendo sim, mesmo step. Aguardo aval.
3. **Documentar convenção `.test` no RUNBOOK como sub-step opcional?**
   Recomendo sim — ~10 linhas, zero código. Aguardo aval.
4. **Rebuild com `--no-cache` ou forçar bust via tag/touch?**
   Recomendo `--no-cache` (mais limpo, garantia). Aguardo aval.

---

**Próximo passo após este doc**: aguardar autorização para implementar com
as decisões de §10 confirmadas.
