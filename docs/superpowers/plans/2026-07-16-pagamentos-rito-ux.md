# Pagamentos — Liberação de pagamento + redesign UX — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Completar o rito da 4.320/64 (novo ato: **liberar pagamento** por parcela) e redesenhar a UX do módulo (menu enxuto com Cadastros colapsado, stepper do rito, Autorizações com tabs Despesa/Pagamento agrupadas por conta, tela Tesouraria).

**Architecture:** Spec: `docs/superpowers/specs/2026-07-16-pagamentos-rito-ux-design.md` (fonte da verdade para payloads/telas). Parcela ganha estado LIBERADA + 3 colunas (migration 0049, ALTER only). Filas agregadas viram endpoints próprios (grupo por conta, enriquecidos). Frontend rebuild sobre o design system existente.

**Tech Stack:** o mesmo do módulo. Testes service-level TDD; tsc; verificação browser pelo controller.

## Global Constraints

- Herda TODAS as constraints do módulo (tenant+excluido em cada join, Decimal, transições só via service com histórico no mesmo commit, locks with_for_update nos fluxos de dinheiro).
- Estados parcela: `A_PAGAR → LIBERADA → PAGA` (+CANCELADA). `pagar_parcela` exige LIBERADA (409 c/ mensagem clara). `estornar_parcela` → A_PAGAR + limpa data_liberacao/id_usuario_liberacao/data_prevista_pagamento.
- `liberar_parcelas` é LOTE all-or-nothing; permissão `pagamento_autorizar`; guards por parcela: status A_PAGAR + débito AUTORIZADO|PAGO_PARCIAL; histórico UMA ação `LIBERADO` por débito envolvido (justificativa "Parcelas N, M").
- `comprometido_conta` e KPIs (vencidas/a_pagar_30d) somam `IN ('A_PAGAR','LIBERADA')`.
- CHECKs: parcela status ganha 'LIBERADA'; debito_historico acao ganha 'LIBERADO','LIBERACAO_REVOGADA' (ALTER dos CHECKs na 0049 — DROP CONSTRAINT + ADD com a lista nova, reversível).
- Menu/telas conforme spec §2-4; stepper `RitoPagamento` em Visão geral, Autorizações, Tesouraria e detalhe do débito.
- Sem link azul em texto de linha; ações são botões/linha clicável; valores tabular-nums à direita; barras de ação sticky; truncamento sempre com min-w-0/max-w.

## File Structure

- `backend/alembic/versions/0049_parcela_liberacao.py` — novo.
- `backend/app/models/pagamentos.py` (+3 colunas Parcela), `schemas/pagamentos.py` (filas + liberar payloads), `services/pagamentos_autorizacao.py` (liberar/revogar/pagar/estornar), `services/pagamentos_caixa.py` (comprometido), `services/pagamentos_dashboard.py` (KPIs), `services/pagamentos_filas.py` — **novo** (fila autorização/liberação/tesouraria agregadas), `routers/pagamentos_debitos.py` (endpoints novos + minha-fila bucket liberar).
- `backend/scripts/seed_pagamentos_demo.py` — liberar antes de pagar; ~15 LIBERADAS pendentes.
- `backend/tests/test_pagamentos_liberacao.py` — novo; ajustes em test_pagamentos_autorizacao/dashboard.
- `frontend/components/pagamentos/RitoPagamento.tsx` — novo; `components/Sidebar.tsx` (subgrupo colapsável + menu §2); `lib/api.ts` (tipos/rotas novas); `app/(app)/pagamentos/autorizacao/page.tsx` (rebuild tabs); `app/(app)/pagamentos/tesouraria/page.tsx` — novo; `app/(app)/pagamentos/page.tsx` (card liberar + stepper + links); `app/(app)/pagamentos/contas-a-pagar/page.tsx` e `[id]/page.tsx` (ajustes §4.4).

---

### Task 1: Backend — migration 0049 + liberar/revogar + guards novos (TDD)

**Files:** Create `backend/alembic/versions/0049_parcela_liberacao.py`, `backend/tests/test_pagamentos_liberacao.py`; Modify models/schemas, `pagamentos_autorizacao.py`, `pagamentos_caixa.py`, `pagamentos_dashboard.py`, testes existentes afetados.

**Interfaces produced:**
- `liberar_parcelas(db, *, tenant_id, usuario_id, parcela_ids: list[int], data_prevista: date | None = None, ip=None) -> list[Parcela]`
- `revogar_liberacao(db, *, tenant_id, usuario_id, parcela_id, justificativa, ip=None) -> Parcela`
- `pagar_parcela` exige LIBERADA; `estornar_parcela` reverte p/ A_PAGAR limpando os 3 campos.
- Parcela: `data_liberacao: date|None`, `id_usuario_liberacao: int|None`, `data_prevista_pagamento: date|None` (+ ParcelaOut).

- [ ] Migration 0049: ALTER CHECKs (parcela status + debhist acao: DROP+ADD com lista nova) + 3 colunas (date/date/FK utils.usuario nullable). Downgrade: reverte CHECKs (validar que não há linhas LIBERADAS antes — no downgrade, UPDATE LIBERADA→A_PAGAR primeiro) e dropa colunas. Roundtrip + SET ROLE.
- [ ] Testes RED (novos em test_pagamentos_liberacao.py, helpers copiados de test_pagamentos_autorizacao.py):
  1. liberar 2 parcelas de débitos distintos → LIBERADA, campos preenchidos, histórico LIBERADO em cada débito;
  2. liberar parcela de débito APROVADO (não autorizado) → 409, nenhuma liberada (all-or-nothing);
  3. pagar parcela A_PAGAR (não liberada) → 409; após liberar → paga OK;
  4. revogar liberação → A_PAGAR, campos limpos, histórico LIBERACAO_REVOGADA; revogar PAGA → 409;
  5. estornar parcela paga → volta A_PAGAR (não LIBERADA) e campos de liberação limpos;
  6. comprometido inclui LIBERADA (autorizar+liberar sem pagar → comprometido inalterado).
- [ ] Ajustar testes existentes que pagam direto (test_pagamentos_autorizacao: inserir liberar antes de pagar; test_pagamentos_dashboard idem).
- [ ] GREEN + regressão do módulo completa. Commit: `feat(pagamentos): liberação de pagamento — parcela LIBERADA, revogação e guards do rito completo`

### Task 2: Backend — filas agregadas + endpoints + minha-fila (TDD)

**Files:** Create `backend/app/services/pagamentos_filas.py`; Modify schemas, `routers/pagamentos_debitos.py`, testes (novo arquivo `test_pagamentos_filas.py`).

**Payloads (schemas novos — contratos p/ o frontend):**
```python
class DebitoFilaItem(BaseModel):
    id: int; nome_fornecedor: str; descricao: str; natureza_codigo: str
    natureza_descricao: str; competencia: str; urgente: bool
    aprovado_por: str | None; aprovado_em: datetime | None; valor_total: Decimal

class ParcelaFilaLibItem(BaseModel):
    id: int; id_debito: int; nome_fornecedor: str; descricao_debito: str
    numero: int; qtd_parcelas: int; valor: Decimal; vencimento: date
    vencida: bool; dias_atraso: int; op_numero: str | None; op_id: int | None

class ParcelaTesourariaItem(ParcelaFilaLibItem):
    data_liberacao: date | None; liberado_por: str | None
    data_prevista_pagamento: date | None

class GrupoConta(BaseModel):
    id_conta: int; nome_conta: str; disponivel: Decimal; abaixo_minimo: bool

class FilaAutorizacaoGrupo(GrupoConta):
    debitos: list[DebitoFilaItem]

class FilaLiberacaoGrupo(GrupoConta):
    parcelas: list[ParcelaFilaLibItem]

class FilaTesourariaOut(BaseModel):
    liberadas: list[ParcelaTesourariaItem]      # ordenadas por data_prevista/vencimento
    pagas_recentes: list[ParcelaTesourariaItem] # últimas 15, com data_pagamento no lugar
```
- [ ] Service `pagamentos_filas.py`: `fila_autorizacao(db,*,tenant_id) -> list[FilaAutorizacaoGrupo]` (APROVADO agrupado por conta, urgentes primeiro depois competência asc; aprovado_por/em = última ação APROVADO do histórico + nomes_usuarios), `fila_liberacao(...) -> list[FilaLiberacaoGrupo]` (A_PAGAR de AUTORIZADO|PAGO_PARCIAL, op via ordem_pagamento_debito mais recente do débito), `fila_tesouraria(...) -> FilaTesourariaOut`.
- [ ] Rotas: GET `/pagamentos/autorizacao/fila` (perm autorizar), GET `/pagamentos/liberacao/fila` (autorizar), GET `/pagamentos/tesouraria/fila` (pagar), POST `/pagamentos/parcelas/liberar` (body `{parcela_ids: list[int], data_prevista?: date}`, perm autorizar), POST `/pagamentos/parcelas/{id}/revogar-liberacao` (body JustificativaIn, perm autorizar). `minha-fila`: bucket novo `liberar: list[ParcelaFila] | None` (perm autorizar) e `pagar` passa a listar só LIBERADAS.
- [ ] Testes service-level das 3 filas (cenário com 2 contas, urgente, aprovador nomeado, OP presente) + guards das rotas cobertos por service. GREEN + regressão. Commit: `feat(pagamentos): filas agregadas por conta (autorização/liberação/tesouraria) + liberar em lote via API`

### Task 3: Seed + verificação de massa

- [ ] `seed_pagamentos_demo.py`: fluxo PAGO/PAGO_PARCIAL agora libera (data_prevista = vencimento) antes de pagar; criar ~15 parcelas LIBERADAS não pagas (metade vencidas) e manter A_PAGAR não liberadas nos AUTORIZADOS restantes. Re-rodar `--tenant sobral --reset`; resumo com contagens por estado de parcela (assert: ≥10 LIBERADAS pendentes, ≥20 A_PAGAR liberáveis).
- [ ] Regressão módulo. Commit: `feat(pagamentos): seed com o passo de liberação do rito`

### Task 4: Frontend — RitoPagamento + Sidebar + api.ts

- [ ] `components/pagamentos/RitoPagamento.tsx`: props `{ atual: "solicitar"|"aprovar"|"autorizar"|"liberar"|"pagar", concluidos?: string[] }`; linha horizontal dos 5 passos (número pequeno em círculo + rótulo), atual em cor da marca (fundo soft), concluídos com ✓ muted, demais muted; responsivo (rótulos somem em <sm, ficam só números com title); sem animação.
- [ ] Sidebar: suporte a `children?: NavItem[]` num item (subgrupo colapsável com chevron, useState); grupo Pagamentos reescrito conforme spec §2 (7 itens, Cadastros ▸ com os 6 filhos). Ícones já importados; "Tesouraria" usa `Banknote` ou `HandCoins` (importar de lucide se preciso).
- [ ] api.ts: tipos dos payloads da Task 2 (Decimal→string, date→string) + `api.pagamentos.filas.{autorizacao,liberacao,tesouraria}()`, `api.pagamentos.parcelas.liberar(ids, dataPrevista?)`, `.revogarLiberacao(id, justificativa)`; `MinhaFila.liberar`.
- [ ] tsc. Commit: `feat(pagamentos): stepper do rito, menu reorganizado com cadastros colapsados e client das filas`

### Task 5: Frontend — Autorizações (rebuild) + Tesouraria (nova)

- [ ] `/pagamentos/autorizacao`: reescrever conforme spec §4.1 — Tabs (segmented control) **Despesa | Pagamento**; componente compartilhado `GrupoContaCard` (cabeçalho: nome, disponível destacado, Σ selecionado, barra de consumo com cores; checkbox de grupo; badge abaixo-mínimo); linhas conforme spec (sem links azuis; fornecedor semibold foreground; ícone discreto → detalhe); barra sticky inferior (Σ + botão primário); dialog de confirmação (Despesa: o atual; Pagamento: resumo + campo data prevista). Estados vazios com direção ("Nada aguardando — os débitos aprovados aparecem aqui").
- [ ] `/pagamentos/tesouraria`: nova conforme spec §4.2 — grupos Atrasadas/Hoje/Esta semana/Depois (por data_prevista ?? vencimento), linha com [Pagar] individual (dialog atual) + lote; tab OPs emitidas (tabela movida da autorização, PDF); tab/seção Pagas recentemente com [Estornar].
- [ ] tsc. Commit: `feat(pagamentos): autorizações em duas etapas (despesa/pagamento) agrupadas por conta + tela da tesouraria`

### Task 6: Frontend — Visão geral + Contas a pagar (ajustes)

- [ ] Home: stepper no topo (sem passo aceso — legenda, prop `atual` opcional); card novo "Pagamentos a liberar" (bucket liberar) entre autorizar e pagar; links "abrir tela →" por card (aprovação→/pagamentos/contas-a-pagar; autorizar→/pagamentos/autorizacao; liberar→/pagamentos/autorizacao?tab=pagamento; pagar→/pagamentos/tesouraria); a tab da autorização deve ler `?tab=` via useSearchParams.
- [ ] Contas a pagar lista: filtros como segmented control; badge de status como primeira coluna; fornecedor sem link (linha clicável). Detalhe: `RitoPagamento` com `concluidos` derivado do status; parcela LIBERADA com badge info + "liberada por X em Y"; botão Pagar só em LIBERADA (some em A_PAGAR, com hint "aguardando liberação").
- [ ] tsc. Commit: `feat(pagamentos): visão geral com o rito completo + contas a pagar legível`

### Task 7: Verificação e2e (controller)

- [ ] Regressão completa + tsc. Browser (3 papéis, tema claro E escuro): rito completo com liberação; revogação; estorno exige re-liberar; menu novo; stepper; grupos por conta com barra de consumo; sem overflow horizontal em nenhuma tela. Screenshots. Ledger.

## Self-review
- Spec §1↔Task 1, §2↔Task 4, §3↔Task 4, §4.1↔Task 5, §4.2↔Task 5, §4.3↔Task 6, §4.4↔Task 6, §5↔Tasks 1-3. Payloads da Task 2 = tipos da Task 4. Bucket liberar usado na Task 6.
- Sem placeholder: payloads completos; regras de agrupamento/ordenação explícitas; guards enumerados.
