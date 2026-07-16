# Pagamentos — Demo data + Dashboard do gestor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Popular o módulo com 12 meses de dados fictícios coerentes (~200 débitos, workflow real) e entregar o dashboard gerencial `/pagamentos/dashboard` (KPIs, fluxo mensal, despesa por natureza/fonte, maiores débitos, alertas).

**Architecture:** Seed roda os **services reais** do módulo (nunca INSERT bruto nas tabelas de negócio) com 3 atores demo, datas retroativas via `parcela.vencimento`/`pagar_parcela(data_pagamento=...)`. Dashboard é 1 endpoint agregador (SQL GROUP BY, Decimal) + 1 página recharts.

**Tech Stack:** FastAPI + SQLAlchemy async, pytest service-level, Next.js + recharts 3.8.1 + Tailwind, Docker.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-16-pagamentos-demo-dashboard-design.md` (valores de massa/decomposições copiados de lá).
- Testes: `docker exec aprimora-py-backend python -m pytest tests/<arquivo> -q`; tsc: `docker exec aprimora-py-frontend ./node_modules/.bin/tsc --noEmit`.
- Seed determinístico (`random.seed(42)`), idempotente (aborta se marcador presente; `--reset` limpa o módulo do tenant em ordem FK-correta e re-semeia).
- Saldo de NENHUMA conta pode ficar negativo em nenhum ponto; autorizações do seed não podem esbarrar no bloqueio por disponível (dimensionar entradas antes das saídas de cada mês).
- Dashboard: agregação SEMPRE no backend; Decimal (nunca float); janela por `date_trunc('month', movimentacao_conta.data)`.
- Dataviz (regras da skill, obrigatórias na Task 3): barras horizontais p/ natureza/fonte (não pizza); entradas verde `#16a34a` × saídas vermelho `#dc2626` (semântico, igual ao caixa); hue única da marca nas categorias; eixo único; tooltip em todo gráfico; legenda quando ≥2 séries; `tabular-nums`; texto em tokens de texto (nunca na cor da série); validar paleta com `node scripts/validate_palette.js` (base da skill dataviz em `C:\Users\Jorge\AppData\Local\Temp\claude\bundled-skills\2.1.210\3ad40c58a16fe02f65eaa9ef09610b20\dataviz`) nos modos light e dark.

## File Structure

- `backend/scripts/__init__.py` + `backend/scripts/seed_pagamentos_demo.py` — **novo**: seed CLI.
- `backend/app/services/pagamentos_dashboard.py` — **novo**: agregações.
- `backend/app/schemas/pagamentos.py` — modificar: schemas do dashboard.
- `backend/app/routers/pagamentos_debitos.py` — modificar: endpoint GET /pagamentos/dashboard no `operacoes_router`.
- `backend/tests/test_pagamentos_dashboard.py` — **novo**.
- `frontend/lib/api.ts` — modificar: tipos + `api.pagamentos.dashboard(meses)`.
- `frontend/app/(app)/pagamentos/dashboard/page.tsx` — **novo**.
- `frontend/components/Sidebar.tsx` — modificar: item Dashboard.

---

### Task 1: Seed demo (`seed_pagamentos_demo.py`)

**Files:**
- Create: `backend/scripts/__init__.py` (vazio), `backend/scripts/seed_pagamentos_demo.py`

**Interfaces:**
- Consumes: services `pagamentos_cadastros` (criar_fornecedor/natureza/fonte/conta/contrato/alcada), `pagamentos_debitos` (criar_debito/enviar_aprovacao/aprovar), `pagamentos_autorizacao` (autorizar_lote/pagar_parcela), `pagamentos_caixa` (lancar_movimentacao/saldo_conta); engine admin no padrão de `backend/tests/conftest.py` (LER o conftest para copiar o mecanismo de URL/engine); `provisionar_tenant` NÃO é usado (tenant já existe — resolver por slug em `aprimora_py.tenant`).
- Produces: comando `docker exec aprimora-py-backend python -m scripts.seed_pagamentos_demo --tenant sobral [--reset]`.

- [ ] **Step 1: Esqueleto CLI + resolução de tenant/atores**

Estrutura do script (argparse; asyncio.run; sessão admin):
- Resolve tenant por slug (erro claro se não existe).
- Resolve/garante atores: admin do tenant (primeiro usuário do grupo nível super, ou por email `admin@local.test` com fallback ao primeiro usuário); cria `aprovador.pag@local.test` / `autorizador.pag@local.test` se ausentes clonando `senha`/`senha_bcrypt`/`id_unidade_trabalho` do admin (INSERT com `data_criacao` — cuidado: a coluna NÃO é criado_em) + vínculo no mesmo grupo do admin + alçada geral 500000 p/ o autorizador (via `cad.criar_alcada`, ignorando 409 se já houver).
- Marcador de idempotência: existe `natureza_despesa` código `3.3.90.30` não-excluída no tenant → sem `--reset`, abortar com mensagem explicando `--reset`.
- `--reset`: DELETE em ordem FK-correta, tudo do tenant: `movimentacao_conta`(via UPDATE parcela SET id_movimentacao=NULL antes), `ordem_pagamento_debito`, `ordem_pagamento`, `debito_historico`, `parcela`, `debito`, `contrato`, `alcada`, `conta_bancaria`, `fonte_recursos`, `natureza_despesa`, `fornecedor_situacao_historico`, `fornecedor`. Imprime o que apagou.
- RLS: a sessão admin (superuser) bypassa; se o conftest usar role app, executar `SET app.tenant_id` — copiar o que os testes fazem.

- [ ] **Step 2: Cadastros base** — listas literais no script (dados da spec): 35 fornecedores (nome + CNPJ fictício formatado, 2 PENDENTE + 1 IRREGULAR com motivo), 12 naturezas (códigos da spec, criticidade variada), 5 fontes STN (grupos permitidos coerentes: FUNDEB→PESSOAL/CUSTEIO; convênios→INVESTIMENTO/CUSTEIO; etc.), 6 contas (saldos iniciais 300k–2M; `saldo_minimo_alerta` tal que a conta "Obras/Convênios" termine ABAIXO do mínimo), ~10 contratos. Tudo via services (usuario_id=admin p/ fornecedores).

- [ ] **Step 3: Linha do tempo (12 meses, ago/2025→jul/2026)**

Para cada mês m (do mais antigo ao atual):
1. Entradas: 1 APORTE "Duodécimo <mês>" + 1-2 RECEITA ("FPM", "FUNDEB", "SUS") por conta ativa, valores 80k–600k conforme a conta, `data` = dia 1-5 do mês (via `caixa.lancar_movimentacao` com payload MovimentacaoCreate).
2. Débitos do mês (total ~200 no período; sortear 14-20/mês): fornecedor/natureza/conta/contrato sorteados coerentes (natureza↔grupo da conta não é validado pelo serviço, mas manter plausível), valor 800–250.000 (distribuição log-ish: muitos pequenos, poucos grandes), 1-4 parcelas com vencimentos mensais a partir de competência+30d, alguns `urgente=True` com justificativa.
3. Fluxo por status sorteado (distribuição da spec):
   - PAGO: criar→enviar(admin)→aprovar(aprovador)→autorizar_lote(autorizador)→pagar TODAS as parcelas (`data_pagamento` = vencimento ± 0-5d, formas variadas).
   - PAGO_PARCIAL: idem, pagar só as primeiras parcelas.
   - AUTORIZADO: parar após autorizar (parcelas A_PAGAR — algumas com vencimento no passado ⇒ VENCIDAS, outras nos próximos 7/30 dias; concentrar esses nos 2 meses mais recentes).
   - APROVADO / AGUARDANDO_APROVACAO / RASCUNHO: parar no ponto correspondente (concentrar no mês corrente).
   - REJEITADO: enviar→rejeitar (justificativas plausíveis: "Sem dotação", "NF divergente").
   - CANCELADO: cancelar com justificativa.
4. **Guarda de saldo**: antes de autorizar/pagar em cada mês, checar `saldo_conta(...).disponivel` da conta; se insuficiente, lançar uma RECEITA extra "Suplementação" cobrindo a diferença + 20% (mantém o invariante sem distorcer o total).

- [ ] **Step 4: Resumo final** — imprimir tabela: contagens por entidade, débitos por status, saldo/comprometido/disponível por conta (asserts internos: nenhum saldo < 0; ≥1 conta abaixo do mínimo; ≥3 parcelas vencidas; ≥200 débitos).

- [ ] **Step 5: Rodar no tenant sobral** — `docker exec aprimora-py-backend python -m scripts.seed_pagamentos_demo --tenant sobral --reset` (o tenant tem dados de teste do e2e — o reset limpa). Colar o resumo no report. Rodar 2ª vez SEM --reset → deve abortar (idempotência). Regressão: `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_debitos.py tests/test_pagamentos_autorizacao.py -q` (o seed não pode quebrar nada — não toca em código de produção).

- [ ] **Step 6: Commit** — `feat(pagamentos): seed de dados demo (12 meses, workflow real) — scripts/seed_pagamentos_demo`

---

### Task 2: Backend do dashboard

**Files:**
- Create: `backend/app/services/pagamentos_dashboard.py`
- Modify: `backend/app/schemas/pagamentos.py`, `backend/app/routers/pagamentos_debitos.py`
- Test: `backend/tests/test_pagamentos_dashboard.py`

**Interfaces:**
- Consumes: models `MovimentacaoConta, Debito, Parcela, ContaBancaria, NaturezaDespesa, FonteRecursos, Fornecedor`; `caixa.saldo_conta`/`comprometido_conta`; `require_any_permission`.
- Produces: `montar_dashboard(db, *, tenant_id: int, meses: int = 12) -> DashboardOut`; rota `GET /pagamentos/dashboard` no `operacoes_router`.

- [ ] **Step 1: Schemas** (em `schemas/pagamentos.py`):

```python
class DashboardKpis(BaseModel):
    saldo_total: Decimal; disponivel_total: Decimal; comprometido_total: Decimal
    a_pagar_30d: Decimal; vencidas_qtd: int; vencidas_valor: Decimal
    pago_no_mes: Decimal; aguardando_aprovacao_qtd: int; aguardando_autorizacao_qtd: int


class FluxoMensalItem(BaseModel):
    mes: str  # 'YYYY-MM'
    entradas: Decimal; saidas: Decimal


class ComposicaoItem(BaseModel):
    codigo: str; descricao: str; valor: Decimal


class DebitoResumoItem(BaseModel):
    id: int; nome_fornecedor: str; descricao: str; valor_total: Decimal
    status: StatusDebito; competencia: str


class ParcelaAlertaItem(BaseModel):
    id: int; id_debito: int; nome_fornecedor: str; valor: Decimal
    vencimento: date; dias_atraso: int


class ContaAlertaItem(BaseModel):
    id_conta: int; nome: str; saldo_atual: Decimal; saldo_minimo_alerta: Decimal


class DashboardAlertas(BaseModel):
    parcelas_vencidas: list[ParcelaAlertaItem]
    parcelas_7dias: list[ParcelaAlertaItem]
    contas_abaixo_minimo: list[ContaAlertaItem]


class DashboardOut(BaseModel):
    kpis: DashboardKpis
    fluxo_mensal: list[FluxoMensalItem]
    por_natureza: list[ComposicaoItem]
    por_fonte: list[ComposicaoItem]
    maiores_debitos: list[DebitoResumoItem]
    alertas: DashboardAlertas
```

- [ ] **Step 2: Testes que falham** (`tests/test_pagamentos_dashboard.py`, padrão dos demais: `_provisionar` + helpers copiados de `test_pagamentos_autorizacao.py`): cenário mínimo — 1 conta saldo 10000, 1 entrada 2000 no mês corrente, 1 débito 2 parcelas (600 paga mês corrente, 400 a pagar vencida ontem):
  - `test_kpis`: saldo_total=11400, comprometido=400, disponivel=11000, pago_no_mes=600, vencidas_qtd=1/valor=400.
  - `test_fluxo_mensal`: mês corrente com entradas=2000 e saidas=600; lista tem `meses` itens (zeros preenchidos).
  - `test_por_natureza_e_fonte`: 1 item cada com valor 600.
  - `test_maiores_e_alertas`: débito aparece em maiores_debitos (PAGO_PARCIAL); parcela vencida em alertas com dias_atraso=1.
  RED esperado: ModuleNotFoundError.

- [ ] **Step 3: Service** — agregações (sketch; completar no padrão do módulo):

```python
async def montar_dashboard(db, *, tenant_id: int, meses: int = 12) -> DashboardOut:
    meses = max(3, min(24, meses))
    hoje = _utcnow().date()
    inicio = (hoje.replace(day=1) - relativedelta(months=meses - 1))  # ou aritmética manual ano/mês (sem dateutil se não estiver no lock — VERIFICAR; senão calcular com divmod)
    # fluxo mensal: SELECT to_char(date_trunc('month', data),'YYYY-MM'), tipo, SUM(valor)
    #   WHERE tenant, not excluido, data >= inicio GROUP BY 1,2 → preencher meses vazios com 0.
    # kpis: reusar caixa.saldo_conta por conta ativa (Σ saldo_atual/comprometido/disponivel);
    #   pago_no_mes: SUM movimentacao PAGAMENTO com date_trunc('month', data)=mês corrente;
    #   a_pagar_30d / vencidas: SUM/COUNT parcelas A_PAGAR (join débito AUTORIZADO|PAGO_PARCIAL)
    #     com vencimento <= hoje+30 / < hoje;
    #   contadores: COUNT débitos por status AGUARDANDO_APROVACAO / APROVADO.
    # por_natureza: SUM(mov.valor) JOIN debito ON mov.id_debito JOIN natureza,
    #   mov.origem='PAGAMENTO', janela; ORDER BY sum DESC → top 6 + item {'—','Outras', resto}.
    # por_fonte: idem via debito.id_conta → conta.id_fonte_recursos → fonte.
    # maiores_debitos: top 10 status IN (AGUARDANDO_APROVACAO, APROVADO, AUTORIZADO,
    #   PAGO_PARCIAL) ORDER BY valor_total DESC (nome via nomes_fornecedores).
    # alertas: parcelas vencidas (limit 10, dias_atraso=(hoje-venc).days) e vencendo ≤7d;
    #   contas: saldo_atual < saldo_minimo_alerta (via painel_caixa).
```

(Import de `relativedelta` só se `python-dateutil` já for dependência — verificar `pyproject.toml`; caso contrário, calcular o mês inicial com aritmética simples de ano/mês.)

- [ ] **Step 4: Rota** — no `operacoes_router` (arquivo `routers/pagamentos_debitos.py`):

```python
@operacoes_router.get("/dashboard", response_model=DashboardOut)
async def dashboard(meses: int = 12,
                    _: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                    tenant_id: int = Depends(require_tenant_id),
                    db: AsyncSession = Depends(get_db)):
    return await dash.montar_dashboard(db, tenant_id=tenant_id, meses=meses)
```

- [ ] **Step 5: GREEN + regressão** — `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_dashboard.py tests/test_pagamentos_caixa.py tests/test_pagamentos_autorizacao.py -q`.

- [ ] **Step 6: Commit** — `feat(pagamentos): endpoint agregador do dashboard financeiro`

---

### Task 3: Frontend do dashboard

**Files:**
- Modify: `frontend/lib/api.ts`, `frontend/components/Sidebar.tsx`
- Create: `frontend/app/(app)/pagamentos/dashboard/page.tsx`

**Interfaces:**
- Consumes: `GET /pagamentos/dashboard?meses=` (payload DashboardOut — Decimals chegam como string); recharts (`BarChart`, `Bar`, `XAxis`, `YAxis`, `Tooltip`, `Legend`, `ResponsiveContainer`) — ver uso existente em `frontend/app/(app)/dashboard/page.tsx`; padrão visual dos cards/tabelas de `frontend/app/(app)/pagamentos/page.tsx`.

- [ ] **Step 1: api.ts** — tipos espelhando DashboardOut (Decimal→string) + `dashboard: (meses = 12) => request<PagamentosDashboard>(`/pagamentos/dashboard${qs({ meses })}`)` dentro de `pagamentos`.

- [ ] **Step 2: Página** — requisitos (seguir dataviz, constraints globais):
  - Header: título "Dashboard financeiro" + Select de período (6/12/24 meses) que refaz a query (`["pag-dashboard", meses]`).
  - Linha 1 — stat tiles (KPIs): Saldo total, Disponível, Comprometido, A pagar 30 dias, Vencidas (qtd + valor, em danger quando >0), Pago no mês, e chips "aguardando aprovação/autorização" com link p/ `/pagamentos`. BRL via `toLocaleString("pt-BR", {style:"currency"...})`, `tabular-nums`.
  - Linha 2 — Fluxo de caixa mensal: BarChart pareado entradas (`#16a34a`) × saídas (`#dc2626`), Legend, Tooltip formatando BRL, XAxis mes 'MMM/aa', UM eixo Y. Barras finas, cantos 4px no topo.
  - Linha 3 (2 colunas) — Despesa por natureza e Por fonte: **barras horizontais** (layout="vertical" no recharts), hue única da marca (usar o azul institucional já usado no app — extrair de `tailwind.config.ts`/uso existente), rótulo direto com valor BRL, top 6 + "Outras".
  - Linha 4 (2 colunas) — Maiores débitos em aberto: tabela (fornecedor, descrição, valor, status badge — reusar o mapa de cores da tela contas-a-pagar) com linha → detalhe; Alertas: parcelas vencidas (dias de atraso em danger), vencendo 7 dias (warning), contas abaixo do mínimo (danger + ícone), cada item com ícone+texto (nunca só cor).
  - Estados: loading skeleton simples; erro com toast.
- [ ] **Step 3: Sidebar** — item `{ label: "Dashboard", href: "/pagamentos/dashboard", icon: BarChart3, anyOf: [as 5 permissões de pagamento] }` logo após "Início" (BarChart3 já é importado no arquivo).
- [ ] **Step 4: Validar paleta** — `node "<dataviz-base>/scripts/validate_palette.js" "#16a34a,#dc2626" --mode light` e `--mode dark` + o hex da marca usado nas barras; colar o resultado no report; se FAIL, snap para o step mais próximo que passe e usar esse.
- [ ] **Step 5: tsc** — limpo.
- [ ] **Step 6: Commit** — `feat(pagamentos): dashboard financeiro do gestor — KPIs, fluxo mensal, composição e alertas`

---

### Task 4: Verificação (controller)

- [ ] Regressão completa backend + tsc.
- [ ] Browser (admin@local.test): `/pagamentos/dashboard` renderiza 4 blocos com a massa do seed; trocar período 6/12/24; conferir coerência de um número contra a API (ex.: saldo_total = Σ painel do caixa); screenshot; conferir que home/caixa/contas-a-pagar continuam consistentes com a massa (fila do aprovador populada etc.).
- [ ] Ledger + commit final se houver ajustes.

## Self-review

- Spec coverage: seed (T1) ↔ spec §1; endpoint/payload (T2) ↔ §2; página/menu/dataviz (T3) ↔ §3; verificação (T4) ↔ §Verificação. Fora de escopo respeitado.
- Consistência: `DashboardOut` do T2 = tipos do T3; `PERMS_LEITURA` já existe no router (T2 reusa); seed usa exclusivamente interfaces já shipped (assinaturas conferidas no R2).
- Sem placeholders: sketches de query têm colunas/joins/filtros nomeados; massas/valores concretos na spec referenciada.
