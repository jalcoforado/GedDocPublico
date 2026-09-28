# Pagamentos F4 — Tesouraria — Plano de Implementação

> **For agentic workers:** implementar task a task, na ordem. Cada task termina com suíte verde e
> commit próprio antes da seguinte. Checkbox (`- [ ]`) por passo.

**Goal:** Dar à tesouraria o rito de execução em lote que falta desde a F1: lote bancário real
(`lote_pagamento`), retenções compondo o líquido (`retencao`), e as transições que
`situacao_pagamento` já promete no vocabulário mas nenhum código atribui hoje
(`PROGRAMADA→ENVIADA_BANCO→...→PAGA` ou `FALHOU`+reprocesso).

**Architecture:** Duas tabelas novas de execução (`lote_pagamento`, `lote_pagamento_parcela`) mais
`retencao` (1:N com débito). O lote nasce `RASCUNHO` a partir de parcelas `LIBERADA` selecionadas
pela tesouraria, evolui `PROGRAMADO→ENVIADO→PROCESSADO`; o retorno do banco é registrado parcela a
parcela dentro do lote (`PAGA`/`FALHOU`), e uma falha devolve a `Parcela.status` a `LIBERADA` para
reentrar num lote seguinte — nunca cancela o débito. `retencao.valor_liquido` do débito continua
**derivado**, nunca armazenado (mesmo padrão da F3 para posição de fila). Nenhuma transação nova:
tudo sob `pagamento_pagar`, que já é "Tesouraria" na tabela de perfis da spec.

**Tech Stack:** FastAPI + SQLAlchemy 2 async + Alembic (migration 0121), Next.js 15, pytest via
`docker exec -e PYTEST_DB_HOST=db aprimora-py-backend`, vitest no host.

**Spec:** `docs/superpowers/specs/2026-08-06-pagamentos-fluxo-design.md` — §4.3 (`lote_pagamento`,
`lote_pagamento_parcela`, `retencao`), §6.2 (segregação de funções — gap a fechar), §7.6 (Central da
tesouraria, 7 passos), §9-F4 (aceite), §13 (fora de escopo: integração bancária real).

**Levantamento factual prévio** (Explore, 2026-09-20): head da migration chain = `0120`; não existem
hoje `LotePagamento`/`Retencao`/equivalente em lugar nenhum do código; execução é 100%
parcela-a-parcela (`pagamentos_autorizacao.py::pagar_parcela` aceita 1 parcela por vez; o "lote" da
tela `tesouraria/page.tsx` é um loop sequencial no cliente, comentado como intencional); o
vocabulário de `situacao_pagamento` já inclui `ENVIADA_BANCO`, `FALHOU`, `CONCILIADA` mas nenhum
código atribui esses três hoje; `ato="PAGAR"` existe em `pagamentos_guardas.py::assert_segregacao`
mas **nunca é chamado** — gap pré-existente da F1 que F4 fecha porque é exatamente o código que F4
está tocando.

---

## Global Constraints

- Idioma pt-BR em tudo; commits terminam com `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Migration nova = **0121**, `down_revision="0120"`, head único, `downgrade()` na ordem inversa.
  Tabelas novas com o boilerplate RLS completo (modelo: `_rls` da `0107`/`0102`; GUC `app.tenant_id`
  com `current_setting(..., true)`, `ENABLE+FORCE`, grants tabela+sequence para `aprimora_app`, sem
  worker — nenhuma task Celery escreve neste domínio).
- `tenant_id` do caller, nunca do payload; 404 cross-tenant; `tenant_filter` nas queries.
- **Nunca gravar `Debito.status` direto** — toda transição de `situacao_pagamento` passa por
  `_registrar_transicao(..., pagamento=...)` (mesma guarda AST `test_guarda_status_legado.py` que já
  protege `situacao_tramitacao`/`situacao_fila`).
- Rota literal antes da paramétrica (`test_guarda_ordem_rotas.py`) — `/pagamentos/lotes/elegiveis`
  antes de `/pagamentos/lotes/{id}`, `/pagamentos/retencoes/pendentes` antes de
  `/pagamentos/retencoes/{id}`.
- GET novo com `require_permission` (guarda de leitura); item de menu novo (se houver) entra em
  `PERMISSOES_ESPERADAS` de `__tests__/menus.test.tsx` — F4 não deveria precisar de item de menu
  novo, "Tesouraria" já existe desde a F1; confirmar na Task 7 antes de mexer no menu.
- Teste HTTP com usuário comum (não-SU) em toda rota nova — reutilizar os helpers de
  `test_pagamentos_f3_*.py` (`_provisionar`, `_usuario_com`, `_setup_debito`, `_get`, `_post`); sem
  ids de FK cravados; e-mails `.test`; cleanup no teardown.
- Guarda estrutural nova é provada por inversão antes do commit.
- Testes por task: no mínimo `pytest tests/test_pagamentos_f4_*.py tests/test_guarda_ordem_rotas.py
  tests/test_guarda_modularizacao.py tests/test_guarda_status_legado.py -q`; famílias tocadas
  (`test_pagamentos_f1_*`, `test_pagamentos_autorizacao*`, `test_pagamentos_filas*`) quando alterar
  `pagamentos_autorizacao.py`/`pagamentos_filas.py`/`pagamentos_guardas.py`. FOREGROUND sempre; nunca
  duas suítes simultâneas; confirmar com `docker top aprimora-py-backend` antes de supor que uma
  rodada travou.
- `Paginated<X>`/tipos de `api.ts` casando 1:1 com `response_model`.
- **Fora de escopo (spec §13):** integração bancária real (CNAB de remessa/retorno automatizado,
  API de banco). F4 entrega o **registro** do envio e do retorno — quem envia o arquivo ao banco e
  lê o retorno automatizado continua sendo a operação humana da tesouraria digitando o resultado (ou
  um upload manual do arquivo de retorno numa fatia futura, fora desta).

## Rulings de planejamento (vinculantes)

1. **Lote é por conta pagadora, não por fonte/unidade.** `lote_pagamento.id_conta_pagadora` é fixo
   no lote inteiro (é o que o banco cobra numa remessa real); a tesouraria monta lotes separados por
   conta quando as parcelas elegíveis vierem de contas diferentes.
2. **Parcela entra num lote só a partir de `LIBERADA`** (nunca `A_PAGAR` direto — a liberação da F1
   continua sendo o gate de autorização de tesouraria; o lote é só o agrupamento de execução).
   `assert_ordem_respeitada` (F3) roda na **criação do lote**, débito a débito, igual já roda em
   `liberar_parcelas`/`pagar_parcela` — se algum preterido aparecer, 409 com a lista, antes de criar
   linha nenhuma.
3. **Uma parcela só pode estar em um lote "ativo" por vez.** `UNIQUE (tenant_id, id_parcela) WHERE
   situacao_lote <> 'FALHOU'` em `lote_pagamento_parcela` (a constraint já está na spec §4.3) —
   falha libera a parcela para reentrar num lote novo; sucesso e cancelamento não.
4. **Máquina de estados do lote:** `RASCUNHO → PROGRAMADO → ENVIADO → PROCESSADO`, com `CANCELADO`
   alcançável de `RASCUNHO` ou `PROGRAMADO` (não de `ENVIADO` — depois de enviado ao banco, o lote só
   se resolve por retorno, nunca por cancelamento unilateral). Adicionar/remover parcela só em
   `RASCUNHO`. Programar (`RASCUNHO→PROGRAMADO`) grava `data_programada`; enviar
   (`PROGRAMADO→ENVIADO`) grava `enviado_em` e é o ponto que move `situacao_pagamento` de `PROGRAMADA`
   para `ENVIADA_BANCO` em todos os débitos do lote; processar retorno (`ENVIADO→PROCESSADO`) é
   quando cada parcela vira `PAGA` ou `FALHOU` e os débitos recebem `PAGA`/`PAGA_PARCIAL`/`FALHOU`
   conforme o mix. `PROCESSADO` é terminal (retorno parcial sucessivo permanece `ENVIADO` até a
   última parcela do lote ser resolvida).
5. **Retenção é lançada pela tesouraria, sob `pagamento_pagar`.** A spec (§7.7) descreve retenção no
   formulário de nova solicitação como estado final do produto, mas isso pertenceria a uma fatia de
   UX de captura antecipada — fora do escopo de F4. Aqui, retenção é CRUD no detalhe do débito
   (aba "Retenções", que já existe na spec §7.2 mas hoje está vazia por falta de dado), liberado
   **desde a criação do débito até a criação do lote** (mesma janela que faz sentido operacionalmente:
   depois que a parcela entra num lote ativo, a retenção trava — mudar valor líquido de um lote já
   `PROGRAMADO`/`ENVIADO` seria alterar dinheiro em trânsito). Guard: `criar/atualizar/excluir
   retenção` de um débito com alguma parcela em lote `RASCUNHO+` → 409.
6. **`valor_liquido` do débito é sempre calculado**, nunca coluna: `valor_total − Σ retencao.valor
   WHERE excluido=false`. Função pura em `pagamentos_estados.py` ou novo módulo
   `pagamentos_retencoes.py`, reaproveitada por schema `Out` e pelo cálculo de `valor_total` do lote.
7. **Comprovante é um único anexo por lote**, não por parcela — é o arquivo/registro da remessa
   confirmada pelo banco (extrato de envio, protocolo, PDF do TED/PIX em lote). Reaproveita
   `protocolos.anexo` com uma FK direta e simples em `lote_pagamento.id_anexo_comprovante` (nullable
   até o retorno ser processado) — **não** cria uma tabela de vínculo nova (YAGNI: um lote, um
   comprovante; se um dia precisar de N documentos por lote, generaliza-se então). Autorização de
   download segue o mesmo padrão de `get_anexo_debito_path_autorizado` (permissão do módulo +
   autorização antes de resolver o recurso), adaptada para o lote.
8. **Falha e reprocesso não passam por `pedido_ajuste` (F2).** É outra classe de evento — falha
   bancária, não ajuste de mérito. `Parcela.status` volta a `LIBERADA`; `debito.situacao_pagamento`
   vira `FALHOU` até entrar num lote novo, quando volta a `PROGRAMADA`. `lote_pagamento_parcela`
   correspondente fica congelada em `FALHOU` com `motivo_falha` — é o registro permanente daquela
   tentativa específica, nunca apagado nem reaproveitado pelo lote seguinte (linha nova).
9. **`debito.situacao_pagamento = PAGA_PARCIAL` no nível do débito** quando o débito tem mais de uma
   parcela e nem todas estão `PAGA` (já existe desde a F1, `pagar_parcela` grava isso — F4 só precisa
   preservar o comportamento ao processar retorno de lote com várias parcelas do mesmo débito
   misturadas entre sucesso/falha).
10. **Segregação de funções na execução (spec §6.2, premissa 6) fecha em F4**: `assert_segregacao(...,
    ato="PAGAR")` passa a ser chamado no momento de **enviar o lote** (não na criação/rascunho — até
    lá é só seleção, reversível). Verifica, para cada débito do lote, que o usuário que está enviando
    não é o solicitante, o gestor decisor nem o validador daquele débito específico. Falha de um
    único débito no lote barra o envio do lote inteiro (409 com a lista dos débitos problemáticos) —
    não há envio parcial por segregação, só por retorno bancário. Super-usuário **não** faz bypass
    (mesma regra da F1/F3).
11. **Recolhimento de retenção é ato isolado**, não amarrado ao ciclo do lote. `POST
    /pagamentos/retencoes/{id}/recolher` grava `recolhido=true`, `data_recolhimento`,
    `documento_recolhimento`; sem transição de volta (recolhimento não tem "desfazer" nesta fatia —
    é ato administrativo externo ao sistema, registro é o que importa). Tela: lista "Retenções
    pendentes de recolhimento" agrupada por tipo (IRRF/INSS/ISS/PIS_COFINS_CSLL/OUTRAS), útil para
    quem monta a guia de recolhimento do mês.
12. **`fila_tesouraria`/`GET /pagamentos/tesouraria/fila` é substituída, não remendada.** A tela nova
    (Central da tesouraria) trabalha em cima de "parcelas elegíveis para lote" + "lotes existentes",
    não da lista achatada atual. O endpoint antigo vira **410 Gone** apontando o substituto (mesmo
    padrão usado em `/aprovar`/`/encaminhar` na F1) — ele é interno (chamado só pelo próprio
    frontend), sem consumidor externo a proteger.
13. **`ck_debhist_acao` ganha as ações**: `LOTE_CRIADO`, `LOTE_PROGRAMADO`, `LOTE_ENVIADO`,
    `PAGAMENTO_CONFIRMADO`, `PAGAMENTO_FALHOU`, `LOTE_CANCELADO`, `RETENCAO_RECOLHIDA` — seguindo o
    padrão de recriar o CHECK inteiro citando a tupla vigente completa (mesmo padrão de `0111`).
    `debito_historico` ganha uma linha por débito afetado a cada transição de lote (mesmo quando o
    ato é sobre o lote inteiro) — é o único jeito de a Task 7.2/detalhe do débito mostrar o evento na
    aba Histórico sem juntar contra `lote_pagamento`.

---

## Estrutura de arquivos

| Arquivo | Papel |
|---|---|
| `backend/alembic/versions/0121_pagamentos_lote_retencao.py` | Create: `lote_pagamento`, `lote_pagamento_parcela`, `retencao`; amplia `ck_debhist_acao`; RLS completo nas 3 tabelas novas |
| `backend/app/models/pagamentos.py` | Modify: `LotePagamento`, `LotePagamentoParcela`, `Retencao` |
| `backend/app/services/pagamentos_retencoes.py` | Create: `criar_retencao`, `atualizar_retencao`, `excluir_retencao`, `listar_retencoes_debito`, `valor_liquido_debito`, `recolher_retencao`, `listar_pendentes_recolhimento` |
| `backend/app/services/pagamentos_lotes.py` | Create: `parcelas_elegiveis_para_lote`, `criar_lote`, `adicionar_parcela`, `remover_parcela`, `cancelar_lote`, `programar_lote`, `enviar_lote`, `processar_retorno`, `anexar_comprovante` |
| `backend/app/services/pagamentos_guardas.py` | Modify: chamar `assert_segregacao(..., ato="PAGAR")` de dentro de `enviar_lote` (não mais dead code) |
| `backend/app/services/pagamentos_autorizacao.py` | Modify: `pagar_parcela`/`estornar_parcela` avaliados — decidir se seguem existindo para pagamento avulso fora de lote (ruling a confirmar na Task 3) ou se F4 os aposenta em favor do lote |
| `backend/app/services/pagamentos_filas.py` | Modify: `fila_tesouraria` removida/depreciada conforme ruling 12 |
| `backend/app/services/pagamentos_debitos.py` | Modify: `_sincronizar_status_legado`/vocabulário — conferir `ENVIADA_BANCO`/`FALHOU`/`CONCILIADA` já mapeiam certo (deveriam, são só valores de string) |
| `backend/app/routers/pagamentos_lotes.py` | Create: `/pagamentos/lotes/*` |
| `backend/app/routers/pagamentos_retencoes.py` | Create: `/pagamentos/retencoes/*` |
| `backend/app/routers/pagamentos_debitos.py` | Modify: `GET /tesouraria/fila` → 410 Gone |
| `backend/app/main.py` | Modify: registrar os 2 routers novos |
| `backend/app/schemas/pagamentos.py` | Modify: `RetencaoCreate/Update/Out`, `LotePagamentoOut`, `LotePagamentoParcelaOut`, `ParcelaElegivelOut`, `RetornoLoteIn` |
| `backend/app/cli/seed_bootstrap.py` | Conferir: nenhuma transação nova, então **sem mudança** — confirmar na Task 1 antes de assumir |
| `backend/tests/test_pagamentos_f4_lote.py` | Create: máquina de estados do lote, elegibilidade, ordem cronológica no lote |
| `backend/tests/test_pagamentos_f4_retencao.py` | Create: CRUD, líquido, trava por lote ativo, recolhimento |
| `backend/tests/test_pagamentos_f4_retorno.py` | Create: retorno sucesso/falha/misto, reprocesso, segregação no envio |
| `frontend/lib/api.ts` | Modify: seção `pagamentos.lotes`, `pagamentos.retencoes`; remover/depreciar `pagamentos.filas.tesouraria` |
| `frontend/app/(app)/m/pagamentos/tesouraria/page.tsx` | Rewrite: Central da tesouraria, 7 passos |
| `frontend/components/pagamentos/DetalheDebitoContent.tsx` | Modify: aba Retenções ganha conteúdo real |
| `frontend/components/pagamentos/` | Create: `CentralTesouraria*.tsx` (passos), `RetencoesSecao.tsx` |
| `frontend/__tests__/pagamentos-f4.test.tsx` | Create |

---

### Task 1: Migration 0121 + modelos

**Files:**
- Create: `backend/alembic/versions/0121_pagamentos_lote_retencao.py`
- Modify: `backend/app/models/pagamentos.py`, `backend/app/models/__init__.py`
- Test: `backend/tests/test_pagamentos_f4_lote.py` (só invariantes desta task)

**Interfaces (nomes EXATOS — tasks seguintes dependem):**

```python
class LotePagamento(Base):              # pagamentos.lote_pagamento
    id, tenant_id
    numero: str                          # varchar(20), único por tenant
    id_conta_pagadora: int               # FK conta_bancaria, NOT NULL
    situacao: str                        # varchar(20) — RASCUNHO|PROGRAMADO|ENVIADO|PROCESSADO|CANCELADO
    data_programada: date | None
    valor_total: Decimal                 # numeric(14,2) — soma congelada na criação/revisão, não recalculada em runtime após ENVIADO
    id_anexo_comprovante: int | None     # FK protocolos.anexo, NULL
    id_usuario: int                      # FK utils.usuario — quem criou
    id_usuario_envio: int | None         # FK utils.usuario — quem enviou (para a checagem de segregação e auditoria)
    enviado_em: datetime | None
    processado_em: datetime | None
    criado_em, atualizado_em, excluido

class LotePagamentoParcela(Base):        # pagamentos.lote_pagamento_parcela
    id, tenant_id
    id_lote: int                         # FK lote_pagamento
    id_parcela: int                      # FK parcela
    situacao: str                        # varchar(20) — PENDENTE|PAGA|FALHOU
    motivo_falha: str | None             # varchar(255)
    criado_em, atualizado_em
    # UNIQUE (tenant_id, id_parcela) WHERE situacao <> 'FALHOU'

class Retencao(Base):                    # pagamentos.retencao
    id, tenant_id
    id_debito: int                       # FK debito
    tipo: str                            # varchar(20) — IRRF|INSS|ISS|PIS_COFINS_CSLL|OUTRAS
    descricao: str | None                # varchar(150)
    base_calculo: Decimal                # numeric(14,2) NOT NULL
    aliquota: Decimal | None             # numeric(6,3)
    valor: Decimal                       # numeric(14,2) NOT NULL
    recolhido: bool                      # default false
    data_recolhimento: date | None
    documento_recolhimento: str | None   # varchar(50)
    criado_em, atualizado_em, excluido
```

- [ ] **Step 1: Migration** — 3 tabelas (DDL espelhando §4.3 + campos de auditoria dos rulings 1-7);
  índices `(tenant_id, id_lote)` em `lote_pagamento_parcela`, `(tenant_id, id_debito)` em `retencao`,
  `(tenant_id, situacao)` em `lote_pagamento`; CHECKs `ck_lote_situacao`
  (`RASCUNHO|PROGRAMADO|ENVIADO|PROCESSADO|CANCELADO`), `ck_lote_parcela_situacao`
  (`PENDENTE|PAGA|FALHOU`), `ck_retencao_tipo`
  (`IRRF|INSS|ISS|PIS_COFINS_CSLL|OUTRAS`); `UNIQUE (tenant_id, numero)` em `lote_pagamento`,
  `UNIQUE (tenant_id, id_parcela) WHERE situacao <> 'FALHOU'` em `lote_pagamento_parcela`. Amplia
  `ck_debhist_acao` com as 7 ações do ruling 13, recriando o CHECK inteiro (padrão `0111`). RLS
  completo (`ENABLE+FORCE`, as duas policies com `NULLIF(current_setting('app.tenant_id', true),
  '')::int`, grants tabela+sequence para `aprimora_app`) nas 3 tabelas novas. Sem backfill (tabelas
  novas, sem dado legado). `downgrade()`: drop das 3 tabelas na ordem inversa de FK, reverte o CHECK
  de `ck_debhist_acao` para a lista vigente da `0111`.
- [ ] **Step 2: Modelos** no padrão do arquivo + reexport em `models/__init__.py`.
- [ ] **Step 3: Teste de invariante (RED primeiro)** em `test_pagamentos_f4_lote.py`:

```python
async def test_parcela_unica_em_lote_ativo(admin_engine, ...):
    # 2ª linha lote_pagamento_parcela para a mesma parcela, situacao != FALHOU → IntegrityError
async def test_numero_lote_unico_por_tenant(admin_engine, ...):
    # 2 lotes com mesmo numero no mesmo tenant → IntegrityError; tenants diferentes, mesmo numero → ok
```

- [ ] **Step 4: Validar migration**

```bash
docker exec aprimora-py-backend alembic upgrade head    # 0121
docker exec aprimora-py-backend alembic heads           # único
docker exec aprimora-py-backend alembic downgrade -1 && docker exec aprimora-py-backend alembic upgrade head
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_rls_papeis_minimos.py tests/test_pagamentos_f4_lote.py -q
```

- [ ] **Step 5: Commit** `feat(pagamentos): migration 0121 — lote_pagamento, lote_pagamento_parcela, retencao (F4)`

---

### Task 2: Retenções — service, schemas, router

**Files:**
- Create: `backend/app/services/pagamentos_retencoes.py`, `backend/app/routers/pagamentos_retencoes.py`
- Modify: `backend/app/schemas/pagamentos.py`, `backend/app/main.py` (registrar router)
- Test: `backend/tests/test_pagamentos_f4_retencao.py`

**Interfaces:**

```python
def valor_liquido(valor_total: Decimal, retencoes: list[Retencao]) -> Decimal: ...  # pura, ruling 6

async def criar_retencao(db, *, tenant_id, id_debito, tipo, base_calculo, aliquota, valor, descricao, usuario_id) -> Retencao: ...
async def atualizar_retencao(db, *, tenant_id, retencao_id, ...) -> Retencao: ...
async def excluir_retencao(db, *, tenant_id, retencao_id) -> None: ...   # soft-delete
async def listar_retencoes_debito(db, *, tenant_id, id_debito) -> list[Retencao]: ...
async def recolher_retencao(db, *, tenant_id, retencao_id, data_recolhimento, documento_recolhimento) -> Retencao: ...
async def listar_pendentes_recolhimento(db, *, tenant_id, tipo=None) -> list[Retencao]: ...

async def _assert_debito_fora_de_lote_ativo(db, *, tenant_id, id_debito) -> None:
    # 409 se existir lote_pagamento_parcela PENDENTE ligada a alguma parcela deste débito
    # em lote com situacao in (RASCUNHO, PROGRAMADO, ENVIADO)  — ruling 5
```

- [ ] **Step 1: Service** — `criar_retencao`/`atualizar_retencao`/`excluir_retencao` chamam
  `_assert_debito_fora_de_lote_ativo` primeiro (409 `"Débito tem parcela em lote ativo — retenção
  travada"`); `valor_liquido` pura, sem `db`, testável isolada.
- [ ] **Step 2: Schemas** — `RetencaoCreate` (tipo/base_calculo/aliquota?/valor/descricao?),
  `RetencaoUpdate` (mesmos campos opcionais, tratando `""`→`None`), `RetencaoOut`. `DebitoOut` ganha
  `valor_liquido: Decimal` (computed, não persistido) e `retencoes: list[RetencaoOut]` (ou endpoint
  separado — decidir por custo de query; tendência: endpoint separado
  `GET /pagamentos/debitos/{id}/retencoes`, mais barato quando a lista do débito não precisa do
  detalhe).
- [ ] **Step 3: Router** `pagamentos_retencoes.py`:
  - `GET /pagamentos/debitos/{id}/retencoes` (`pagamento_pagar`, leitura ampliada por
    `_LEITURA` como conciliação já faz — conferir se `pagamento_auditar`/`pagamento_validar` também
    devem ler; ruling: sim, mesma lista `_LEITURA` de `pagamentos_conciliacao.py`)
  - `POST /pagamentos/debitos/{id}/retencoes` (`pagamento_pagar`, escrita)
  - `PUT /pagamentos/retencoes/{id}` , `DELETE /pagamentos/retencoes/{id}` (`pagamento_pagar`)
  - `GET /pagamentos/retencoes/pendentes` (**antes** de qualquer rota paramétrica de retenção;
    `pagamento_pagar`) — filtro `?tipo=`
  - `POST /pagamentos/retencoes/{id}/recolher` (`pagamento_pagar`)
- [ ] **Step 4: Testes** — CRUD feliz; 409 com débito em lote ativo (monta lote de teste mínimo,
  mesmo antes da Task 3 existir como feature completa — pode inserir a linha
  `lote_pagamento_parcela` direto via fixture para este teste, sem depender do serviço de lote
  ainda não escrito); `valor_liquido` com 0, 1 e N retenções, excluída não conta; recolhimento grava
  os 3 campos; teste HTTP usuário comum.
- [ ] **Step 5: Suíte e commit** `feat(pagamentos): retenções — CRUD, líquido derivado, recolhimento (F4)`

---

### Task 3: Serviço de lote — seleção, criação, revisão, cancelamento

**Files:**
- Create: `backend/app/services/pagamentos_lotes.py` (início), parte de `pagamentos_routers/pagamentos_lotes.py`
- Modify: `backend/app/services/pagamentos_autorizacao.py` (decisão abaixo)
- Test: `backend/tests/test_pagamentos_f4_lote.py`

**Decisão a fechar nesta task (não adiar):** `pagar_parcela`/`estornar_parcela` avulsos
(`pagamentos_autorizacao.py`) **continuam existindo** para o caso de pagamento fora do rito de lote
(ex.: correção pontual, estorno). O lote é o caminho **recomendado e exposto na Central da
tesouraria**, não o único fisicamente possível no backend — evita reescrever `estornar_parcela` (que
já lida bem com reversão de `MovimentacaoConta`) dentro do conceito de lote, que não faz sentido para
estorno. `liberar_parcelas`/`revogar_liberacao` também continuam como estão (são antes do lote).

**Interfaces:**

```python
async def parcelas_elegiveis_para_lote(db, *, tenant_id, id_conta_pagadora=None) -> list[Parcela]:
    # status == LIBERADA, sem linha lote_pagamento_parcela ativa (mesmo filtro do UNIQUE),
    # opcionalmente filtradas por conta pagadora do débito

async def criar_lote(db, *, tenant_id, id_conta_pagadora, parcela_ids: list[int], usuario_id) -> LotePagamento:
    # valida: todas LIBERADA, todas da mesma conta pagadora, nenhuma já em lote ativo (senão 409),
    # assert_ordem_respeitada débito a débito (F3, senão 409 com preteridos),
    # numero sequencial por tenant (mesmo padrão de OrdemPagamento — conferir geração lá),
    # valor_total = soma dos valor_liquido dos débitos das parcelas, situacao=RASCUNHO,
    # cria N linhas lote_pagamento_parcela(situacao=PENDENTE), debito_historico LOTE_CRIADO por débito

async def adicionar_parcela(db, *, tenant_id, lote_id, parcela_id, usuario_id) -> LotePagamento: ...
    # só se lote.situacao == RASCUNHO (senão 409); mesmas validações de criar_lote para a parcela isolada

async def remover_parcela(db, *, tenant_id, lote_id, parcela_id, usuario_id) -> LotePagamento: ...
    # só RASCUNHO; deleta a linha lote_pagamento_parcela (não soft-delete — nunca existiu de fato)

async def cancelar_lote(db, *, tenant_id, lote_id, usuario_id) -> LotePagamento: ...
    # só RASCUNHO|PROGRAMADO (ruling 4); situacao=CANCELADO; libera as parcelas (remove as linhas
    # lote_pagamento_parcela, parcelas voltam a aparecer em parcelas_elegiveis_para_lote);
    # debito_historico LOTE_CANCELADO por débito afetado

async def listar_lotes(db, *, tenant_id, situacao=None) -> Paginated[LotePagamento]: ...
async def obter_lote(db, *, tenant_id, lote_id) -> LotePagamento: ...  # com parcelas + débitos (join)
```

- [ ] **Step 1: Service** conforme interfaces acima. `_proximo_numero_lote(db, tenant_id)` — conferir
  se `OrdemPagamento` tem um padrão de numeração reaproveitável (`pagamentos_autorizacao.py`) antes de
  inventar um novo.
- [ ] **Step 2: Router** `pagamentos_lotes.py`:
  - `GET /pagamentos/lotes/elegiveis` (**antes** de `/pagamentos/lotes/{id}`) — lista
    `parcelas_elegiveis_para_lote`, agrupadas por conta pagadora (o cabeçalho da Central pede isso)
  - `POST /pagamentos/lotes` (criar)
  - `GET /pagamentos/lotes` (listar, paginado)
  - `GET /pagamentos/lotes/{id}` (detalhe)
  - `POST /pagamentos/lotes/{id}/parcelas` / `DELETE /pagamentos/lotes/{id}/parcelas/{parcela_id}`
  - `POST /pagamentos/lotes/{id}/cancelar`
  - todas sob `pagamento_pagar`.
- [ ] **Step 3: Testes** — criação feliz (2+ parcelas, conta única); rejeita conta mista (422/409 —
  decidir código, sugestão 422 por ser erro de formulário, não de estado); rejeita parcela não
  `LIBERADA`; rejeita parcela já em lote ativo; 409 com preteridos quando fura ordem cronológica;
  adicionar/remover só em `RASCUNHO`; cancelar libera parcelas (reaparecem em `elegiveis`); teste
  HTTP usuário comum.
- [ ] **Step 4: Suíte e commit** `feat(pagamentos): lote de pagamento — seleção, criação, revisão, cancelamento (F4)`

---

### Task 4: Programar e enviar o lote — fecha o gap de segregação

**Files:**
- Modify: `backend/app/services/pagamentos_lotes.py`, `backend/app/services/pagamentos_guardas.py`,
  `backend/app/routers/pagamentos_lotes.py`
- Test: `backend/tests/test_pagamentos_f4_lote.py`, `backend/tests/test_pagamentos_f4_retorno.py`
  (segregação no envio)

**Interfaces:**

```python
async def programar_lote(db, *, tenant_id, lote_id, data_programada, usuario_id) -> LotePagamento:
    # só RASCUNHO com >= 1 parcela (senão 409 "lote vazio"); situacao=PROGRAMADO;
    # debito_historico LOTE_PROGRAMADO por débito

async def enviar_lote(db, *, tenant_id, lote_id, usuario_id) -> LotePagamento:
    # só PROGRAMADO; PARA CADA débito do lote: assert_segregacao(debito, usuario_id, ato="PAGAR")
    #   — se qualquer um falhar, 409 com a lista de débitos problemáticos, NADA é gravado (all-or-nothing)
    # situacao=ENVIADO, enviado_em=now(), id_usuario_envio=usuario_id
    # PARA CADA débito: _registrar_transicao(..., pagamento=EST.ENVIADA_BANCO)
    # debito_historico LOTE_ENVIADO por débito
```

- [ ] **Step 1: `assert_segregacao` ganha corpo para `ato="PAGAR"`** em `pagamentos_guardas.py` (hoje
  o `Literal`/match já tem o caso mas nunca é exercitado — conferir se precisa só habilitar ou também
  implementar a lógica: comparar `usuario_id` contra
  `debito.id_usuario_solicitante`/`id_gestor_decisor`/`id_validador`). Teste dedicado ANTES de plugar
  em `enviar_lote` (RED primeiro): SU tentando enviar lote com débito que ele mesmo validou → 403.
- [ ] **Step 2:** `programar_lote`/`enviar_lote` no service; router `POST
  /pagamentos/lotes/{id}/programar`, `POST /pagamentos/lotes/{id}/enviar`.
- [ ] **Step 3: Testes** — programar lote vazio → 409; enviar não-programado → 409; enviar com
  segregação violada → 403, lote continua `PROGRAMADO` (nada gravado); enviar feliz → todos os
  débitos em `ENVIADA_BANCO`, lote `ENVIADO`; teste HTTP usuário comum (dois usuários distintos,
  papéis diferentes, para não colidir com a própria checagem de segregação sendo testada).
- [ ] **Step 4: Suíte e commit** `feat(pagamentos): programar/enviar lote — fecha segregação de funções na execução (F4)`

---

### Task 5: Processar retorno — pago/falhou, comprovante, reprocesso

**Files:**
- Modify: `backend/app/services/pagamentos_lotes.py`, `backend/app/routers/pagamentos_lotes.py`,
  `backend/app/schemas/pagamentos.py`
- Test: `backend/tests/test_pagamentos_f4_retorno.py`

**Interfaces:**

```python
class RetornoParcelaIn(BaseModel):
    parcela_id: int
    resultado: Literal["PAGA", "FALHOU"]
    motivo_falha: str | None = None      # obrigatório se FALHOU (422 senão)
    data_pagamento: date | None = None   # default hoje se PAGA

async def processar_retorno(db, *, tenant_id, lote_id, retornos: list[RetornoParcelaIn], usuario_id) -> LotePagamento:
    # só ENVIADO; para cada retorno:
    #   PAGA  → lote_pagamento_parcela.situacao=PAGA; Parcela.status=PAGA; grava MovimentacaoConta
    #           (mesmo padrão de pagar_parcela); debito recalcula PAGA|PAGA_PARCIAL (ruling 9)
    #   FALHOU → lote_pagamento_parcela.situacao=FALHOU (+motivo_falha); Parcela.status volta a LIBERADA;
    #            debito.situacao_pagamento = FALHOU (ruling 8); debito_historico PAGAMENTO_FALHOU
    # lote.situacao = PROCESSADO só quando toda parcela do lote saiu de PENDENTE (senão continua ENVIADO
    # — retorno pode chegar em ondas)
    # debito_historico PAGAMENTO_CONFIRMADO por débito com pelo menos 1 PAGA

async def anexar_comprovante(db, *, tenant_id, lote_id, anexo_id, usuario_id) -> LotePagamento:
    # grava id_anexo_comprovante; sem restrição de situacao do lote (pode anexar antes ou depois do retorno)
```

- [ ] **Step 1: Service** `processar_retorno` — reaproveitar o trecho de gravação de
  `MovimentacaoConta` de `pagar_parcela` (extrair função privada comum se o corpo for idêntico o
  bastante; não forçar se as pré-condições divergirem demais — 3 linhas duplicadas é melhor que uma
  abstração errada).
- [ ] **Step 2: Router** — `POST /pagamentos/lotes/{id}/retorno` (body: lista de
  `RetornoParcelaIn`), `POST /pagamentos/lotes/{id}/comprovante` (reaproveita o padrão de upload de
  `pagamentos_anexos.py`, adaptado para lote em vez de débito).
- [ ] **Step 3: Testes** — retorno 100% sucesso → lote `PROCESSADO`, débitos `PAGA`; retorno misto
  (2 PAGA + 1 FALHOU no mesmo débito multiparcelado) → débito `PAGA_PARCIAL`; parcela que falhou
  reaparece em `parcelas_elegiveis_para_lote` (reprocesso); segunda tentativa cria nova linha
  `lote_pagamento_parcela`, a antiga permanece `FALHOU` (não é sobrescrita — auditoria); retorno em
  ondas mantém lote `ENVIADO` até a última parcela resolver; download de comprovante autorizado
  (permissão do módulo, autorização antes de resolver recurso — mesma disciplina do anexo de
  débito); teste HTTP usuário comum.
- [ ] **Step 4: Suíte e commit** `feat(pagamentos): retorno de lote — pago/falha/reprocesso + comprovante (F4)`

---

### Task 6: Aposentar `fila_tesouraria` legada

**Files:**
- Modify: `backend/app/routers/pagamentos_debitos.py` (`GET /tesouraria/fila` → 410),
  `backend/app/services/pagamentos_filas.py` (remover `fila_tesouraria` ou marcar deprecated —
  decidir na hora: se nenhum outro consumidor chamar, remover de verdade; grep antes de apagar)
- Test: atualizar/remover o teste que hoje cobre esse endpoint

- [ ] **Step 1:** grep por `fila_tesouraria`/`/tesouraria/fila` em todo o repo (backend E frontend)
  antes de tocar — confirmar que só o próprio `tesouraria/page.tsx` (que a Task 7 reescreve) consome.
- [ ] **Step 2:** endpoint → 410 com mensagem apontando `/pagamentos/lotes/elegiveis` +
  `/pagamentos/lotes`; função de serviço removida se órfã.
- [ ] **Step 3: Suíte e commit** `fix(pagamentos): aposenta GET /tesouraria/fila (410) — substituído pelos lotes (F4)`

---

### Task 7: Frontend — Central da tesouraria (7 passos) + Retenções no detalhe

**Files:**
- Modify: `frontend/lib/api.ts` (seção `pagamentos.lotes`, `pagamentos.retencoes`; remover
  `pagamentos.filas.tesouraria`), `frontend/components/pagamentos/DetalheDebitoContent.tsx`
- Rewrite: `frontend/app/(app)/m/pagamentos/tesouraria/page.tsx`
- Create: `frontend/components/pagamentos/RetencoesSecao.tsx`, componentes de passo da Central
  (nomes a definir durante a implementação — ex. `SelecionarElegiveisStep.tsx`,
  `RevisarLoteStep.tsx`, `RetornoLoteStep.tsx`, ou um único arquivo com state machine local se ficar
  mais simples que 7 arquivos — decidir olhando o tamanho real, sem prescrever agora)
- Test: `frontend/__tests__/pagamentos-f4.test.tsx`

- [ ] **Step 1: Tipos em `api.ts`** — `LotePagamento`, `LotePagamentoParcela`, `Retencao`, e os
  métodos correspondentes aos routers das Tasks 2-6. Endpoint paginado (`GET /pagamentos/lotes`) usa
  `Paginated<LotePagamento>`.
- [ ] **Step 2: Central da tesouraria** — cabeçalho permanente (spec §7.6: quantidade, valor total,
  conta pagadora, fonte, bloqueados, erros, situação do lote) + os 7 passos como wizard/stepper
  local (sem rota própria por passo — mesma filosofia de "não perder contexto" do §7.7). Passo
  "processar retorno" é formulário por parcela (resultado PAGA/FALHOU + motivo condicional).
- [ ] **Step 3: Retenções no detalhe** — `RetencoesSecao.tsx` dentro da aba "Retenções" já prevista
  em `DetalheDebitoContent.tsx`: lista, adicionar/editar/excluir (desabilitado com tooltip explicando
  o motivo quando o débito estiver em lote ativo — 409 do backend vira mensagem, não erro genérico),
  líquido calculado exibido junto do bruto.
- [ ] **Step 4: Tela de recolhimentos** — lista simples "Retenções pendentes de recolhimento"
  (reaproveita padrão de tabela existente do módulo), ação "Registrar recolhimento" abre modal com
  data+documento.
- [ ] **Step 5: Testes vitest** — fluxo feliz do wizard (mock de api.ts), aba retenções
  renderiza/trava conforme prop, formulário de retorno valida motivo obrigatório em FALHOU.
- [ ] **Step 6: `npx tsc --noEmit` limpo** + teste manual no browser (dev server) do fluxo completo:
  criar lote → programar → enviar → processar retorno com 1 sucesso + 1 falha → conferir que a
  falhada reaparece em elegíveis.
- [ ] **Step 7: Commit** `feat(pagamentos): Central da tesouraria — lote em 7 passos, retenções, recolhimentos (F4)`

---

### Task 8: Docs e fechamento

- [ ] Atualizar `docs/BACKLOG-PENDENCIAS.md` §1.0 (pagamentos): F4 fechado, F5 (remoção do `status`
  legado) segue não autorizada — não iniciar sem pedir.
- [ ] Atualizar a spec (`2026-08-06-pagamentos-fluxo-design.md`) se alguma ruling deste plano divergir
  do texto original (ex.: ruling 12, substituição em vez de extensão de `fila_tesouraria`; ruling 7,
  comprovante único por lote em vez de não especificado) — a spec é a autoridade, e rulings que
  mudam o desenho registrado nela precisam voltar pra lá, não só para este plano.
- [ ] Suíte completa (`pytest -q`, sem filtro) + `tsc --noEmit` + `vitest run` verdes antes do commit
  final.

---

## Aceite da fatia (spec §9-F4)

- [ ] Lote só aceita parcela `LIBERADA` e elegível pela ordem cronológica (preterido → 409 com lista).
- [ ] Pagamento falho no retorno reprocessa (parcela volta a `LIBERADA`, reaparece em elegíveis; o
  registro da tentativa falha permanece, imutável, para auditoria).
- [ ] Retenções compõem o líquido (`valor_liquido` correto em toda leitura, nunca armazenado).
- [ ] Segregação de funções bloqueia o **envio** do lote quando o mesmo usuário decidiu o débito em
  papel anterior — inclusive super-usuário (403, sem bypass).
- [ ] `GET /tesouraria/fila` devolve 410 com o substituto indicado.
- [ ] Suíte completa verde nos dois papéis de banco (`ged_user` padrão dos testes e, se aplicável,
  `aprimora_app` conforme §"Papéis de banco" do CLAUDE.md).

---

## Riscos específicos desta fatia

| Risco | Mitigação |
|---|---|
| Envio de lote grava metade e falha no meio (crash) | transação única do banco por `enviar_lote`; se `assert_segregacao` falhar para qualquer débito, nada é gravado (checagem completa antes do primeiro `UPDATE`) |
| Retorno em ondas deixa lote "preso" em `ENVIADO` para sempre | Central da tesouraria lista lotes `ENVIADO` com contagem de pendentes — visível, não fica escondido |
| Cálculo de líquido diverge entre backend (autoridade) e frontend (exibição otimista) | frontend nunca calcula líquido sozinho — sempre lê `valor_liquido` do `DebitoOut`/`RetencaoOut` |
| `assert_segregacao(ato="PAGAR")` nunca foi exercitado em produção — comportamento real desconhecido | teste dedicado (Task 4, Step 1) isolado do resto do lote antes de integrar |
