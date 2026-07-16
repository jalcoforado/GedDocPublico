# Pagamentos — Autorização do pagamento (liberação de parcela) + redesign de UX do módulo

## Context

Feedback do Jorge testando com a massa demo: (1) as telas operacionais estão "confusas,
difíceis de ler, difíceis de localizar"; (2) **falta o segundo ato do rito da Lei 4.320/64**
— o módulo tem autorização da DESPESA (débito→AUTORIZADO+OP), mas não a autorização do
PAGAMENTO (liberar cada parcela para a tesouraria executar).

Decisões (AskUserQuestion 2026-07-16): novo passo **liberar parcela** (estado LIBERADA);
redesign do **módulo inteiro** (navegação + telas operacionais). Decisão do controller:
liberar usa a MESMA permissão `pagamento_autorizar` (ordenador) — ato distinto na trilha,
não papel novo.

## 1. Fluxo — o rito completo

```
DÉBITO:  RASCUNHO → AGUARDANDO_APROVACAO → APROVADO → AUTORIZADO → PAGO_PARCIAL → PAGO
PARCELA:                                   A_PAGAR → LIBERADA → PAGA   (+ CANCELADA)
```

- **liberar_parcela(s)** (ordenador, `pagamento_autorizar`): parcela A_PAGAR de débito
  AUTORIZADO|PAGO_PARCIAL → LIBERADA. Campos novos na parcela: `data_liberacao` (date),
  `id_usuario_liberacao` (FK), `data_prevista_pagamento` (date, opcional — quando a
  tesouraria deve executar). Histórico do débito: ação `LIBERADO` ("Parcela N liberada").
  Em lote (várias parcelas de vários débitos numa chamada).
- **revogar_liberacao** (ordenador): LIBERADA (não paga) → A_PAGAR, limpa os campos,
  histórico `LIBERACAO_REVOGADA` com justificativa.
- **pagar_parcela** (tesouraria): agora EXIGE status LIBERADA (409 para A_PAGAR).
- **estornar_parcela**: parcela volta para **A_PAGAR** (a re-liberação é exigida de novo)
  e limpa também os campos de liberação.
- **comprometido** (caixa/dashboard): passa a somar parcelas `IN ('A_PAGAR','LIBERADA')`.
  KPIs vencidas/a_pagar_30d idem. `minha-fila`: bucket `pagar` (tesouraria) = só LIBERADAS;
  bucket novo `liberar` (ordenador) = A_PAGAR de débitos AUTORIZADO|PAGO_PARCIAL.
- Migration **0049**: ALTER `pagamentos.parcela` — widen CHECK de status (+'LIBERADA'),
  + 3 colunas; sem tabela nova (RLS já cobre). Reversível.
- Seed demo: passa a liberar antes de pagar; deixa ~15 parcelas LIBERADAS não pagas
  (fila da tesouraria) e mantém A_PAGAR não liberadas (fila do ordenador).

## 2. Navegação — menu Pagamentos enxuto

De 11 itens planos para 7, na ordem do trabalho:

| Item | Rota | Quem vê (anyOf) |
|---|---|---|
| Visão geral | `/pagamentos` (home renovada) | qualquer papel do módulo |
| Dashboard | `/pagamentos/dashboard` | qualquer papel |
| Contas a pagar | `/pagamentos/contas-a-pagar` | solicitar/aprovar/autorizar/pagar |
| Autorizações | `/pagamentos/autorizacao` (tabs Despesa · Pagamento) | pagamento_autorizar |
| Tesouraria | `/pagamentos/tesouraria` | pagamento_pagar |
| Caixa | `/pagamentos/caixa` | pagamento_cadastro |
| Cadastros ▸ | submenu colapsado (fornecedores, naturezas, fontes, contas, contratos, alçadas) | pagamento_cadastro |

O Sidebar ganha suporte a **subgrupo colapsável** dentro do grupo (padrão simples:
item "Cadastros" expande/colapsa os 6 filhos; persistir aberto/fechado em useState).

## 3. Assinatura visual — o stepper do rito

Componente `RitoPagamento` no topo de cada tela operacional: os 5 passos
*Solicitar → Aprovar → Autorizar despesa → Liberar pagamento → Pagar* como uma linha
discreta (números pequenos + rótulos), com o passo da tela atual aceso na cor da marca e
os demais em muted. Ele conta onde a tela está no fluxo — é wayfinding, não decoração.
No detalhe do débito, o stepper reflete o STATUS do débito (passos concluídos com check).

## 4. Telas (redesign)

Princípios (frontend-design + dataviz, aplicados ao design system existente): hierarquia
tipográfica clara (título > grupo > linha), metadados em muted, valores em `tabular-nums`
alinhados à direita, nada de link azul em texto corrido (ação = botão/ícone; nome =
foreground), barras de ação **fixas** (sticky bottom) nos fluxos de lote, agrupamento
que espelha o raciocínio do usuário, estados vazios orientando a próxima ação.

### 4.1 Autorizações (`/pagamentos/autorizacao`) — tabs **Despesa** | **Pagamento**
- **Tab Despesa** (fila APROVADO, agrupada POR CONTA): cada grupo = card com cabeçalho
  [nome da conta · disponível em destaque · Σ selecionado · barra de consumo
  (Σ/disponível, âmbar >80%, vermelha >100%)] + "selecionar grupo"; linhas: checkbox,
  fornecedor (foreground, semibold), natureza (código, tooltip descrição), competência,
  **aprovado por + quando** (muted, vem do novo endpoint), selo URGENTE, valor.
  Urgentes primeiro, depois competência asc. Barra fixa: "N débitos · Σ R$ X ·
  [Autorizar despesas (gerar OP)]" → dialog de confirmação atual (Σ por conta vs
  disponível) mantido.
- **Tab Pagamento** (fila de liberação): parcelas A_PAGAR de débitos AUTORIZADO|
  PAGO_PARCIAL, agrupadas POR CONTA (mesmo padrão de grupo), linhas: checkbox,
  fornecedor, parcela N/QT, vencimento (vencida em danger com dias de atraso), OP de
  origem (numero, link PDF), valor. Campo opcional "data prevista de pagamento" na barra
  fixa. Ação: [Liberar pagamentos] → dialog resumo → `liberar` em lote. Linhas LIBERADAS
  não aparecem aqui (foram para a Tesouraria).
- Seção "Ordens de Pagamento emitidas" sai desta tela → vira tab/tabela na Tesouraria.

### 4.2 Tesouraria (`/pagamentos/tesouraria`) — nova tela
- Fila = parcelas **LIBERADAS**, agrupadas por **data prevista/vencimento** (Atrasadas ·
  Hoje · Esta semana · Depois), linhas: fornecedor, débito (descrição truncada), OP,
  liberado por/quando, valor; ação por linha [Pagar] (dialog forma+data atual) e lote
  [Pagar selecionadas] (sequência de chamadas, toast agregado).
- Segunda tab: **OPs emitidas** (a tabela que estava na autorização, com PDF).
- Terceira seção/tab: **Pagas recentemente** (últimas 15, com botão Estornar).

### 4.3 Visão geral (`/pagamentos`) — home renovada
- Stepper do rito no topo como legenda do módulo.
- Cards de fila por papel (mantidos, já compactados) reordenados na ordem do rito, cada
  um com link "abrir tela" para a tela da etapa (aprovação→contas a pagar?; autorizar→
  Autorizações tab Despesa; liberar→tab Pagamento (card novo); pagar→Tesouraria).
- Seção caixa compacta mantida.
- `minha-fila` ganha bucket `liberar` (para o card novo).

### 4.4 Contas a pagar — ajustes leves
- Lista: tirar link azul do fornecedor (linha inteira clicável já existe), status badge
  primeiro à esquerda com cor, filtros como segmented control em vez de select.
- Detalhe: stepper do rito refletindo o débito; seção parcelas mostra estado LIBERADA
  (badge própria, info) e quem liberou.

## 5. Backend — resumo das mudanças

- Migration 0049 (ALTER parcela: CHECK + data_liberacao/id_usuario_liberacao/
  data_prevista_pagamento).
- `pagamentos_autorizacao.py`: `liberar_parcelas(db, *, tenant_id, usuario_id,
  parcela_ids, data_prevista=None, ip=None)` (lote, all-or-nothing, guards: débito
  AUTORIZADO|PAGO_PARCIAL, parcela A_PAGAR, histórico LIBERADO por débito),
  `revogar_liberacao(... justificativa ...)`, `pagar_parcela` exige LIBERADA,
  `estornar_parcela` reverte para A_PAGAR limpando liberação.
- `pagamentos_caixa.comprometido_conta`: status IN ('A_PAGAR','LIBERADA').
- `pagamentos_dashboard`: vencidas/a_pagar_30d incluem LIBERADA.
- Endpoint novo `GET /pagamentos/autorizacao/fila` → grupos por conta com débitos
  APROVADO enriquecidos (aprovado_por/aprovado_em via histórico, natureza codigo, conta
  nome, disponivel da conta); `GET /pagamentos/liberacao/fila` → grupos por conta com
  parcelas A_PAGAR liberáveis (+ numero da OP); `GET /pagamentos/tesouraria/fila` →
  parcelas LIBERADAS (+ liberado_por, OP) e pagas recentes. `POST /pagamentos/parcelas/
  liberar` (lote) e `POST /pagamentos/parcelas/{id}/revogar-liberacao`.
- `minha-fila`: bucket `liberar`; bucket `pagar` = LIBERADAS.
- Histórico: ações novas LIBERADO / LIBERACAO_REVOGADA (widen CHECK da 0048? o CHECK
  `ck_debhist_acao` lista ações — precisa ALTER na 0049).
- Seed: liberar antes de pagar; deixar ~15 LIBERADAS pendentes.
- Testes: transições novas + guards + estorno reverte liberação + comprometido inclui
  LIBERADA + filas.

## Fora de escopo
Assinatura digital da liberação, papéis separados p/ liberar (fica em pagamento_autorizar),
notificações. R3 continua: conciliação/transparência/relatórios.

## Verificação
1. Regressão + testes novos verdes; tsc 0.
2. Browser (3 papéis): rito completo com o passo novo — criar→aprovar→autorizar (OP)→
   **liberar**→pagar na Tesouraria; estorno exige re-liberação; menu novo com Cadastros
   colapsado; stepper presente nas telas.
3. Legibilidade: nenhuma tela com overflow horizontal; grupos por conta com Σ e barra.
