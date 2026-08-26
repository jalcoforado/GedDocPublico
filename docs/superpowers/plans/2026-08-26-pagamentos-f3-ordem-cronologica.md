# Pagamentos F3 — Ordem Cronológica — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao módulo de pagamentos a fila cronológica legal (art. 141 da 14.133/2021): posição ganha na liquidação, apurada por fonte+unidade+categoria+exercício, com elegibilidade avaliada em toda mudança relevante, 409 ao preterir e exceção formal como único caminho de furar a ordem.

**Architecture:** Tabela `posicao_cronologica` (1:1 com débito na fila) alimentada por `confirmar_liquidacao`; posição **calculada** por window function na leitura, nunca armazenada; função pura `avaliar_elegibilidade` chamada nos pontos de mutação (autorização, ajuste, fornecedor, bloqueio, pagamento); guarda `assert_ordem_respeitada` nos atos de seleção da tesouraria (liberar/pagar); `excecao_cronologica` append-only destrava com `EXCECAO_AUTORIZADA`. Frontend: tela "Ordem cronológica" agrupada por chave de fila + seção Fila no detalhe.

**Tech Stack:** FastAPI + SQLAlchemy 2 async + Alembic (migration 0107), Next.js 15, pytest via `docker exec -e PYTEST_DB_HOST=db aprimora-py-backend`, vitest no host.

**Spec:** `docs/superpowers/specs/2026-08-06-pagamentos-fluxo-design.md` — §4.3 (`posicao_cronologica`, `excecao_cronologica`), §4.4 (`contrato.categoria`), §5 (marco, elegibilidade, preterição), §7.1/§7.5 (menu e tela), §9-F3 (aceite).

## Global Constraints

- Idioma pt-BR em tudo; commits terminam com `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Migration nova = **0107**, `down_revision="0106"`, head único, downgrade na ordem inversa. Tabelas novas com o boilerplate RLS completo (modelo: `_rls` da `0102`; GUC `app.tenant_id` com `current_setting(..., true)`, ENABLE+FORCE, grants tabela+sequence para `aprimora_app`, sem worker).
- `tenant_id` do caller, nunca do payload; 404 cross-tenant; `tenant_filter` nas queries.
- **Nunca gravar `Debito.status` direto** — toda transição de `situacao_fila` passa por `_registrar_transicao(..., fila=...)` (guarda AST `test_guarda_status_legado.py`).
- Rota literal antes da paramétrica (`test_guarda_ordem_rotas.py`); GET novo com `require_permission` (guarda de leitura); item de menu novo entra em `PERMISSOES_ESPERADAS` de `__tests__/menus.test.tsx`.
- Teste HTTP com usuário comum (não-SU) em toda rota nova — helpers de `test_pagamentos_f2_ajustes.py` (`_provisionar`, `_usuario_com`, `_setup_debito`, `_levar_ate_aguardando_*`, `_get`, `_post`) são reutilizáveis; sem ids de FK cravados; e-mails `.test`; cleanup no teardown.
- Guarda estrutural nova é provada por inversão antes do commit.
- Testes por task: `pytest tests/test_pagamentos_f3_*.py tests/test_guarda_ordem_rotas.py tests/test_guarda_modularizacao.py -q` no mínimo; famílias tocadas (filas/autorização/liberação) quando alterar `pagamentos_autorizacao.py`/`pagamentos_filas.py`. FOREGROUND sempre; nunca duas suítes simultâneas; `pgrep -af pytest` + kill se suspeitar de fantasma.
- **Não é job**: elegibilidade é recalculada sincronamente nos pontos de mutação (spec §5.2). Posição **nunca** é armazenada (§4.3).
- `Paginated<X>`/tipos de `api.ts` casando 1:1 com `response_model`.

## Rulings de planejamento (vinculantes)

1. **`exercicio` = ano de `data_liquidacao`** (o marco). Débito não tem coluna exercício; o da fila nasce do marco e fica gravado em `posicao_cronologica.exercicio`.
2. **`marco_em` = `data_liquidacao` (date) + hora do registro** (spec §5.1): `datetime.combine(data_liquidacao, hora_atual)`. Imutável, salvo alteração **material** de `data_liquidacao` via F2 (edição em `AJUSTE_*` versiona) — nesse caso o marco é regravado e o fato vai ao histórico (`acao='MARCO_REGRAVADO'`).
3. **Categoria do débito sem contrato**: `DebitoCreate`/`DebitoUpdate` ganham `categoria` opcional (`BENS|LOCACOES|SERVICOS|OBRAS`); na liquidação, débito **sem contrato e sem categoria → 422** apontando o campo. Com contrato, vale `contrato.categoria` (a coluna existe desde a 0085, nullable). `ContratoCreate` passa a **exigir** categoria; `ContratoUpdate` a aceita.
4. **Backfill da 0107**: `contrato.categoria IS NULL → 'SERVICOS'` (§4.4; 19 linhas no dev). Sem flag de "revisar" persistida (YAGNI) — a tela de contratos ganha a coluna/edição de categoria; o alerta é o banner descrito na Task 6.
5. **Preterição**: "à frente na mesma fila" = mesma chave `(id_unidade, id_fonte_recursos, categoria, exercicio)`, `situacao='ELEGIVEL'` e `marco_em` menor (desempate por `id`). Débito `BLOQUEADA`/`AGUARDANDO_DISPONIBILIDADE` à frente **não** bloqueia a seleção (não está elegível). Débito selecionado com `EXCECAO_AUTORIZADA` passa. A guarda entra em **liberar_parcelas E pagar_parcela** (os dois atos de seleção do rito atual).
6. **Elegibilidade persiste em dois lugares em sincronia**: `debito.situacao_fila` (via `_registrar_transicao`, que já incrementa lock e grava histórico) e `posicao_cronologica.situacao` (espelho, mesmo valor + `motivo_bloqueio`). Pontos de reavaliação (síncronos): `confirmar_liquidacao` (entrada), `autoridade_aprovar`, `solicitar_ajuste`/`responder_ajuste` (pedidos abertos ⇔ item 2 da elegibilidade), `atualizar_fornecedor` (situação cadastral mudou → reavalia débitos do fornecedor na fila), criar/ativar/desativar `bloqueio_saldo` (reavalia débitos da conta), `pagar_parcela` (pagamento integral → `CONCLUIDA`, já existe) e `estornar`. `cancelar` débito na fila → `RETIRADA`.
7. **Disponibilidade (item 4 da elegibilidade)** usa `saldo_conta(...).disponivel` da conta pagadora vs soma das parcelas não pagas do débito; sem conta pagadora ainda (pré-autorização) a condição não se aplica — débito só pode ser `ELEGIVEL` depois de `AUTORIZADA` de todo jeito.
8. **Exceção cronológica**: `POST /pagamentos/debitos/{id}/excecao-cronologica` sob `require_permission("pagamento_autorizar")`; `id_autoridade` = usuário autenticado; append-only, sem UPDATE/DELETE; débito precisa estar na fila (404 se não registrado) e não `CONCLUIDA`/`RETIRADA` (409). Registro → `EXCECAO_AUTORIZADA` nas duas persistências.
9. **A tela é leitura para todos os perfis** (§7.1 "Ordem cronológica — todos os perfis (leitura)"): gate = `require_any_permission(*PERMS_LEITURA)`, como as demais leituras do módulo.

---

## Estrutura de arquivos

| Arquivo | Papel |
|---|---|
| `backend/alembic/versions/0107_posicao_cronologica.py` | Create: 2 tabelas + backfill categoria |
| `backend/app/models/pagamentos.py` | Modify: `PosicaoCronologica`, `ExcecaoCronologica` |
| `backend/app/services/pagamentos_cronologia.py` | Create: registro do marco, fila com window function, `avaliar_elegibilidade`, `reavaliar_*`, `assert_ordem_respeitada`, exceção |
| `backend/app/services/pagamentos_debitos.py` | Modify: `confirmar_liquidacao` (registro + 422), `cancelar` (RETIRADA), hooks de ajuste, regravação de marco na edição material de `data_liquidacao` |
| `backend/app/services/pagamentos_autorizacao.py` | Modify: `autoridade_aprovar`→reavaliação; `liberar`/`pagar_parcela`→`assert_ordem_respeitada`; `estornar`→reavaliação |
| `backend/app/services/pagamentos_cadastros.py` | Modify: `atualizar_fornecedor` e bloqueios → reavaliação |
| `backend/app/routers/pagamentos_debitos.py` | Modify: GET fila-cronologica, GET /debitos/{id}/fila, POST excecao-cronologica |
| `backend/app/schemas/pagamentos.py` | Modify: `PosicaoFilaItem`, `FilaCronologicaGrupo`, `PosicaoDebitoOut`, `ExcecaoCronologicaIn/Out`, `categoria` em DebitoCreate/Update e ContratoCreate/Update |
| `backend/tests/test_pagamentos_f3_fila.py` | Create: marco, fila, posição, categoria |
| `backend/tests/test_pagamentos_f3_elegibilidade.py` | Create: 5 condições + reavaliações |
| `backend/tests/test_pagamentos_f3_pretericao.py` | Create: 409, preteridos, exceção |
| `frontend/lib/api.ts`, `frontend/lib/menus/pagamentos.ts`, `frontend/app/(app)/m/pagamentos/fila/page.tsx`, `frontend/components/pagamentos/DetalheDebitoContent.tsx`, tela de contratos | Modify/Create: tela da fila, menu, seção Fila, categoria em contratos |
| `frontend/__tests__/pagamentos-f3.test.tsx`, `__tests__/menus.test.tsx` | Create/Modify |

---

### Task 1: Migration 0107 + modelos

**Files:**
- Create: `backend/alembic/versions/0107_posicao_cronologica.py`
- Modify: `backend/app/models/pagamentos.py`
- Test: `backend/tests/test_pagamentos_f3_fila.py` (só o teste de invariante desta task)

**Interfaces:**
- Produces (nomes EXATOS — Tasks 2-5 dependem):

```python
class PosicaoCronologica(Base):        # pagamentos.posicao_cronologica
    id, tenant_id, id_debito (FK debito, UNIQUE (tenant_id, id_debito))
    id_unidade (FK utils.unidade_trabalho, NOT NULL)
    id_fonte_recursos (FK fonte_recursos, NOT NULL)
    categoria: str            # varchar(20) NOT NULL — BENS|LOCACOES|SERVICOS|OBRAS
    exercicio: int            # NOT NULL
    marco_em: datetime        # NOT NULL
    situacao: str             # varchar(30) NOT NULL — espelha debito.situacao_fila
    motivo_bloqueio: str|None # varchar(255)
    previsao_pagamento: date|None
    registrado_em: datetime   # NOT NULL server_default now()
    atualizado_em: datetime|None

class ExcecaoCronologica(Base):        # pagamentos.excecao_cronologica (append-only)
    id, tenant_id, id_debito (FK debito, NOT NULL)
    justificativa: str        # text NOT NULL
    fundamento: str           # varchar(255) NOT NULL
    id_autoridade (FK utils.usuario, NOT NULL)
    data_autorizacao: date    # NOT NULL
    id_usuario_registro (FK utils.usuario, nullable)
    documentos: dict|None     # jsonb — ids de anexo_debito
    criado_em: datetime       # NOT NULL server_default now()
```

- [ ] **Step 1: Migration** — as duas tabelas acima (DDL espelhando §4.3), índice de fila `ix_posicao_cronologica_fila` em `(tenant_id, id_unidade, id_fonte_recursos, categoria, exercicio, marco_em)`, índice `(tenant_id, id_debito)` em `excecao_cronologica`; `_rls` (padrão 0102) nas duas; CHECK `ck_posicao_categoria` (`categoria IN ('BENS','LOCACOES','SERVICOS','OBRAS')` — mesmo domínio do `ck_contrato_categoria` da 0085). Backfill: `UPDATE pagamentos.contrato SET categoria='SERVICOS' WHERE categoria IS NULL AND excluido=false` (e também `excluido=true`, tanto faz — aplicar sem filtro de excluido para não deixar NULL residual). `downgrade()`: drop `excecao_cronologica`, drop `posicao_cronologica`; o backfill de categoria NÃO é revertido (não há como saber quais eram NULL — registrar no docstring).
- [ ] **Step 2: Modelos** no padrão do arquivo + reexport em `models/__init__.py`.
- [ ] **Step 3: Teste de invariante (RED primeiro)** em `test_pagamentos_f3_fila.py`:

```python
async def test_nenhum_contrato_sem_categoria(admin_engine):
    # pós-0107: SELECT count(*) FROM pagamentos.contrato WHERE categoria IS NULL == 0
async def test_posicao_e_unica_por_debito(admin_engine, ...):
    # inserir 2ª posição para o mesmo débito → IntegrityError (prova o UNIQUE)
```

- [ ] **Step 4: Validar migration**

```bash
docker exec aprimora-py-backend alembic upgrade head    # 0107
docker exec aprimora-py-backend alembic heads           # único
docker exec aprimora-py-backend alembic downgrade -1 && docker exec aprimora-py-backend alembic upgrade head
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_rls_papeis_minimos.py tests/test_pagamentos_f3_fila.py -q
```

- [ ] **Step 5: Commit** `feat(pagamentos): migration 0107 — posicao_cronologica + excecao_cronologica + backfill de categoria (F3)`

---

### Task 2: Registro do marco na liquidação

**Files:**
- Create: `backend/app/services/pagamentos_cronologia.py` (início)
- Modify: `backend/app/services/pagamentos_debitos.py` (`confirmar_liquidacao:679-692`; `atualizar_debito` p/ regravação de marco; `cancelar`; criação aceita `categoria`), `backend/app/schemas/pagamentos.py` (`categoria` em `DebitoCreate`/`DebitoUpdate`/`DebitoOut`; obrigatória em `ContratoCreate`)
- Test: `backend/tests/test_pagamentos_f3_fila.py`

**Interfaces:**
- Consumes: `PosicaoCronologica` (T1); `_registrar_transicao(..., fila=...)`; `est.REGISTRADA/RETIRADA/NAO_REGISTRADA` (constantes já existem em `pagamentos_estados.py` — conferir nomes exatos).
- Produces (T3-T5 dependem):

```python
# pagamentos_cronologia.py
CATEGORIAS = ("BENS", "LOCACOES", "SERVICOS", "OBRAS")
def categoria_do_debito(debito, contrato) -> str | None   # contrato.categoria se houver, senão debito.categoria
async def registrar_na_fila(db, *, tenant_id, debito, data_liquidacao) -> PosicaoCronologica
    # cria a linha (situacao=REGISTRADA, exercicio=data_liquidacao.year,
    # marco_em=combine(data_liquidacao, now().time())); NÃO commita; idempotente:
    # se já existe posição do débito, devolve a existente sem alterar o marco
async def regravar_marco(db, *, tenant_id, debito, data_liquidacao_nova) -> PosicaoCronologica
    # atualiza marco_em/exercicio; caller registra histórico MARCO_REGRAVADO
```

- [ ] **Step 1: Testes RED**:

```python
async def test_liquidacao_registra_na_fila(...):
    # débito COM contrato (categoria SERVICOS): confirmar_liquidacao →
    # posicao criada (situacao REGISTRADA, exercicio=ano, categoria do contrato,
    # marco_em.date()==data_liquidacao) e debito.situacao_fila == REGISTRADA
async def test_liquidacao_sem_contrato_usa_categoria_do_debito(...):
async def test_liquidacao_sem_contrato_e_sem_categoria_e_422(...):
async def test_liquidar_duas_vezes_nao_regrava_marco(...):
    # 2ª confirmação (ou re-liquidação) mantém marco_em original
async def test_edicao_material_de_data_liquidacao_regrava_marco(...):
    # débito liquidado + em AJUSTE_*: atualizar_debito mudando data_liquidacao →
    # marco novo + histórico acao='MARCO_REGRAVADO' (usa o fluxo F2 real)
async def test_cancelar_debito_na_fila_vira_retirada(...):
    # cancelar → situacao_fila RETIRADA e posicao.situacao RETIRADA
```

- [ ] **Step 2: Implementar.** `confirmar_liquidacao` passa a: resolver categoria (422 se None), chamar `registrar_na_fila`, e trocar o `db.add(DebitoHistorico(...))` manual por `_registrar_transicao(..., fila=est.REGISTRADA, acao="LIQUIDADO")` **mantendo** as validações de status atuais (conferir que `transicao_permitida` aceita — a fila `NAO_REGISTRADA→REGISTRADA` pode exigir aresta nova no grafo de fila, se houver grafo de fila; se não houver, o parâmetro `fila` é aplicado direto). `atualizar_debito`: quando a edição material inclui `data_liquidacao` e o débito tem posição → `regravar_marco` + histórico. `cancelar`: se tem posição → `fila=est.RETIRADA` + espelho.
- [ ] **Step 3:** `pytest tests/test_pagamentos_f3_fila.py tests/test_pagamentos_f2_ajustes.py tests/test_guarda_status_legado.py -q`
- [ ] **Step 4: Commit** `feat(pagamentos): liquidação registra o marco na fila cronológica (F3)`

---

### Task 3: Consulta da fila — posição por window function

**Files:**
- Modify: `backend/app/services/pagamentos_cronologia.py`, `backend/app/routers/pagamentos_debitos.py`, `backend/app/schemas/pagamentos.py`
- Test: `backend/tests/test_pagamentos_f3_fila.py`

**Interfaces:**
- Produces (T5 e T6 dependem):

```python
async def listar_fila(db, *, tenant_id, id_fonte=None, id_unidade=None, categoria=None,
                      exercicio=None) -> list[FilaCronologicaGrupo]
    # grupos pela chave; itens ordenados por row_number() over
    # (partition by chave order by marco_em, id); cada item: posicao, id_debito,
    # numero (id), fornecedor_nome, descricao, valor_total, marco_em, situacao,
    # motivo_bloqueio, previsao_pagamento, tem_excecao: bool
async def posicao_do_debito(db, *, tenant_id, debito_id) -> PosicaoDebitoOut | None
    # posição no grupo + total do grupo + situacao + exceções do débito
```

Endpoints (rota literal `fila-cronologica` ANTES de qualquer paramétrica irmã em `operacoes_router`):
- `GET /pagamentos/fila-cronologica` → `list[FilaCronologicaGrupo]`, `require_any_permission(*PERMS_LEITURA)` (Ruling 9), filtros por query.
- `GET /pagamentos/debitos/{debito_id}/fila` → `PosicaoDebitoOut` (404 se não registrado), `PERMS_LEITURA`.

- [ ] **Step 1: Testes RED** — 3 débitos liquidados na MESMA chave em ordem embaralhada de criação → posições 1/2/3 por `marco_em`; débito de OUTRA fonte não entra no grupo; `posicao_do_debito` devolve `posicao=2, total=3`; HTTP usuário comum 200; débito não registrado → 404; **posição recalculada**: liquidar um 4º débito com data ANTERIOR aos demais → ele vira posição 1 sem nenhum UPDATE de posição (prova que não é armazenada).
- [ ] **Step 2: Implementar** (SQLAlchemy `func.row_number().over(partition_by=..., order_by=(PosicaoCronologica.marco_em, PosicaoCronologica.id))`; join com Debito+Fornecedor; excluir situação `RETIRADA` e `CONCLUIDA` da listagem default, com query-param `incluir_concluidas=true` para auditoria).
- [ ] **Step 3:** `pytest tests/test_pagamentos_f3_fila.py tests/test_guarda_ordem_rotas.py tests/test_guarda_modularizacao.py -q`
- [ ] **Step 4: Commit** `feat(pagamentos): fila cronológica com posição por window function (F3)`

---

### Task 4: Elegibilidade — função pura + reavaliação síncrona

**Files:**
- Modify: `backend/app/services/pagamentos_cronologia.py`; hooks em `pagamentos_debitos.py` (`autoridade_aprovar` fica em `pagamentos_debitos.py` — conferir; ajuste/reenvio), `pagamentos_autorizacao.py` (autorizar/estornar/pagar), `pagamentos_cadastros.py` (fornecedor, bloqueios)
- Test: `backend/tests/test_pagamentos_f3_elegibilidade.py`

**Interfaces:**
- Consumes: `saldo_conta` (`pagamentos_caixa.py:83`, devolve `.disponivel`); `pedidos ABERTO` de `pagamentos_ajustes.py`; `fornecedor.situacao_cadastral`; `BloqueioSaldo.ativo` + período vigente.
- Produces (T5 depende):

```python
def avaliar_elegibilidade(*, tramitacao: str, tem_pedido_aberto: bool,
                          fornecedor_regular: bool, disponivel_ok: bool,
                          tem_bloqueio: bool, tem_excecao: bool) -> tuple[str, str | None]
    # PURA (sem IO). Ordem: tramitacao != AUTORIZADA -> (REGISTRADA, None);
    # tem_bloqueio -> (BLOQUEADA, motivo); tem_pedido_aberto -> (BLOQUEADA, ...);
    # not fornecedor_regular -> (BLOQUEADA, ...); not disponivel_ok ->
    # (AGUARDANDO_DISPONIBILIDADE, ...); tem_excecao -> (EXCECAO_AUTORIZADA, None);
    # senão (ELEGIVEL, None)
async def reavaliar_debito(db, *, tenant_id, debito_id, usuario_id=None) -> None
    # carrega os fatos, chama a pura, e SE mudou aplica via _registrar_transicao
    # (fila=novo, acao='FILA_REAVALIADA') + espelha posicao.situacao/motivo_bloqueio.
    # Débito sem posição ou CONCLUIDA/RETIRADA: no-op.
async def reavaliar_por_fornecedor(db, *, tenant_id, fornecedor_id) -> int   # nº reavaliados
async def reavaliar_por_conta(db, *, tenant_id, conta_id) -> int
```

- [ ] **Step 1: Testes RED da função pura** (tabela — todos os ramos, incl. precedências: bloqueio vence pedido, exceção só vale quando as demais condições passam? NÃO — spec: exceção é para furar ORDEM, não elegibilidade; `tem_excecao` só troca o rótulo quando o débito estaria ELEGIVEL. Testar exatamente isso).
- [ ] **Step 2: Testes RED dos hooks** (integração, fluxo real):

```python
async def test_autorizacao_torna_elegivel(...)             # AUTORIZADA + tudo ok → ELEGIVEL
async def test_fornecedor_irregular_bloqueia_na_fila(...)  # atualizar_fornecedor IRREGULAR → BLOQUEADA; voltar REGULAR → ELEGIVEL
async def test_bloqueio_de_saldo_bloqueia_debitos_da_conta(...)
async def test_sem_disponivel_aguarda_disponibilidade(...) # bloqueio consumindo o disponível
async def test_pedido_de_ajuste_pos_autorizacao_bloqueia(...)  # se o rito permitir; senão documentar que pedido aberto ⇒ tramitacao != AUTORIZADA e o ramo é o da função pura
async def test_pagamento_integral_conclui(...)             # já existia; agora espelha posicao
```

- [ ] **Step 3: Implementar** — hooks chamam `reavaliar_debito`/`reavaliar_por_*` DEPOIS da mutação, ANTES do commit (mesma transação, atomicidade).
- [ ] **Step 4:** `pytest tests/test_pagamentos_f3_elegibilidade.py tests/test_pagamentos_autorizacao.py tests/test_pagamentos_liberacao.py tests/test_pagamentos_caixa.py tests/test_pagamentos_saldos_v2.py -q`
- [ ] **Step 5: Commit** `feat(pagamentos): elegibilidade da fila avaliada em toda mutação relevante (F3)`

---

### Task 5: 409 ao preterir + exceção cronológica

**Files:**
- Modify: `backend/app/services/pagamentos_cronologia.py`, `backend/app/services/pagamentos_autorizacao.py` (liberar em `POST /parcelas/liberar` e `pagar_parcela:356-391`), `backend/app/routers/pagamentos_debitos.py`, schemas
- Test: `backend/tests/test_pagamentos_f3_pretericao.py`

**Interfaces:**

```python
async def preteridos(db, *, tenant_id, debito_id) -> list[PosicaoFilaItem]
    # débitos ELEGIVEL da MESMA chave com (marco_em, id) menor (Ruling 5)
async def assert_ordem_respeitada(db, *, tenant_id, debito_id) -> None
    # no-op se débito EXCECAO_AUTORIZADA ou sem posição (débito legado sem fila —
    # fail-open deliberado, registrar no docstring: fila só governa quem está nela);
    # senão levanta OrdemCronologicaError(409) com a lista dos preteridos no detail
async def registrar_excecao(db, *, tenant_id, debito_id, usuario_id, justificativa,
                            fundamento, data_autorizacao, documentos=None) -> ExcecaoCronologica
```

Endpoint: `POST /pagamentos/debitos/{debito_id}/excecao-cronologica` (`require_permission("pagamento_autorizar")`, Ruling 8) → cria a exceção + `_registrar_transicao(fila=EXCECAO_AUTORIZADA, acao='EXCECAO_AUTORIZADA')` + espelho + `audit.log("excecao_cronologica.autorizada")`. `GET .../excecao-cronologica` → `list[ExcecaoCronologicaOut]` (`PERMS_LEITURA`).

- [ ] **Step 1: Testes RED**:

```python
async def test_pagar_fora_de_ordem_e_409_com_preteridos(...)   # 2 elegíveis; pagar o 2º → 409 listando o 1º
async def test_liberar_fora_de_ordem_e_409(...)
async def test_pagar_o_primeiro_da_fila_passa(...)
async def test_bloqueado_a_frente_nao_impede(...)              # 1º BLOQUEADA, 2º ELEGIVEL → pagar 2º passa
async def test_excecao_destrava_e_fica_visivel(...)            # HTTP: registrar exceção (pagamento_autorizar) → EXCECAO_AUTORIZADA → pagar passa; justificativa aparece no GET
async def test_excecao_sem_fundamento_e_422(...)
async def test_excecao_por_usuario_sem_pagamento_autorizar_e_403(...)  # usuário comum com outra perm
async def test_filas_diferentes_nao_se_preterem(...)           # fontes distintas
```

- [ ] **Step 2: Implementar** (guarda chamada no início de liberar/pagar, ANTES de qualquer escrita — atomicidade F2-style).
- [ ] **Step 3:** `pytest tests/test_pagamentos_f3_pretericao.py tests/test_pagamentos_autorizacao.py tests/test_pagamentos_liberacao.py tests/test_pagamentos_concorrencia.py tests/test_guarda_ordem_rotas.py -q`
- [ ] **Step 4: Commit** `feat(pagamentos): 409 ao preterir e exceção cronológica formal (F3)`

---

### Task 6: Frontend — tela da fila, seção no detalhe, categoria de contrato

**Files:**
- Create: `frontend/app/(app)/m/pagamentos/fila/page.tsx`
- Modify: `frontend/lib/api.ts`, `frontend/lib/menus/pagamentos.ts`, `frontend/components/pagamentos/DetalheDebitoContent.tsx`, tela de contratos (`app/(app)/m/pagamentos/cadastros/contratos/`), `frontend/__tests__/menus.test.tsx`
- Test: `frontend/__tests__/pagamentos-f3.test.tsx`

**Interfaces:** consome os endpoints das Tasks 3 e 5 — declarar `FilaCronologicaGrupo`, `PosicaoFilaItem`, `PosicaoDebitoOut`, `ExcecaoCronologicaOut` em `api.ts` campo a campo contra os schemas reais; métodos `filaCronologica(filtros?)`, `posicaoDebito(id)`, `listarExcecoes(id)`, `registrarExcecao(id, payload)`.

- [ ] **Step 1: `api.ts`** + tipos.
- [ ] **Step 2: Tela `/m/pagamentos/fila`** (§7.5): grupos por chave (título "Unidade · Fonte · Categoria · Exercício"), colunas posição/marco/fornecedor/documento/valor/situação (ícone+TEXTO, nunca só cor); exceção autorizada marcada com ícone **e** texto + justificativa em painel/expansão; filtros por fonte/unidade/categoria/exercício. Item de menu **"Ordem cronológica"** em `lib/menus/pagamentos.ts` (leitura: mesmas perms dos itens de leitura — entrar na tabela `PERMISSOES_ESPERADAS` de `__tests__/menus.test.tsx`).
- [ ] **Step 3: Seção "Fila" no `DetalheDebitoContent.tsx`** (novo `SectionCard` após "Parcelas"): posição N de M, marco, situação com motivo, exceções listadas; botão "Autorizar exceção cronológica" (dialog com justificativa+fundamento+data, só para quem `can("pagamento_autorizar")`); 409 de liberar/pagar nas telas existentes mostra a lista de preteridos legível (mensagem do backend).
- [ ] **Step 4: Contratos**: coluna+campo `categoria` (select das 4, rótulos pt), obrigatória ao criar; banner na listagem quando houver contrato sem categoria (defensivo — pós-backfill deve ser zero).
- [ ] **Step 5: vitest** (`pagamentos-f3.test.tsx`): fila renderiza grupos e posições; exceção aparece com texto; seção Fila mostra posição e bloqueio com motivo. `cd frontend && npx tsc --noEmit && npx vitest run __tests__/pagamentos-f3.test.tsx __tests__/menus.test.tsx`.
- [ ] **Step 6: Commit** `feat(pagamentos): tela da ordem cronológica e seção Fila no detalhe (F3)`

---

### Task 7: Docs e fechamento (controlador, inline)

- [ ] Bloco F3 no `docs/BACKLOG-PENDENCIAS.md` §2.1 (entregue + pendências datadas).
- [ ] Suítes completas solo (backend inteira, frontend inteira, tsc) antes do review final da branch.

## Aceite da fatia (spec §9-F3)

- Posição correta e auditável ✔ (T2+T3: window function, marco imutável, regravação material auditada)
- Preterir sem exceção é bloqueado ✔ (T5: 409 em liberar E pagar, com lista)
- Exceção exige os cinco campos ✔ (T5: justificativa, fundamento, autoridade, data, documentos opcionais — 422 sem os obrigatórios)
