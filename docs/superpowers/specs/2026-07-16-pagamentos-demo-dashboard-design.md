# Pagamentos — Massa de dados demo + Dashboard do gestor financeiro (design)

## Context

O módulo Pagamentos (R1+R2, mergeado em `23af43d`) está funcional mas quase vazio — difícil
demonstrar. O Jorge pediu: (1) **dados fictícios coerentes e volumosos** para deixar o sistema
demonstrável; (2) um **dashboard gerencial** do módulo para o gestor financeiro da prefeitura
acompanhar saldo, principais débitos e indicadores.

Decisões (AskUserQuestion 2026-07-16): dashboard com os 4 blocos (KPIs, fluxo mensal, despesa
por natureza/fonte, maiores débitos + alertas); seed de **12 meses / ~200 débitos**; seed como
**script commitado** e re-executável.

## 1. Seed demo — `backend/scripts/seed_pagamentos_demo.py`

- Execução: `docker exec aprimora-py-backend python -m scripts.seed_pagamentos_demo --tenant sobral`
  (+ `--reset` para limpar os dados do módulo no tenant e re-semear). Engine/sessão no padrão do
  `backend/tests/conftest.py` (admin engine), tenant resolvido por slug.
- **Idempotência:** marcador = natureza demo `3.3.90.30` + fornecedor com CNPJ do bloco demo;
  se presente e sem `--reset`, aborta com instrução. `--reset` apaga TODOS os dados do módulo
  pagamentos daquele tenant (ordem FK-correta) antes de re-semear — comportamento documentado
  no help do script.
- **Atores:** garante os usuários demo `aprovador.pag@local.test` e `autorizador.pag@local.test`
  (clonando a senha do admin do tenant, como no e2e do R2) + alçada geral (R$ 500.000) para o
  autorizador. Workflow SEMPRE via services (criar_debito/enviar/aprovar/autorizar_lote/
  pagar_parcela) — nunca INSERT bruto nas tabelas de negócio — para gerar trilha, OPs e
  movimentações legítimas.
- **Massa (random com seed fixo p/ reprodutibilidade):**
  - ~35 fornecedores com nomes/CNPJs fictícios plausíveis (construtoras, distribuidoras de
    alimentos/medicamentos, laboratórios, gráficas, TI, transporte, engenharia, limpeza urbana,
    combustíveis…), 2-3 com situação PENDENTE/IRREGULAR + motivo (demonstra compliance).
  - 12 naturezas com códigos orçamentários reais (3.3.90.30 material de consumo, 3.3.90.39
    serviços PJ, 3.3.90.36 serviços PF, 4.4.90.51 obras, 4.4.90.52 equipamentos, 3.3.90.14
    diárias, 3.3.90.33 passagens, 3.3.90.40 TI, 3.3.90.46 auxílio-alimentação, 3.3.90.47
    obrigações tributárias, 3.1.90.11 vencimentos, 3.3.90.92 exercícios anteriores).
  - 5 fontes padrão STN (1.500 recursos próprios, 1.540 FUNDEB, 1.600 SUS, 1.621 transferências
    FNDE, 1.700 convênios) com grupos permitidos coerentes.
  - 6 contas: Movimento, Folha, FUNDEB, FMS Saúde, Obras/Convênios, Reserva — saldos iniciais
    variados (300k–2M) e saldo_minimo_alerta > 0 (uma conta deve ficar abaixo do mínimo para
    demonstrar o alerta).
  - ~10 contratos amarrados a fornecedores/unidade.
  - **12 meses (ago/2025→jul/2026):** entradas mensais por conta (APORTE "Duodécimo",
    RECEITA "Transferência FUNDEB/FPM/SUS") + ~200 débitos com competências espalhadas,
    parcelas 1–4x, valores 800–250.000. Distribuição de status: ~65% PAGO, ~8% PAGO_PARCIAL,
    ~8% AUTORIZADO, ~6% APROVADO, ~5% AGUARDANDO_APROVACAO, ~4% RASCUNHO, ~4%
    REJEITADO/CANCELADO (com justificativas plausíveis). Alguns débitos urgentes.
  - Datas: `parcela.vencimento` e `pagar_parcela(data_pagamento=...)` retroativos (a
    movimentação herda a data) → fluxo mensal e "pago no mês" ficam corretos; `criado_em`
    NOW é aceitável para demo. Algumas parcelas A_PAGAR com vencimento passado (vencidas) e
    outras nos próximos 7/30 dias.
  - **Invariante:** entradas mensais dimensionadas para o saldo de cada conta nunca ficar
    negativo nem o disponível impedir as autorizações do próprio seed.

## 2. Dashboard — backend

- `GET /api/v2/pagamentos/dashboard?meses=12` (default 12, clamp 3–24), permissão
  `require_any_permission("pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar",
  "pagamento_pagar", "pagamento_cadastro")`.
- Service novo `backend/app/services/pagamentos_dashboard.py`, agregações SQL (GROUP BY,
  `date_trunc('month', data)`), Decimal fim-a-fim. Payload único (`DashboardOut`):
  - `kpis`: saldo_total, disponivel_total, comprometido_total, a_pagar_30d, vencidas_qtd,
    vencidas_valor, pago_no_mes, aguardando_aprovacao_qtd, aguardando_autorizacao_qtd.
  - `fluxo_mensal[]`: {mes 'YYYY-MM', entradas, saidas} — janela de `meses`.
  - `por_natureza[]`: Σ movimentações PAGAMENTO na janela por natureza (top 6 + "Outras"),
    {codigo, descricao, valor}.
  - `por_fonte[]`: idem por fonte da conta do débito, {codigo, descricao, valor}.
  - `maiores_debitos[]`: top 10 em aberto (AGUARDANDO_APROVACAO/APROVADO/AUTORIZADO/
    PAGO_PARCIAL) por valor_total, com nome_fornecedor e status.
  - `alertas`: parcelas_vencidas[] (top 10, com dias de atraso), parcelas_7dias[],
    contas_abaixo_minimo[] (nome, saldo_atual, minimo).
- Testes service-level (cenário mínimo construído via services, asserts nos agregados).

## 3. Dashboard — frontend

- Página `frontend/app/(app)/pagamentos/dashboard/page.tsx`; item **Dashboard** no grupo
  Pagamentos do Sidebar (anyOf das 5 permissões), entre Início e Contas a pagar.
- Recharts (já usado no dashboard do GED). Regras da skill dataviz aplicadas:
  - Fluxo mensal: **barras pareadas** entradas×saídas (verde/vermelho semânticos, mesmos do
    caixa), legenda, tooltip, eixo único, `tabular-nums`.
  - Natureza e Fonte: **barras horizontais** (magnitude → barra, não pizza), hue única da
    marca, rótulos diretos com valores BRL.
  - Paleta validada com `scripts/validate_palette.js` da skill (par verde/vermelho + hue da
    marca, modos light e dark).
  - KPIs como stat tiles (número hero + label), alertas com cor de status + ícone (nunca só
    cor). Vencidas em danger.
- Filtro único: período (6/12/24 meses) → refaz a query.

## Fora de escopo

Exportação (PDF/planilha) do dashboard, comparativo orçado×realizado, drill-down por unidade
gestora — candidatos ao R3 junto com conciliação/transparência/relatórios.

## Verificação

1. Seed no tenant sobral → contagens (~35/12/5/6/~200) + saldo de cada conta ≥ 0 + pelo menos
   uma conta abaixo do mínimo + parcelas vencidas existentes.
2. Suíte backend + testes novos verdes; tsc limpo.
3. Browser: dashboard renderiza os 4 blocos com os dados do seed; filtro de período funciona;
   home/caixa/contas-a-pagar continuam consistentes com a massa nova.
