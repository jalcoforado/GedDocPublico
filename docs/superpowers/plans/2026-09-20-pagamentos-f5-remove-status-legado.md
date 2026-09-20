# Pagamentos F5 (parcial) — Remoção do `status` legado — Plano de Implementação

> Escopo autorizado por Jorge em 2026-09-20: **só a remoção do `status` legado**. O resto de F5
> (visão geral com indicadores clicáveis, caixa de trabalho refinada, sweep de estados vazios/
> erro/a11y/responsividade, "os 23 cenários do §17 do pedido") fica de fora — o documento original
> de 20 seções que a spec resume não está neste repositório, então não dá para verificar contra ele.

**Goal:** Apagar `pagamentos.debito.status` (a coluna legada de 16 valores, derivada desde a F1) e
tudo que a mantém — `_sincronizar_status_legado`, o índice, o CHECK, a guarda que só protegia
escrita — migrando cada consumidor real para as três dimensões (`situacao_tramitacao`,
`situacao_fila`, `situacao_pagamento`).

**Por que agora, e não achado de carona**: a spec (§4.2) registra o risco explicitamente —
"coluna derivada mantida por código é uma fonte de divergência" — e a F1 já a nomeou como dívida
deliberada, não descuido. `pagamentos_debitos.py:768-788` já mostra por que vale a pena: o
mapeamento reverso (`status` → três dimensões) feito pela migration 0085 nunca é reaplicado no
sentido inverso, então um débito nascido antes da F1 e nunca mais tocado carregaria um `status`
legado (`VALIDADO`/`AGUARDANDO_AUTORIZACAO`) que `AUTORIZAVEIS` não reconhece — um bug latente que
some ao trocar o filtro para `situacao_tramitacao`.

**Levantamento factual prévio** (Explore, 2026-09-20; ver seção "Consumidores" abaixo para o mapa
completo arquivo:linha): 8 arquivos de serviço leem `Debito.status` de verdade (não contando os que
só fazem `d.status`/`d.status` de outro objeto tipo `Parcela.status`); 2 arquivos de teste inteiros
(`test_pagamentos_status_derivado.py`, `test_pagamentos_migration_0085.py`, 124 linhas juntas) só
existem para proteger o contrato que está sendo removido; ~8 arquivos de teste têm ~50+ asserções
sobre o valor de `status`; o frontend usa `status` de débito em **um único lugar de UI real**
(`dashboard/page.tsx`, badge de "maiores débitos em aberto") — o resto (`statusDebito.ts`) é código
morto (`DEBITO_STATUS_TABS` não é importado em lugar nenhum) ou já migrado (`situacoes.ts`,
`statusFluxo.ts`, `EtapasFluxo.tsx`, `RitoPagamento.tsx`, `SituacoesDebito.tsx`,
`DetalheDebitoContent.tsx`, as 5 telas de `solicitacoes/`). Medição no banco de dev (2026-09-20):
14 débitos, todos com `status` dentro do conjunto que `_sincronizar_status_legado` ainda produz —
nenhum débito "morto" pré-F1 para se preocupar neste ambiente, mas a lógica muda para as três
dimensões de qualquer forma (é estritamente mais correta, não só equivalente).

**Fora deste branch, de propósito**: `pagamentos_lotes.py` (F4, PR #68, ainda não mesclado em
`main` quando este branch nasceu) tem duas linhas informativas (`status_anterior=debito.status,
status_novo=debito.status` em inserts diretos de `DebitoHistorico`) que também precisam migrar.
Como as duas fatias evoluem em paralelo sem depender uma da outra, a Task 9 deste plano cobre esse
ajuste como um PR pequeno e separado, DEPOIS que #68 mesclar — não dá para tocar um arquivo que não
existe em `main` ainda.

**Tech Stack:** FastAPI + SQLAlchemy 2 async + Alembic, Next.js 15, pytest via
`docker exec -e PYTEST_DB_HOST=db aprimora-py-backend`, vitest no host.

**Spec:** `docs/superpowers/specs/2026-08-06-pagamentos-fluxo-design.md` §4.1 (três dimensões),
§4.2 (a coluna legada — "morre na F5"), §4.5 (mapeamento status↔três dimensões, autoridade para
toda tradução deste plano).

---

## Global Constraints

- Idioma pt-BR; commits terminam com `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- **Nada de nova função de tradução "status → três dimensões" pela metade.** A tradução correta é
  ler §4.5 de trás para frente: cada `ST_*`/tupla vira uma condição sobre `situacao_tramitacao`/
  `situacao_fila`/`situacao_pagamento` (ruling por constante, seção abaixo) — não adivinhar.
- Migration nova, `down_revision` = head atual no momento do PR (confirmar com `alembic heads`
  antes de escrever — outros PRs podem ter avançado a cadeia). Ordem obrigatória dentro dela:
  `DROP INDEX ix_debito_tenant_status` → `DROP CONSTRAINT ck_debito_status` → `DROP COLUMN status`.
  `downgrade()` recria a coluna **nullable, sem backfill** (não há como reconstruir com fidelidade
  o valor exato que existia — mesma postura da 0107 para dado impossível de reverter com certeza) e
  documenta isso no docstring.
- Testes por task: no mínimo o arquivo de teste do próprio serviço tocado +
  `pytest tests/test_guarda_modularizacao.py tests/test_guarda_status_legado.py -q` (até a Task
  9 remover essa guarda) + `tests/test_rls_papeis_minimos.py` depois da migration. FOREGROUND
  sempre; nunca duas suítes simultâneas.
- **Não silenciar teste que já falha por outro motivo** — se um teste pré-existente cair ao migrar
  seu arquivo, ler a causa antes de assumir que é só o `status` sumindo.
- Ordem das tasks importa: os consumidores (services/routers/frontend) migram ANTES da migration
  que apaga a coluna — a coluna só pode sumir depois que nada mais lê `Debito.status` em runtime.

## Rulings de tradução (vinculantes — §4.5 é a fonte)

Cada constante/gate atual e sua tradução exata para as três dimensões:

1. **`ST_RASCUNHO`/`EDITAVEIS = (RASCUNHO, DEVOLVIDO)`** → `situacao_tramitacao in (RASCUNHO,
   AJUSTE_GESTOR, AJUSTE_VALIDACAO, AJUSTE_AUTORIDADE)`. `DEVOLVIDO` colapsava três estados novos
   (F2) num só — a tradução correta é a UNIÃO dos três, não escolher um.
2. **`AUTORIZAVEIS = (ST_ENVIADO_SECRETARIO, ST_AGUARDANDO_AUTORIZACAO)`** →
   `situacao_tramitacao == AGUARDANDO_AUTORIDADE`. `ST_AGUARDANDO_AUTORIZACAO` é legado pré-F1 morto
   (nenhum código o produz desde `_sincronizar_status_legado`); a tradução por dimensão automaticamente
   alcança esses débitos também — é o bug latente citado no Goal, corrigido de graça.
3. **`EM_TESOURARIA = (ST_ENVIADO_TESOURARIA, ST_EM_PROCESSAMENTO, ST_PAGO_PARCIAL)`** →
   `situacao_pagamento in (PROGRAMADA, ENVIADA_BANCO, EM_PROCESSAMENTO, PAGA_PARCIAL, FALHOU)`.
   `FALHOU` entra porque §4.5 não previa a F4 (que introduziu esse valor) — um débito com pagamento
   `FALHOU` ainda está "na tesouraria" no sentido operacional (precisa de um lote novo), mesmo sem
   entrada na tabela de mapeamento original. Ponto de julgamento registrado aqui de propósito.
4. **`COM_RESERVA = (ST_AUTORIZADO, *EM_TESOURARIA, ST_ESTORNADO)`** →
   `situacao_tramitacao == AUTORIZADA and situacao_pagamento != NAO_INICIADA` **OU**
   `situacao_pagamento in (..., ESTORNADA)`. Mais simples: `situacao_tramitacao == AUTORIZADA and
   situacao_fila == ELEGIVEL` cobre TODOS os casos de `COM_RESERVA` pela própria tabela §4.5 (toda
   linha de `AUTORIZADO` até `ESTORNADO` tem `situacao_fila = ELEGIVEL` OU `CONCLUIDA` — checar:
   `PAGO`/`CONCILIADO` têm fila `CONCLUIDA`, não `ELEGIVEL`!). Tradução correta:
   `situacao_tramitacao == AUTORIZADA and situacao_fila in (ELEGIVEL, CONCLUIDA)`.
5. **`d.status != ST_PAGO`** (conciliação, gate de estorno) → `d.situacao_pagamento != PAGA`.
6. **`d.status not in (RASCUNHO, REJEITADO, CANCELADO)`** (`excluir_debito`) →
   `d.situacao_tramitacao not in (RASCUNHO, REJEITADA_GESTOR, INDEFERIDA_AUTORIDADE, CANCELADA)`.
   `REJEITADO` no legado cobria TANTO rejeição do gestor QUANTO indeferimento da autoridade (F1
   separou os dois) — de novo, união dos dois estados novos.
7. **`Debito.status.notin_(("REJEITADO", "CANCELADO"))`** (`detectar_duplicidade`) →
   `situacao_tramitacao.notin_((REJEITADA_GESTOR, INDEFERIDA_AUTORIDADE, CANCELADA))`.
8. **`STATUS_EM_ANDAMENTO`** (`pagamentos_excecoes.py`, 8 valores) → leitura própria na Task 5
   (arquivo pequeno, tradução direta valor a valor pela tabela §4.5 — sem ruling extra aqui, ver
   o arquivo ao chegar na task).
9. **`_STATUS_COMPROMETIDO`/`_STATUS_MAIORES`** (`pagamentos_dashboard.py`) → mesma tradução do
   ruling 4 (`COM_RESERVA`) para o primeiro; o segundo é só um `ORDER BY valor_total` sem filtro de
   status — conferir ao chegar na Task 6, pode não precisar de tradução nenhuma.
10. **`status_f` (parâmetro público em `GET /pagamentos/debitos` e `exportar.csv`)** — **removido**,
    não substituído por um equivalente de três dimensões. Levantamento confirma zero chamador no
    frontend (`api.ts` expõe o parâmetro mas nenhuma tela o usa) — é código morto de API. O router
    já aceita `situacao_tramitacao` como filtro alternativo (linha 119) desde antes deste plano;
    quem precisar filtrar por execução ganha um novo `situacao_pagamento` opcional na mesma rota
    (Task 2), não um `status_f` renomeado.
11. **`DebitoHistorico.status_anterior`/`status_novo`** (`NOT NULL` hoje) — **preservados**, mas a
    fonte do valor deixa de ser `Debito.status` (que vai sumir) e passa a ser `status_legado()`
    **chamada inline**, não armazenada em lugar nenhum além do histórico em si. A função pura
    `status_legado(tramitacao, fila, pagamento)` de `pagamentos_estados.py` **sobrevive** — só
    `_sincronizar_status_legado` (a versão que ESCREVE em `Debito.status`) morre. Isso preserva 100%
    da trilha de auditoria existente e futura sem manter a coluna. `_registrar_transicao` troca
    `status_anterior = debito.status` por `status_anterior = est.status_legado(debito.situacao_tramitacao,
    debito.situacao_fila, debito.situacao_pagamento)` calculado ANTES de aplicar a transição, e
    o mesmo depois para `status_novo`. Os 3 inserts diretos de `DebitoHistorico` fora de
    `_registrar_transicao` (`atualizar_debito`, `responder_ajuste`, e — fora deste branch —
    `pagamentos_lotes.py`) fazem o mesmo cálculo inline.

---

## Estrutura de arquivos

| Arquivo | Papel |
|---|---|
| `backend/app/services/pagamentos_debitos.py` | Modify: `_registrar_transicao` (ruling 11), remove `_sincronizar_status_legado`, `detectar_duplicidade` (ruling 7), `listar_debitos` (remove `status_f`, ruling 10), `excluir_debito` (ruling 6), `debito_out` (remove chave `status`), constantes `ST_*`/`EDITAVEIS`/`AUTORIZAVEIS`/`EM_TESOURARIA`/`COM_RESERVA` → viram funções/predicados sobre as três dimensões |
| `backend/app/services/pagamentos_estados.py` | Modify: mantém `status_legado()` pura; docstring atualizado (não é mais "sobrevive até a F5" — sobrevive PERMANENTEMENTE como cálculo do histórico) |
| `backend/app/services/pagamentos_autorizacao.py` | Modify: ~22 ocorrências, rulings 2-4 |
| `backend/app/services/pagamentos_filas.py` | Modify: rulings 2, 3 |
| `backend/app/services/pagamentos_excecoes.py` | Modify: ruling 8 |
| `backend/app/services/pagamentos_conciliacao.py` | Modify: ruling 5 |
| `backend/app/services/pagamentos_export.py` | Modify: remove coluna `status` do CSV (ruling: usar `status_legado()` calculado, para não quebrar o formato do arquivo que auditores externos já recebem — ver Task 6) |
| `backend/app/services/pagamentos_dashboard.py` | Modify: ruling 9; `DebitoResumoItem.status` calculado via `status_legado()`, não lido de `d.status` |
| `backend/app/routers/pagamentos_debitos.py` | Modify: remove `status_f` de `list_debitos`/`exportar_debitos_csv`; `minha_fila` troca `status_f=st` por filtro de dimensão |
| `backend/app/schemas/pagamentos.py` | Modify: `DebitoOut.status` removido; `DebitoHistoricoOut.status_anterior/novo` viram `str \| None`/`str` sem o `StatusDebito` Literal (valor histórico livre, não mais validado contra enum ativo); `StatusDebito` Literal removido se nada mais o referenciar |
| `backend/app/models/pagamentos.py` | Modify: remove `status` de `Debito` |
| `backend/alembic/versions/0122_pagamentos_remove_status_legado.py` | Create: DROP INDEX/CONSTRAINT/COLUMN |
| `backend/tests/test_guarda_status_legado.py` | Delete (guarda protegia escrita numa coluna que não existe mais) |
| `backend/tests/test_pagamentos_status_derivado.py` | Delete (testa `_sincronizar_status_legado`, que não existe mais) |
| `backend/tests/test_pagamentos_migration_0085.py` | Delete (testa o contrato `status_legado()`/`MAPA_BACKFILL` da migration original — a migration em si NÃO muda, é histórica; só o teste que a amarra ao `status` atual perde sentido) |
| `backend/tests/test_pagamentos_autorizacao.py`, `test_pagamentos_f3_pretericao.py`, `test_pagamentos_liberacao.py`, `test_pagamentos_debitos.py`, `test_pagamentos_dashboard.py`, `test_pagamentos_conciliacao_v2.py`, `test_pagamentos_validacoes_v2.py` | Modify: troca `assert d.status == "X"` por asserções nas três dimensões, arquivo por arquivo, na mesma task que migra o serviço correspondente |
| `frontend/lib/api.ts` | Modify: remove `status`/`StatusDebito` de `Debito`/`DebitoOut`/`DebitoResumoItem`; remove `status` de `debitos.list()` params |
| `frontend/components/pagamentos/statusDebito.ts` | Delete (código morto confirmado — `DEBITO_STATUS_TABS` sem importador; `DEBITO_STATUS_BADGE` só usado pelo dashboard, que migra para `situacoes.ts` na Task 7) |
| `frontend/app/(app)/m/pagamentos/dashboard/page.tsx` | Modify: badge de "maiores débitos" usa `situacao_tramitacao`/`situacao_pagamento` + `situacoes.ts` em vez de `StatusDebito` |
| `frontend/__tests__/pagamentos-f2.test.tsx`, `pagamentos-f3.test.tsx`, `pagamentos-f4.test.tsx` | Modify: remove `status: "..."` dos fixtures (erro de compilação TS, não teste vermelho) |

---

### Task 1: `pagamentos_debitos.py` — o módulo dono da coluna

**Files:** `backend/app/services/pagamentos_debitos.py`, `backend/tests/test_pagamentos_debitos.py`

- [ ] **Step 1**: `_registrar_transicao` — aplica ruling 11 (histórico calculado inline, não lido de
  `debito.status`). Remove `_sincronizar_status_legado` (a função que ESCREVE); `est.status_legado`
  continua importada e usada só para o cálculo do histórico.
- [ ] **Step 2**: `detectar_duplicidade` (ruling 7), `excluir_debito` (ruling 6), `listar_debitos`
  (remove `status_f`, ruling 10), `debito_out` (remove a chave `"status"` do dict retornado).
- [ ] **Step 3**: `ST_*`/`EDITAVEIS`/`AUTORIZAVEIS`/`EM_TESOURARIA`/`COM_RESERVA` — substituídas por
  funções puras `esta_editavel(d) -> bool`, `esta_autorizavel(d) -> bool`, `esta_em_tesouraria(d) ->
  bool`, `tem_reserva(d) -> bool` (rulings 1-4), preservando os NOMES importados por outros módulos
  como aliases de função em vez de tupla, para o diff dos consumidores ficar em trocar `x in
  TUPLA` por `funcao(x)` — mecânico, não redesenho por arquivo.
- [ ] **Step 4**: Testes — `test_pagamentos_debitos.py` troca as asserções de `status` restantes;
  novo teste `test_historico_preserva_status_legado_sem_coluna` prova que
  `DebitoHistorico.status_anterior/novo` continuam corretos (comparar contra `status_legado()`
  chamado no teste) mesmo sem `Debito.status` existir mais no objeto.
- [ ] **Step 5**: `pytest tests/test_pagamentos_debitos.py tests/test_guarda_modularizacao.py -q`
- [ ] **Step 6**: Commit `refactor(pagamentos): status legado sai de pagamentos_debitos.py — histórico calculado, não armazenado (F5)`

### Task 2: `routers/pagamentos_debitos.py`

**Files:** `backend/app/routers/pagamentos_debitos.py`

- [ ] Remove `status_f` de `list_debitos`/`exportar_debitos_csv`; adiciona `situacao_pagamento:
  str | None` como filtro opcional (ruling 10) nas duas rotas, repassado a `listar_debitos`.
- [ ] `minha_fila`: troca o loop `for st in (svc.ST_AUTORIZADO, *svc.EM_TESOURARIA):
  status_f=st` por um filtro direto em `situacao_tramitacao`/`situacao_pagamento` (usar
  `svc.esta_autorizavel`/`svc.esta_em_tesouraria` como predicado client-side sobre o resultado de
  UMA query, não N queries por status — oportunidade de simplificar, não só traduzir).
- [ ] `pytest tests/test_pagamentos_debitos.py tests/test_pagamentos_f2_ajustes.py -q` (a segunda
  porque `minha_fila` é usada pela caixa de trabalho testada lá).
- [ ] Commit `refactor(pagamentos): router de débitos larga status_f — filtro por dimensão (F5)`

### Task 3: `pagamentos_autorizacao.py` (o maior — ~22 ocorrências)

**Files:** `backend/app/services/pagamentos_autorizacao.py`,
`backend/tests/test_pagamentos_autorizacao.py`, `backend/tests/test_pagamentos_f3_pretericao.py`,
`backend/tests/test_pagamentos_liberacao.py`

- [ ] Troca toda ocorrência pelos predicados da Task 1 Step 3 (`esta_autorizavel`,
  `esta_em_tesouraria`, `tem_reserva`) — mecânico, arquivo por arquivo dos rulings 2-4.
- [ ] `d.status == deb.ST_ENVIADO_TESOURARIA` (revogar_liberacao) → `d.situacao_pagamento ==
  est.PROGRAMADA` (é o único status que mapeia pra ENVIADO_TESOURARIA sozinho, §4.5).
- [ ] Testes: os 3 arquivos trocam `assert d.status == "X"` pelas três dimensões equivalentes —
  usar a tabela §4.5 linha a linha, não inventar equivalência.
- [ ] `pytest tests/test_pagamentos_autorizacao.py tests/test_pagamentos_f3_pretericao.py tests/test_pagamentos_liberacao.py -q`
- [ ] Commit `refactor(pagamentos): autorização/liberação/tesouraria migram para as três dimensões (F5)`

### Task 4: `pagamentos_filas.py`

**Files:** `backend/app/services/pagamentos_filas.py`

- [ ] `Debito.status.in_(AUTORIZAVEIS)` / `.in_((ST_AUTORIZADO, ST_ESTORNADO, *EM_TESOURARIA))` →
  filtros SQLAlchemy equivalentes sobre `situacao_tramitacao`/`situacao_pagamento` (não dá pra usar
  a função Python `esta_autorizavel` num `.where()` — precisa da forma SQL; escrever o `.where()`
  direto, comentando que espelha `esta_autorizavel`/`esta_em_tesouraria` para não divergir).
- [ ] `pytest tests/test_pagamentos_filas.py -q`
- [ ] Commit `refactor(pagamentos): filas de autorização/liberação migram para as três dimensões (F5)`

### Task 5: `pagamentos_excecoes.py`

**Files:** `backend/app/services/pagamentos_excecoes.py`

- [ ] `STATUS_EM_ANDAMENTO` (8 valores) → predicado sobre `situacao_tramitacao`/`situacao_pagamento`
  — ler os 8 valores atuais, traduzir cada um pela tabela §4.5, testar contra o teste existente do
  relatório de exceções antes de assumir a tradução certa.
- [ ] `pytest tests/test_pagamentos_excecoes_c12.py -q` (nome a confirmar — usar o teste que já
  cobre `relatorio_excecoes`)
- [ ] Commit `refactor(pagamentos): relatório de exceções migra para as três dimensões (F5)`

### Task 6: `pagamentos_conciliacao.py`, `pagamentos_export.py`, `pagamentos_dashboard.py`

**Files:** os três + `test_pagamentos_conciliacao_v2.py`, `test_pagamentos_dashboard.py`

- [ ] Conciliação: ruling 5 (`d.status != ST_PAGO` → `d.situacao_pagamento != est.PAGA`).
- [ ] Export CSV: coluna `"status"` do CSV continua existindo no ARQUIVO (auditores externos já
  recebem esse formato — quebrar a coluna é quebrar um contrato de terceiro, não só código interno)
  mas o VALOR passa a vir de `est.status_legado(d.situacao_tramitacao, d.situacao_fila,
  d.situacao_pagamento)` calculado na hora da exportação, não de `d.status`.
- [ ] Dashboard: `_STATUS_COMPROMETIDO`/`_STATUS_MAIORES` → `tem_reserva()` (ruling 9);
  `DebitoResumoItem.status` no schema continua existindo (é o que o frontend option 3 abaixo
  consome) mas populado via `est.status_legado(...)` no momento da query, não lido de `d.status`.
- [ ] `pytest tests/test_pagamentos_conciliacao_v2.py tests/test_pagamentos_dashboard.py tests/test_pagamentos_validacoes_v2.py -q`
- [ ] Commit `refactor(pagamentos): conciliação/export/dashboard migram para as três dimensões (F5)`

### Task 7: Schemas + migration + guarda + testes órfãos

**Files:** `backend/app/schemas/pagamentos.py`, `backend/app/models/pagamentos.py`,
`backend/alembic/versions/0122_*.py`, `backend/tests/test_guarda_status_legado.py` (delete),
`backend/tests/test_pagamentos_status_derivado.py` (delete),
`backend/tests/test_pagamentos_migration_0085.py` (delete)

- [ ] `DebitoOut.status` removido; `StatusDebito` Literal removido (conferir que nada mais o usa —
  `DebitoResumoItem.status` vira `str`, populado por `status_legado()`, não precisa do Literal
  fechado porque não é mais gravado/validado contra CHECK nenhum).
- [ ] `models/pagamentos.py`: remove `status: Mapped[str]` de `Debito`.
- [ ] Migration 0122: `alembic heads` primeiro para confirmar `down_revision` (não assumir 0121 —
  conferir se algo mesclou depois). `DROP INDEX ix_debito_tenant_status` → `DROP CONSTRAINT
  ck_debito_status` → `DROP COLUMN status`. `downgrade()`: recria a coluna nullable, sem backfill,
  docstring explicando por quê (mesmo padrão da 0107 para dado que não dá pra reconstruir).
- [ ] `docker exec aprimora-py-backend alembic upgrade head` / `downgrade -1` / `upgrade head`.
- [ ] Deleta os 3 arquivos de teste órfãos.
- [ ] `pytest tests/test_rls_papeis_minimos.py tests/test_pagamentos_estados.py -q` (o segundo
  ainda testa `status_legado()` como função pura — sobrevive, só perde os testes de
  `_sincronizar_status_legado` se houver algum lá; conferir ao chegar).
- [ ] Commit `feat(pagamentos): migration 0122 — remove a coluna status legada (F5)`

### Task 8: Frontend

**Files:** `frontend/lib/api.ts`, `frontend/components/pagamentos/statusDebito.ts` (delete),
`frontend/app/(app)/m/pagamentos/dashboard/page.tsx`,
`frontend/__tests__/pagamentos-f2.test.tsx`, `pagamentos-f3.test.tsx`, `pagamentos-f4.test.tsx`

- [ ] `api.ts`: remove `status`/`StatusDebito` de `Debito`/`DebitoOut`; `DebitoResumoItem.status`
  vira `string` simples (ainda existe no payload, calculado no backend). Remove `status` dos
  params de `debitos.list()`.
- [ ] `dashboard/page.tsx`: troca `DEBITO_STATUS_BADGE[deb.status]` por um rótulo/cor derivado de
  `situacao_tramitacao`/`situacao_pagamento` via `situacoes.ts` (reaproveitar
  `TRAMITACAO_ROTULO`/`TRANSACAO_PAGAMENTOS_ROTULO` já existentes, não inventar rótulo novo) — mas
  `DebitoResumoItem` não tem essas duas colunas no schema atual (`schemas/pagamentos.py` — conferir
  ao chegar na task; se não tiver, é um campo a acrescentar em `DebitoResumoItem` na Task 6, senão
  esta task fica sem dado pra trabalhar).
- [ ] Deleta `statusDebito.ts` (confirmar de novo, no momento da task, que nada passou a importar
  `DEBITO_STATUS_TABS` nas tasks anteriores).
- [ ] `frontend/__tests__/pagamentos-f2/f3/f4.test.tsx`: remove `status: "..."` dos fixtures — é
  erro de compilação TS, não teste vermelho (confirmado no levantamento).
- [ ] `npx tsc --noEmit` limpo; `npx vitest run` sem regressão; teste manual não é possível nesta
  sessão (sem ferramenta de browser) — registrar isso no PR como já feito em F4.
- [ ] Commit `refactor(pagamentos): frontend larga status legado — dashboard usa três dimensões (F5)`

### Task 9 (fora deste branch — PR separado, depois que #68 mesclar): `pagamentos_lotes.py`

Não faz parte deste PR (o arquivo não existe em `main` ainda). Depois que a F4 mesclar: trocar as
duas linhas `status_anterior=debito.status, status_novo=debito.status` em
`_registrar_evento_lote` por `est.status_legado(debito.situacao_tramitacao, debito.situacao_fila,
debito.situacao_pagamento)`, mesmo padrão do ruling 11. PR de 1 arquivo, trivial — não precisa de
plano próprio, só not-forget.

### Task 10: Suíte completa + fechamento

- [ ] `pytest -q` sem filtro — comparar contra a baseline conhecida desta sessão (1727 passed / 45
  skipped / 3 failed pré-existentes de `test_guarda_links_docs.py`, não relacionadas). Qualquer
  novo vermelho fora desses 3 é bug desta fatia, não pré-existente.
- [ ] Atualiza `docs/BACKLOG-PENDENCIAS.md`: item de F5 fecha (só a parte de remoção do status); a
  parte de UI/a11y/23 cenários continua registrada como não feita, com a mesma nota sobre o
  documento original ausente.
- [ ] Commit de fechamento.

---

## Aceite da fatia

- [ ] `SELECT status FROM pagamentos.debito` falha (coluna não existe).
- [ ] Nenhum arquivo de serviço/router/schema/model cita `Debito.status`, `ST_*`, `StatusDebito`
  (grep de confirmação antes do PR).
- [ ] `debito_historico.status_anterior/novo` continuam `NOT NULL` e corretos em toda transição
  nova, calculados sem depender de coluna nenhuma.
- [ ] `GET /pagamentos/debitos/exportar.csv` continua com a coluna `status` no arquivo (contrato
  externo preservado), valor calculado.
- [ ] Suíte completa verde nos dois papéis de banco, nas mesmas condições da F4.
