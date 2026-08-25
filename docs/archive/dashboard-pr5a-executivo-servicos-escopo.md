# PR 5a — Escopo técnico: Dashboard executivo mínimo por serviço

**Autor:** Jorge + assistente · **Status:** PROPOSTA (aguardando autorização — nada implementado)

> **Estende** o dashboard executivo existente (Fases 18a/18b/18c — `/dashboard/kpis`,
> `/dashboard/export.{csv,pdf}`) com a **dimensão serviço** (PR 4a/4b) e os
> indicadores específicos do **checklist** (PR 4c) e **complementação** (PR 4d).
> Não é um dashboard novo do zero. **Sem** BI avançado, gráficos sofisticados,
> SLA completo, exportação avançada ou drill-down com dados pessoais. Gerar
> primeiro este doc; **não implementar**.

---

## 1. Objetivo

Dar a gestores uma visão "por serviço" do andamento operacional dos protocolos
do tenant: quais serviços puxam mais demanda, quais têm gargalo documental,
quantas complementações estão abertas e quanto tempo o cidadão leva para
responder. Tudo agregado, tudo `tenant`-scoped, sem dados pessoais.

## 2. Achados no código (o que será reusado, não recriado)

| Necessidade | Já existe | Decisão |
|---|---|---|
| Endpoint `/dashboard/kpis` + export `csv/pdf` | [`routers/dashboard.py`](../backend/app/routers/dashboard.py) (Fases 18a/18b/18c) | **Estender** — adicionar bloco `por_servico` e indicadores 4c/4d ao `DashboardKpis` existente |
| Serviço de agregações | [`services/dashboard.py::kpis`](../backend/app/services/dashboard.py) | **Estender** com novas queries (breakdown + indicadores) |
| Schemas | [`schemas/dashboard.py::DashboardKpis`](../backend/app/schemas/dashboard.py) (`volume`, `conclusao`, `sla`, `comparativo`, `por_tipo`, `por_assunto`, `por_unidade`, `serie_temporal`) | **Estender** com `documental`, `complementacao`, `por_servico` |
| Página `/dashboard` no servidor | [`app/(app)/dashboard/page.tsx`](../frontend/app/(app)/dashboard/page.tsx) — KPIs em cards + breakdowns recharts | **Estender** — novos cards e ranking de serviços; sem nova lib |
| `processo.id_servico` | PR 4b (migration 0025) | **Fonte** do breakdown por serviço; `NULL` = processo legado |
| `anexo.documento_exigido_key` + checklist calculado | PR 4c | **Fonte** do indicador "documental pendente/parcial/completo" — agregado, **sem** ler conteúdo |
| `complementacao_documental` (status / `criado_em` / `respondido_em`) | PR 4d | **Fonte** dos indicadores de complementação (aberta / respondida no período / tempo médio de resposta) |
| Permissão | Hoje endpoints de dashboard usam só `get_current_user` (qualquer autenticado vê) | **Criar transação `dashboard`** semeada idempotentemente (padrão da migration 0023/0024) — ver D-PERMISSAO |
| Padrão de tenant scoping | `tenant_id` em todas as queries + RLS nas tabelas relevantes | **Reusar** sem mexer |

**Última migration commitada = `0027`** → **nova = `0028`** (apenas para
semear a permissão `dashboard`; **sem** alterar tabelas).

## 3. Decisões a fechar (recomendações)

### D-ESTRUTURA — estender o `/dashboard/kpis` existente (RECOMENDADO)

- **Não** criar `/dashboard/resumo`, `/dashboard/servicos`, `/dashboard/unidades`
  separados. O dashboard atual já entrega tudo em uma chamada — manter um único
  payload reduz round-trips, simplifica o frontend e preserva o `export csv/pdf`
  já existente.
- O `DashboardKpis` ganha 3 blocos novos: `documental`, `complementacao`,
  `por_servico` (top N + linha "legado" agregada). Os blocos existentes
  permanecem **byte-compatíveis** (sem campo deletado ou renomeado).

**Alternativa rejeitada:** criar `/dashboard/servicos` separado. Aumenta
superfície sem ganho real e duplica o padrão de filtros `periodo`/`id_unidade`.

### D-PERMISSAO — criar transação `dashboard` (RECOMENDADO)

- Hoje o `/dashboard/kpis` está exposto a **qualquer usuário autenticado**.
  Isso é uma lacuna real — vai contra "respeitar permissões" do brief.
- Semear `utils.transacao` com `('Dashboard executivo', 'dashboard')` via
  migration 0028 (padrão idempotente, igual `configuracao` e `servico`).
- Trocar `Depends(get_current_user)` por
  `Depends(require_permission("dashboard"))` (sem `action` — basta "ver").
- Super-usuário continua bypassando (já é o padrão de
  `require_permission`).
- **Impacto em testes existentes:** os testes da Fase 18 usam super-usuário
  → continuam OK. Se algum teste usar não-SU sem grupo, vou conceder a
  transação via fixture.

### D-INDICADORES — escopo mínimo focado em "por serviço" (RECOMENDADO)

Novos indicadores agregados (todos `tenant`-scoped, todos respeitam o filtro
`periodo` / `id_unidade` / `id_servico` quando aplicável):

**Bloco `documental` (deriva do checklist do PR 4c)**

| Campo | Definição |
|---|---|
| `com_id_servico_periodo` | nº de processos abertos no período com `id_servico IS NOT NULL` |
| `sem_id_servico_periodo` | nº de processos abertos no período com `id_servico IS NULL` ("legado") |
| `checklist_pendente` | nº de processos abertos no período cujo checklist seria `pendente` (tem obrigatórios e nenhum enviado) — calculado por agregação SQL **sem** carregar processos em memória |
| `checklist_parcial` | idem, calculado como `parcial` |
| `checklist_completo` | idem, calculado como `completo` |

> Cálculo do checklist agregado fica em **SQL puro com JOIN +
> `documentos_exigidos` desempacotado via `jsonb_array_elements`**, contando
> matches por `anexo.documento_exigido_key`. Sem chamar `calcular_checklist`
> por processo (não escala). Detalhe técnico em §6.

**Bloco `complementacao` (deriva do PR 4d)**

| Campo | Definição |
|---|---|
| `abertas_agora` | snapshot — `WHERE status='aberta' AND excluido=FALSE` (não janelado) |
| `solicitadas_periodo` | `WHERE criado_em IN [desde, ate)` |
| `respondidas_periodo` | `WHERE respondido_em IN [desde, ate)` |
| `canceladas_periodo` | `WHERE cancelado_em IN [desde, ate)` |
| `tempo_medio_resposta_dias` | `AVG(respondido_em - criado_em)` em dias, apenas para `respondida` no período. Null se não houver dados |

**Bloco `por_servico` (breakdown — top N + legado)**

| Campo | Definição |
|---|---|
| `por_servico: list[ServicoBreakdownItem]` | top 10 por nº de processos abertos no período, com `id_servico`, `nome`, `count`, `complementacoes_abertas` (snapshot), `tempo_medio_resposta_dias` (null se 0 amostras). Linha extra (sem `id_servico`) somando os legados, com `nome = "(sem serviço)"`. |

### D-FILTROS — incrementais sobre os existentes (RECOMENDADO)

O endpoint atual aceita `periodo` (7/30/90/365) e `id_unidade`. Acrescentar:

- `id_servico: int | None` — restringe processos a um serviço.
- `incluir_legado: bool = True` — quando `False`, filtra
  `processo.id_servico IS NOT NULL` em todas as queries; quando `True`,
  inclui processos legados (default, comportamento atual).

`status` (brief item 2): processo tem `ativo` (boolean) e o status real é
derivado de movimentações/arquivamentos. **Não** adicionar filtro `status`
neste PR — exigiria definição de máquina de estados que o sistema ainda não
expõe explicitamente. Os 3 contadores de complementação (`abertas/respondidas/canceladas`)
e os contadores de checklist (`pendente/parcial/completo`) já cobrem o que o
brief chama de "status" sem inventar uma máquina nova.

### D-FRONTEND — estender a página `/dashboard` (RECOMENDADO)

- Adicionar:
  - 3 KPIs novos (com/sem serviço; checklist pendente; complementações abertas);
  - 1 ranking "Top 10 serviços" (tabela + barra horizontal recharts, reusando
    a lib que **já está no projeto**);
  - 1 ranking "Complementações por serviço" (tabela compacta com
    abertas/respondidas/tempo médio).
- Adicionar 2 controles ao painel de filtros: `<select>` de serviço (lista
  por `api.servicos.listar`) e `Checkbox` "Incluir processos legados sem
  serviço".
- **Não** adicionar nova lib de gráfico — usar `recharts` já presente.

### D-CACHE — sem cache neste PR

- O endpoint atual roda em < 100 ms para tenants de teste e re-fetch é
  `refetchInterval: 60_000` no frontend. Não introduzir cache (Redis/etc)
  agora; o índice em `processo.id_servico` (PR 4b) é suficiente para o
  breakdown.

## 4. Migration `0028_dashboard_perm` (DDL mínima)

- **Sem alteração em tabelas**. Apenas semeia a transação
  `('Dashboard executivo', 'dashboard')` em `utils.transacao`, idempotente
  no padrão de `servico` / `configuracao`.
- `downgrade`: remove `grupo_transacao`/`sistema_transacao` que referenciem
  `dashboard` e depois remove a transação.

```sql
INSERT INTO utils.transacao (transacao, codigo)
SELECT 'Dashboard executivo', 'dashboard'
WHERE NOT EXISTS (
    SELECT 1 FROM utils.transacao WHERE codigo = 'dashboard'
);
```

CI: a migration aplica em banco limpo (`stamp 0020 → head`); round-trip
testado.

## 5. Schemas

Em [`schemas/dashboard.py`](../backend/app/schemas/dashboard.py), **acrescentar**:

```py
class DocumentalKpis(BaseModel):
    com_id_servico_periodo: int
    sem_id_servico_periodo: int
    checklist_pendente: int
    checklist_parcial: int
    checklist_completo: int


class ComplementacaoKpis(BaseModel):
    abertas_agora: int
    solicitadas_periodo: int
    respondidas_periodo: int
    canceladas_periodo: int
    tempo_medio_resposta_dias: float | None


class ServicoBreakdownItem(BaseModel):
    id_servico: int | None  # null = linha "(sem serviço)"
    nome: str
    count: int
    complementacoes_abertas: int
    tempo_medio_resposta_dias: float | None


class DashboardKpis(BaseModel):
    # ... campos existentes preservados ...
    documental: DocumentalKpis           # PR 5a
    complementacao: ComplementacaoKpis   # PR 5a
    por_servico: list[ServicoBreakdownItem]  # PR 5a
```

Compatibilidade: nada deletado/renomeado; consumidores do `DashboardKpis`
existentes seguem funcionando.

## 6. Service — `services/dashboard.py` (extensão)

- **Manter** a assinatura `kpis(db, *, tenant_id, periodo_dias, id_unidade)`
  acrescentando `id_servico: int | None = None` e
  `incluir_legado: bool = True`.
- Reusar `_counts_intervalo` + adicionar dois novos helpers:
  - `_documental_periodo(...)` que computa
    `(com_id_servico, sem_id_servico, pendente, parcial, completo)` em
    **uma única query** com CTE/JOIN sobre
    `protocolos.servico, jsonb_array_elements(documentos_exigidos)`
    + `LEFT JOIN protocolos.anexo` por `documento_exigido_key`.
  - `_complementacao_periodo(...)` para os 4 contadores +
    `tempo_medio_resposta_dias`.
  - `_breakdown_servico(...)` para o top 10 + linha "(sem serviço)".

Esqueleto da query agregada do checklist (sem dados pessoais, sem `corpo`,
sem `nome`):

```sql
-- Quantos obrigatórios e quantos enviados, por processo, no período.
WITH docs_exigidos AS (
  SELECT s.id AS id_servico,
         (item ->> 'key')               AS key,
         (item ->> 'obrigatorio')::bool AS obrigatorio
  FROM protocolos.servico s,
       LATERAL jsonb_array_elements(s.documentos_exigidos) AS item
  WHERE s.tenant_id = :t
    AND s.excluido = false
), por_processo AS (
  SELECT p.id,
         COUNT(*) FILTER (WHERE d.obrigatorio) AS obrigatorios,
         COUNT(*) FILTER (
           WHERE d.obrigatorio AND a.id IS NOT NULL
         )                                       AS obrigatorios_enviados
  FROM protocolos.processo p
  JOIN docs_exigidos d
    ON d.id_servico = p.id_servico
  LEFT JOIN protocolos.anexo_processo ap
    ON ap.id_processo = p.id AND ap.excluido = false
  LEFT JOIN protocolos.anexo a
    ON a.id = ap.id_anexo AND a.excluido = false AND a.ativo = true
   AND a.documento_exigido_key = d.key
  WHERE p.tenant_id = :t
    AND p.excluido = false
    AND p.id_servico IS NOT NULL
    AND p.data_hora_abertura >= :desde
    AND p.data_hora_abertura <  :ate
  GROUP BY p.id
)
SELECT
  COUNT(*) FILTER (WHERE obrigatorios > 0 AND obrigatorios_enviados = 0)         AS pendente,
  COUNT(*) FILTER (WHERE obrigatorios > 0 AND obrigatorios_enviados > 0
                                          AND obrigatorios_enviados < obrigatorios) AS parcial,
  COUNT(*) FILTER (WHERE obrigatorios = 0
                       OR obrigatorios_enviados = obrigatorios)                 AS completo
FROM por_processo;
```

(query de contagem com/sem `id_servico` no período é trivial — `COUNT(*)`
com/sem `IS NOT NULL`.)

## 7. Endpoint

`GET /api/v2/dashboard/kpis` (mesma URL atual) — agora exige
`require_permission("dashboard")` em vez de `get_current_user`. Acrescenta os
query params:

- `id_servico: int | None`
- `incluir_legado: bool = True` (default preserva comportamento atual)

`export.csv` e `export.pdf` permanecem na **mesma URL**, recebendo os mesmos
filtros novos. O gerador CSV/PDF passa a incluir as 3 seções novas; testes
de integração existentes desses exports continuam válidos (formato é
append-only).

## 8. Frontend — `/(app)/dashboard/page.tsx` (extensão)

- 3 KPIs novos na grade existente:
  - "Documental pendente" (warning) — `documental.checklist_pendente`.
  - "Complementações abertas" (warning) — `complementacao.abertas_agora`.
  - "Tempo médio de resposta" — `complementacao.tempo_medio_resposta_dias`,
    formatado em dias.
- Bloco "Top 10 serviços" abaixo dos breakdowns existentes:
  - Tabela compacta: serviço, processos no período, complementações
    abertas, tempo médio de resposta.
  - Linha final destacada com `(sem serviço) — legado` quando
    `incluir_legado=true` e houver dados.
- Filtros: `<select>` de serviço (`api.servicos.listar()` — endpoint admin
  já existe) e `Checkbox` "Incluir processos legados sem serviço".
- Sem nova lib; só reutilizar `recharts`.

## 9. Segurança e LGPD

- **Tenant pelo Host** (middleware atual). Todas as queries têm
  `tenant_id = :t`.
- **Cross-tenant 404** indireto: filtro por `tenant_id` em service +
  `require_tenant_id` no endpoint impedem qualquer leak.
- `require_permission("dashboard")` — super-usuário bypassa; demais precisam
  da transação concedida.
- **Não** retornar: CPF, nome do cidadão, `corpo`, nome de arquivo,
  mensagem de complementação, motivo de cancelamento. Os payloads novos só
  contêm contagens, médias, `id_servico` e `nome` do serviço (que já é
  público para o cidadão).
- Confirmar visual no PR: nenhum campo `processo.corpo`/`observacao` chega
  ao JSON.

## 10. Testes obrigatórios

### 10.1 Backend (pytest) — `backend/tests/test_pr5a_dashboard_servicos.py`

- Migration 0028 aplica em banco limpo; round-trip OK; reaplicar não duplica
  a transação.
- `/dashboard/kpis` **sem permissão `dashboard`** (usuário não-SU sem
  transação) → 403.
- Super-usuário continua acessando sem grupo.
- **Cross-tenant**: usuário do tenant B vê apenas dados do B (zero do A).
- **Total por serviço correto** (top 10 ordenado desc por count).
- **Legado contabilizado** corretamente: 3 processos sem `id_servico` no
  período → linha `(sem serviço)` com `count = 3`.
- **Filtro `incluir_legado=false`** remove a linha legado e reduz
  `documental.sem_id_servico_periodo` da soma.
- **Filtro `id_servico=X`** isola para um único serviço (top só com aquele;
  contadores documentais só dos processos do serviço).
- **`documental.checklist_*`** confere com cálculo do `calcular_checklist`
  por processo em um set pequeno (compara agregado vs cálculo individual).
- **`complementacao.abertas_agora`** conta linhas com `status='aberta'`;
  **`solicitadas_periodo`** conta `criado_em` no intervalo;
  **`respondidas_periodo`** conta `respondido_em` no intervalo;
  **`canceladas_periodo`** conta `cancelado_em` no intervalo.
- **`tempo_medio_resposta_dias`** = média de
  `(respondido_em - criado_em)` em dias; null quando sem amostras.
- **Sem dados pessoais no payload**: nenhuma string com CPF, nome de
  cidadão, mensagem de complementação ou nome de arquivo aparece em
  `kpis(...)` (verificado por inspeção do JSON serializado).
- Filtros existentes (`periodo`, `id_unidade`) continuam funcionando — não
  regredir testes da Fase 18.
- Export CSV/PDF não quebra (cabeçalho + seções append-only).

### 10.2 Frontend (vitest)

- Página `/dashboard` renderiza os 3 cards novos quando o endpoint retorna
  dados.
- Tabela "Top 10 serviços" renderiza com a linha "(sem serviço)" no fim
  quando há legado.
- Filtro `<select>` de serviço chama `dashboardApi.kpis` com `id_servico`.
- `Checkbox` "Incluir legado" alterna `incluir_legado` e dispara refetch.
- Estado vazio: quando todos os arrays vêm vazios, mostra mensagem
  amigável "Sem dados no período".
- Estado de erro: quando o endpoint dá 403, mostra "Sem permissão para o
  dashboard" (intent danger).

### 10.3 E2E (Playwright — opcional, baixo custo)

`tests-e2e/specs/dashboard-servicos.spec.ts`: super-usuário abre
`/dashboard`, vê o card de "Documental pendente", filtra por um serviço e
confirma que o ranking some/troca.

## 11. Fora de escopo

- BI avançado (cubos, drill-down livre);
- gráficos complexos (heatmap, Sankey);
- export adicional (Excel `.xlsx` nativo, JSON push);
- **SLA completo** (regras por serviço, alarmes, prazos legais) — fica para
  PR futuro;
- **alertas** (email/in_app por desvios de KPI);
- **drill-down com dados pessoais** (clicar num serviço e ver lista de
  processos com manifestante) — vedado por LGPD neste PR;
- **dashboard global da plataforma** / métricas cross-tenant — somente
  Admin SaaS pode querer isso, fica em PR específico;
- **cobrança / billing**;
- **IA / previsão de demanda**;
- **cache** (Redis/memcached) — adiar até medir necessidade real.

## 12. Critérios de aceite

- Migration 0028 aplicada/testada; transação `dashboard` semeada
  idempotente.
- Endpoint `/dashboard/kpis` exige permissão `dashboard` (super-usuário
  bypassa). Endpoints `export.csv`/`export.pdf` idem.
- `DashboardKpis` ganha `documental`, `complementacao`, `por_servico`
  **sem** remover ou renomear campos existentes.
- Top 10 serviços + linha "(sem serviço)" disponíveis na resposta quando
  há dados.
- `incluir_legado` e `id_servico` aplicáveis em todos os contadores.
- Sem dados pessoais no payload (verificado por teste).
- Página `/dashboard` mostra os novos KPIs, ranking de serviços, controles
  de filtro.
- Testes backend + frontend passando; sem regressão (PRs 4a/4b/4c/4d
  verdes).
- Itens fora de escopo **não** implementados.
- Relatório final com arquivos, testes, riscos, ganchos para SLA por
  serviço (PR 5b?), alertas e dashboard global.

## 13. Anti-objetivos (o que NÃO fazer)

- Não criar endpoints novos `/dashboard/servicos` ou `/dashboard/unidades`
  paralelos — manter unificado.
- Não recriar lib de gráficos.
- Não calcular checklist por processo em Python (já existe `calcular_checklist`,
  mas é por-processo; nas agregações usar SQL agregada).
- Não modificar `processo`/`anexo`/`servico`/`complementacao_documental` —
  apenas LER.
- Não vazar `corpo`, `observacao`, CPF, nome ou mensagem em payload algum.
- Não adicionar `status` enum no `processo` (fora de escopo desde PR 4d).
- Não introduzir cache distribuído neste PR.
