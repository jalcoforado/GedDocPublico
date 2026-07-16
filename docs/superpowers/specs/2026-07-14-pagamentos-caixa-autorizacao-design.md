# Pagamentos — Controle de caixa + autorização (design revisado)

> **Supersede** `2026-07-13-pagamentos-pag1-cadastros-design.md`. Após feedback: o
> valor do módulo é **controlar o caixa da prefeitura** (lançar débitos, aprovar/
> autorizar, pagar deduzindo do saldo), não um conjunto de cadastros CRUD. Este
> documento redefine o modelo e o faseamento. Reaproveita o backend já testado do
> PAG-1 (migration 0045, RLS, conta/natureza/fonte/contrato/alçada).

## Context

O objetivo real: **fluxo de caixa** de uma prefeitura — cada conta bancária tem um
saldo; entram recursos (aportes/receitas) e saem pagamentos, que **deduzem do saldo**;
os pagamentos passam por um fluxo de **autorização** (segregação de funções + alçada)
antes de saírem. O que foi entregue antes (6 telas de cadastro) era só a base e não
mostrava o caixa funcionando.

Decisões (feedback + brainstorming 2026-07-14):
- **`credor` → `fornecedor`**: a base é o **Fornecedor**; "credor" é apenas o papel do
  fornecedor referenciado por um débito. Não existe entidade "credor".
- **Débito com parcelas**: uma despesa/compromisso pode ter 1+ **parcelas**, cada uma
  com vencimento e paga individualmente (cada pagamento deduz o saldo).
- **3 níveis**: solicitante → secretário **aprova** → autorizador **autoriza** (gera
  Ordem de Pagamento, checa saldo/alçada/segregação) → tesouraria **paga**. Autorização
  em lote.
- **Entradas + saldo inicial**: conta tem saldo inicial e aceita lançamentos de entrada
  (aporte/receita) e saída (ajuste), além dos pagamentos.
- **Home = fila "o que precisa de mim"** (por papel); caixa/extrato/contas-a-pagar em
  seções/abas.
- **Aproveitar e refatorar** o PAG-1: manter conta/natureza/fonte/contrato/alçada;
  renomear credor→fornecedor; adicionar o núcleo financeiro.
- **Faseamento R1 → R2** (cada um entrega algo usável).

## Modelo de dados (schema `pagamentos`)

### Cadastros (reaproveitados)
- **`fornecedor`** (rename de `credor`): `tipo_pessoa`, `cnpj_cpf`, `nome`,
  `situacao_cadastral`, `motivo_pendencia`, dados bancários cifrados (Fernet).
- **`natureza_despesa`**, **`fonte_recursos`**, **`contrato`** (o `contrato.id_credor`
  vira `id_fornecedor`), **`alcada`** — sem mudança estrutural.
- **`conta_bancaria`**: **+ `saldo_inicial` Numeric(14,2) default 0**.

### Financeiro — R1
- **`movimentacao_conta`** (o extrato/razão): `id_conta`, `tipo` ('ENTRADA'|'SAIDA'),
  `valor` Numeric(14,2) (>0), `origem` ('APORTE'|'RECEITA'|'AJUSTE'|'PAGAMENTO'|'ESTORNO'),
  `id_debito?`, `id_parcela?`, `data` Date, `id_usuario`, `descricao`, timestamps, `excluido`.
  - **saldo_atual(conta)** = `saldo_inicial + Σ(ENTRADA) − Σ(SAIDA)` (não excluídos).
  - R1 usa lançamentos manuais ENTRADA (APORTE/RECEITA) e SAIDA (AJUSTE). PAGAMENTO/
    ESTORNO chegam no R2 (via pagamento de parcela).

### Débito + parcelas + workflow — R2
- **`debito`** (despesa/compromisso): `id_fornecedor`, `id_natureza`, `id_conta`,
  `id_contrato?`, `valor_total`, `competencia`, `numero_ne`, `numero_nf`, `criticidade`,
  `urgente`, `justificativa_urgencia`, `descricao`, `status`, `id_usuario_solicitante`,
  timestamps, `excluido`.
  - `status`: `RASCUNHO → AGUARDANDO_APROVACAO → APROVADO → AUTORIZADO → PAGO_PARCIAL →
    PAGO` (+ `DEVOLVIDO`, `REJEITADO`, `CANCELADO`). Workflow no nível do **débito**.
- **`parcela`**: `id_debito`, `numero` (1..N), `valor`, `vencimento`,
  `status` ('A_PAGAR'|'PAGA'|'CANCELADA'), `data_pagamento?`, `forma_pagamento?`,
  `comprovante?`, `id_movimentacao?` (a SAIDA gerada no pagamento), timestamps, `excluido`.
  - Σ(parcelas.valor) = `debito.valor_total` (validado no serviço).
- **`debito_historico`**: trilha imutável das transições (status_ant→novo, usuário, IP,
  justificativa, data).
- **`ordem_pagamento`**: `numero`, `id_usuario_autorizador`, N:N com débitos, `valor_total`,
  `ip_origem`. Gerada na autorização (art. 64, Lei 4.320/64; PDF assinável via WeasyPrint).

## Fluxo e regras (R2)

Transições no serviço (nunca direto no ORM), cada uma gravando `debito_historico`:
- **enviar_aprovacao** (solicitante): RASCUNHO → AGUARDANDO_APROVACAO. Exige ≥1 parcela e
  Σparcelas = valor_total.
- **aprovar / devolver / rejeitar** (aprovador): AGUARDANDO_APROVACAO → APROVADO |
  (RASCUNHO com motivo) | REJEITADO.
- **autorizar** (autorizador, em lote): APROVADO → AUTORIZADO. Checa:
  - **saldo**: `disponível(conta) = saldo_atual − comprometido ≥ valor_total`;
    `comprometido` = Σ valor de parcelas A_PAGAR de débitos AUTORIZADOS.
  - **alçada**: `alcada(autorizador, natureza).valor_maximo ≥ valor_total` (ou limite geral).
  - **segregação de funções**: autorizador ∉ {solicitante, aprovador} do débito (via histórico).
  - Gera `ordem_pagamento`.
- **pagar_parcela** (tesouraria): só se débito AUTORIZADO e parcela A_PAGAR. Cria
  `movimentacao_conta` SAIDA origem=PAGAMENTO → **deduz saldo** → parcela PAGA. Quando todas
  as parcelas pagas → débito PAGO (senão PAGO_PARCIAL).
- **cancelar / estornar**: cancelar débito não pago; estornar parcela paga cria
  movimentação ESTORNO (reverte o saldo) e reabre a parcela.

## RBAC (papéis)

Novas transações (super-usuário bypassa): `pagamento_solicitar`, `pagamento_aprovar`,
`pagamento_autorizar`, `pagamento_pagar` — além de `pagamento_cadastro` (já existe, para
os cadastros). Segregação de funções é reforçada no serviço via atores do histórico, não
só pela permissão.

## Telas (operacionais)

- **Home — "O que precisa de mim"** (por papel): solicitante (rascunhos/devolvidos),
  aprovador (fila de aprovação), autorizador (fila de autorização + **autorizar em lote**),
  tesouraria (parcelas a pagar / vencendo). *(R1 entrega a casca + a seção de caixa; as
  filas de débito populam no R2.)*
- **Caixa**: painel de saldos por conta (inicial / entradas / saídas / atual / comprometido
  / disponível) + **extrato** (movimentações) + **lançar entrada/ajuste**. *(R1)*
- **Contas a pagar**: criar débito (puxa fornecedor + parcelas), lista por status, **detalhe
  com parcelas + trilha de status + ações por papel**. *(R2)*
- **Cadastros** (configuração secundária, não é a cara do módulo): fornecedores, naturezas,
  fontes, contas, contratos, alçadas.

## Faseamento

- **R1 — Caixa visível**: refactor credor→fornecedor; `conta.saldo_inicial` +
  `movimentacao_conta`; lançar entrada (aporte/receita) e saída (ajuste); **extrato** por
  conta; **painel de caixa** (saldos). Entrega: contas com saldo mexendo (entra/sai) e
  extrato — testável ponta-a-ponta.
- **R2 — Débito + autorização + pagar**: `debito` + `parcela` + `debito_historico` +
  `ordem_pagamento`; workflow 3 níveis (solicitar→aprovar→autorizar→pagar) com saldo/alçada/
  segregação; **pagar parcela deduz do saldo** (movimentação PAGAMENTO); home "o que precisa
  de mim" populada + contas a pagar + autorização em lote + detalhe do débito.
- **R3+ (depois)**: conciliação bancária, transparência pública, relatórios de fluxo de caixa.

## Reuso (não reconstruir)
Migration/RLS/GRANTs (padrão 0043), CRUD pattern (transporte_regulado/minutas), Fernet
(`app/core/crypto.py`), Unidade (órgão), AuditLog, Notificação, Celery, WeasyPrint (OP em
PDF), Assinatura v2 (assinar OP). A migration de alteração (0046+) renomeia credor→fornecedor,
adiciona `conta.saldo_inicial` e cria `movimentacao_conta` (R1); débito/parcela/histórico/OP
entram na migration do R2.

## Riscos / atenção
- **Rename credor→fornecedor**: toca model/schema/service/router/tests/frontend + o FK
  `contrato.id_credor`→`id_fornecedor` + índices/uniques; RLS policies seguem a tabela no
  RENAME. Fazer numa migration dedicada com roundtrip.
- **Consistência do saldo**: `pagar_parcela` (cria movimentação + muda status) deve ser
  atômico; saldo é sempre derivado das movimentações (fonte única da verdade), nunca um
  contador denormalizado que possa divergir.
- **Segregação de funções**: precisa dos atores reais no histórico; garantir que
  solicitar/aprovar/autorizar gravem `id_usuario` corretamente.
- **Σparcelas = valor_total**: invariante validada no serviço (e idealmente CHECK/trigger não
  trivial — manter no serviço com teste).

## Verificação (por fase)
- **R1**: subir stack (localhost:8090, `admin@local.test`/`admin123`); criar conta com saldo
  inicial, lançar aporte (entrada) e ajuste (saída), conferir **saldo_atual** e **extrato**;
  painel de caixa mostra saldos; regressão backend verde; tsc limpo.
- **R2**: criar débito com parcelas → enviar → aprovar → autorizar (testar bloqueio por saldo,
  alçada e segregação) → pagar parcela (saldo baixa, movimentação PAGAMENTO) → débito
  PAGO/PAGO_PARCIAL; Ordem de Pagamento em PDF; fila "o que precisa de mim" por papel.
