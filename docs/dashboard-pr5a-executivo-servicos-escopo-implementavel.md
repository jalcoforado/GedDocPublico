# PR 5a — Escopo Implementável: Dashboard executivo por serviço, documentos e complementações

**Autor:** Jorge + assistente · **Status:** ESCOPO FECHADO (aguardando autorização para implementar)

> Consolida a [proposta](dashboard-pr5a-executivo-servicos-escopo.md) com as
> **6 decisões (D-ESTRUTURA / D-PERMISSAO / D-INDICADORES / D-FILTROS /
> D-FRONTEND / D-CACHE)** fechadas. Estende o dashboard executivo existente
> (Fases 18a/18b/18c) com a dimensão **serviço** (PR 4a/4b) e os indicadores
> agregados de **checklist** (PR 4c) e **complementação documental** (PR 4d).
> **Não** cria endpoint novo, **não** modifica tabelas de domínio, **não**
> introduz lib nova. **Nada será alterado em código até autorização explícita.**

---

## 1. Objetivo e decisões travadas

Dar a gestores municipais visão "por serviço" do andamento operacional, com:
ranking de demanda, gargalo documental e estado das complementações
formais — sem expor dado pessoal e sem inflar escopo.

**Decisões fechadas:**

- **D-ESTRUTURA** — estender `/dashboard/kpis` existente (sem endpoints
  paralelos); manter payload **byte-compatível** (campos atuais
  preservados, sem renomear nem deletar).
- **D-PERMISSAO** — criar transação `dashboard` (migration 0028,
  idempotente, padrão 0023/0024). Endpoint passa a exigir
  `require_permission("dashboard")`. SU mantém bypass. Não-SU sem a
  transação → 403. Endpoints `export.csv` e `export.pdf` recebem o
  mesmo gate.
- **D-INDICADORES** — 3 blocos novos: `documental`, `complementacao`,
  `por_servico`. Cálculo do checklist agregado em **SQL puro com CTE +
  `jsonb_array_elements`** — **não** chamar `calcular_checklist`
  por processo.
- **D-FILTROS** — acrescentar `id_servico: int | None` e
  `incluir_legado: bool = True`. **Sem** filtro de `status` neste PR
  (exigiria máquina de estados explícita).
- **D-FRONTEND** — estender [`app/(app)/dashboard/page.tsx`](../frontend/app/(app)/dashboard/page.tsx);
  reusar `recharts` (já no projeto); sem nova lib.
- **D-CACHE** — nenhum; índice `tenant_id + id_servico` (PR 4b) é
  suficiente.
- **LGPD** — payload aceita apenas valores agregados; **nunca** CPF,
  nome do cidadão, `corpo`, `observacao`, mensagem do servidor, motivo
  de cancelamento, nome de arquivo ou conteúdo. Teste valida ausência.

## 2. Migration `0028_dashboard_perm`

Apenas semeia a transação `dashboard` em `utils.transacao`,
idempotentemente, no padrão de `0023_tenant_config_inicial.py` e
`0024_servico_catalogo.py`. **Nenhuma tabela de domínio é alterada.**

```py
# backend/alembic/versions/0028_dashboard_perm.py
"""Permissão de dashboard executivo (PR 5a).

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-30

Semeia a transação `dashboard` em `utils.transacao`. Idempotente, mesmo
padrão de `configuracao` (0023) e `servico` (0024). Sem alteração em
tabelas de domínio.
"""
from __future__ import annotations
from collections.abc import Sequence
from alembic import op

revision: str = "0028"
down_revision: str | Sequence[str] | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO utils.transacao (transacao, codigo)
        SELECT 'Dashboard executivo', 'dashboard'
        WHERE NOT EXISTS (
            SELECT 1 FROM utils.transacao WHERE codigo = 'dashboard'
        )
        """
    )


def downgrade() -> None:
    # FK-safe: remove concessões antes da transação.
    op.execute(
        """
        DELETE FROM utils.grupo_transacao
        WHERE id_transacao IN (
            SELECT id FROM utils.transacao WHERE codigo = 'dashboard'
        )
        """
    )
    op.execute(
        """
        DELETE FROM utils.sistema_transacao
        WHERE id_transacao IN (
            SELECT id FROM utils.transacao WHERE codigo = 'dashboard'
        )
        """
    )
    op.execute("DELETE FROM utils.transacao WHERE codigo = 'dashboard'")
```

**CI:** `stamp 0020 → upgrade head` aplica 0028 em banco limpo; round-trip
limpo (reaplicar não duplica).

## 3. Schemas — `backend/app/schemas/dashboard.py` (extensão)

Acrescentar três classes + 3 campos novos em `DashboardKpis`. Campos
existentes ficam intactos (D-ESTRUTURA: byte-compatível).

```py
class DocumentalKpis(BaseModel):
    com_id_servico_periodo: int
    sem_id_servico_periodo: int
    checklist_pendente: int     # processos abertos no período com obrigatórios e nenhum enviado
    checklist_parcial: int      # algum obrigatório enviado, nem todos
    checklist_completo: int     # sem obrigatórios pendentes (ou sem obrigatórios)
    # nota: processos com id_servico mas serviço sem documentos_exigidos
    # entram em `checklist_completo` (são "sem nada a exigir" — completo trivial).


class ComplementacaoKpis(BaseModel):
    abertas_agora: int                   # snapshot
    solicitadas_periodo: int             # criado_em em [desde, ate)
    respondidas_periodo: int             # respondido_em em [desde, ate)
    canceladas_periodo: int              # cancelado_em em [desde, ate)
    processos_com_aberta_agora: int      # distinct id_processo onde existe aberta
    tempo_medio_resposta_dias: float | None  # AVG sobre respondidas no período; null se 0


class ServicoBreakdownItem(BaseModel):
    id_servico: int | None   # null = linha "(sem serviço)" (legado)
    nome: str                # "(sem serviço)" para legado
    count: int               # processos abertos no período
    complementacoes_abertas: int
    complementacoes_respondidas_periodo: int
    checklist_pendente: int
    checklist_parcial: int
    checklist_completo: int


class DashboardKpis(BaseModel):
    # ... campos existentes preservados (periodo_dias, id_unidade,
    # volume, conclusao, sla, comparativo, por_tipo, por_assunto,
    # por_unidade, serie_temporal) ...
    documental: DocumentalKpis           # PR 5a
    complementacao: ComplementacaoKpis   # PR 5a
    por_servico: list[ServicoBreakdownItem]  # PR 5a (top 10 + linha "(sem serviço)" quando há legado e incluir_legado=True)
```

Notas de compatibilidade:

- A página `/dashboard` atual lê apenas os campos antigos; ficar à
  vontade para ignorar campos novos no front até serem usados.
- `dashboardExportCsvUrl` / `dashboardExportPdfUrl` no front aceitam
  query params arbitrários (já passam `qs(...)`) — bastará adicionar
  `id_servico` e `incluir_legado` quando vinculados.

## 4. Service — `backend/app/services/dashboard.py` (extensão)

### 4.1 Assinatura de `kpis(...)`

```py
async def kpis(
    db: AsyncSession,
    *,
    tenant_id: int,
    periodo_dias: int = 30,
    id_unidade: int | None = None,
    id_servico: int | None = None,         # PR 5a
    incluir_legado: bool = True,           # PR 5a
) -> dict[str, Any]: ...
```

### 4.2 Filtro reusável

Acrescentar à fábrica `_base_processo` (e mirror em queries inline) o
mesmo padrão de filtro:

```py
if id_servico is not None:
    stmt = stmt.where(Processo.id_servico == id_servico)
elif not incluir_legado:
    stmt = stmt.where(Processo.id_servico.is_not(None))
```

`id_servico` informado **ignora** `incluir_legado` (faz sentido: o
gestor está olhando 1 serviço específico).

### 4.3 `_documental_periodo(...)` — nova função

Calcula `documental.{com_id_servico_periodo, sem_id_servico_periodo,
checklist_pendente, checklist_parcial, checklist_completo}` no
intervalo `[desde, ate)` aplicando `id_unidade` / `id_servico` /
`incluir_legado`.

**Estratégia (uma rodada de queries, sem N+1):**

1. `com_id_servico_periodo` + `sem_id_servico_periodo`: dois
   `COUNT(*)` filtrando `id_servico IS [NOT] NULL` no intervalo.
2. Checklist agregado — **uma** query SQL com CTE
   `jsonb_array_elements(documentos_exigidos)` + LEFT JOIN em
   `anexo`:

```sql
WITH docs_exigidos AS (
  SELECT s.id AS id_servico,
         (item ->> 'key')               AS key,
         (COALESCE(item ->> 'obrigatorio', 'false'))::bool AS obrigatorio
  FROM protocolos.servico s,
       LATERAL jsonb_array_elements(COALESCE(s.documentos_exigidos, '[]'::jsonb)) AS item
  WHERE s.tenant_id = :t
    AND s.excluido = false
), por_processo AS (
  SELECT p.id,
         COUNT(*) FILTER (WHERE d.obrigatorio)                                AS obrigatorios,
         COUNT(*) FILTER (WHERE d.obrigatorio AND a.id IS NOT NULL)           AS obrigatorios_enviados
  FROM protocolos.processo p
  JOIN docs_exigidos d
    ON d.id_servico = p.id_servico
  LEFT JOIN protocolos.anexo_processo ap
    ON ap.id_processo = p.id AND ap.excluido = false AND ap.tenant_id = :t
  LEFT JOIN protocolos.anexo a
    ON a.id = ap.id_anexo
   AND a.excluido = false
   AND a.ativo = true
   AND a.documento_exigido_key = d.key
   AND a.tenant_id = :t
  WHERE p.tenant_id = :t
    AND p.excluido = false
    AND p.id_servico IS NOT NULL
    AND p.data_hora_abertura >= :desde
    AND p.data_hora_abertura <  :ate
    /* + filtros opcionais id_unidade / id_servico */
  GROUP BY p.id
)
SELECT
  COUNT(*) FILTER (WHERE obrigatorios > 0 AND obrigatorios_enviados = 0)                              AS pendente,
  COUNT(*) FILTER (WHERE obrigatorios > 0 AND obrigatorios_enviados > 0
                                          AND obrigatorios_enviados < obrigatorios)                  AS parcial,
  COUNT(*) FILTER (WHERE obrigatorios = 0 OR obrigatorios_enviados = obrigatorios)                   AS completo
FROM por_processo;
```

> **Casamento com o checklist do PR 4c:** a regra de status documental
> usada por [`services/checklist_documentos.py::_calcular_status`](../backend/app/services/checklist_documentos.py)
> trata processo sem `id_servico` ou serviço sem `documentos_exigidos`
> como `sem_documentos_exigidos`. No agregado, eles ficam **fora**
> de `pendente/parcial/completo` (a CTE acima já exclui pela cláusula
> `id_servico IS NOT NULL`). Processo com serviço mas sem itens
> exigidos entra como `completo` (trivial — não há o que faltar).
> Testes verificam essa correspondência em §10.

3. `id_unidade` e `id_servico` aplicam-se ao `WHERE` de `processo` na
   CTE; `incluir_legado=False` é redundante aqui (a CTE já filtra
   `id_servico IS NOT NULL`).

### 4.4 `_complementacao_periodo(...)` — nova função

Quatro `COUNT(*)` em `protocolos.complementacao_documental` aplicando
filtros (`tenant_id`, intervalo, `id_servico` via join opcional em
`processo` para herdar o filtro do gestor):

- `abertas_agora`: `status='aberta' AND excluido=false` (snapshot).
- `solicitadas_periodo`: `criado_em ∈ [desde, ate)`.
- `respondidas_periodo`: `respondido_em ∈ [desde, ate)`.
- `canceladas_periodo`: `cancelado_em ∈ [desde, ate)`.
- `processos_com_aberta_agora`: `COUNT(DISTINCT id_processo)` com
  `status='aberta'`.
- `tempo_medio_resposta_dias`:
  `AVG(EXTRACT(epoch FROM respondido_em - criado_em) / 86400.0)` para
  `respondida` no período; `None` se 0 amostras.

Para honrar `id_unidade` / `id_servico` / `incluir_legado`, todas as
queries fazem `JOIN protocolos.processo p ON p.id = cd.id_processo`
e aplicam os mesmos filtros usados nos outros indicadores.

### 4.5 `_breakdown_servico(...)` — nova função

Top 10 serviços por nº de processos abertos no período, com
agregação multi-coluna em **uma** query (joins externos para
complementação + checklist). Linha "(sem serviço)" agregada via
`UNION ALL`, **apenas** quando `incluir_legado=True` e
`id_servico is None`.

Estratégia:

1. `servico_counts`: `Servico` LEFT JOIN `Processo` no período →
   `count`, `complementacoes_abertas` (subquery escalar), etc. `ORDER
   BY count DESC LIMIT 10`.
2. `legado_row`: agregado em `Processo` `WHERE id_servico IS NULL`
   no período, com mesmas colunas. Concatenado no Python (não
   precisa `UNION` em SQL).
3. Para cada linha: as colunas `checklist_pendente / parcial /
   completo` reusam o mesmo padrão da §4.3, restritas ao
   `id_servico` daquela linha (ou `IS NULL`). **Em 1 query
   agregada por chamada** (uma única passagem pela CTE
   `por_processo`, agrupando por `p.id_servico`). Não há N+1.

### 4.6 Retorno final

Anexar ao dict retornado por `kpis(...)`:

```py
return {
  # ... campos existentes ...
  "documental": {...},
  "complementacao": {...},
  "por_servico": [...],
}
```

## 5. Router — `backend/app/routers/dashboard.py` (extensão)

- Trocar `Depends(get_current_user)` por
  `Depends(require_permission("dashboard"))` nos 3 endpoints
  (`/kpis`, `/export.csv`, `/export.pdf`).
- Acrescentar `id_servico: int | None = Query(None)` e
  `incluir_legado: bool = Query(True)` em todos os três.
- Repassar para `compute_kpis(...)`.

```py
@router.get("/kpis", response_model=DashboardKpis)
async def get_kpis(
    _: Usuario = Depends(require_permission("dashboard")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    periodo: int = Query(30),
    id_unidade: int | None = Query(None),
    id_servico: int | None = Query(None),      # PR 5a
    incluir_legado: bool = Query(True),         # PR 5a
): ...
```

## 6. Export CSV/PDF — `backend/app/services/dashboard_export.py`

- O CSV/PDF atual já é seccionado. **Anexar** seções `[Documental]`,
  `[Complementação]`, `[Por serviço]` no fim, **sem** mexer nas seções
  anteriores (append-only). Testes existentes do export não regridem.
- Linha "(sem serviço)" aparece como uma linha igual às outras na
  seção `[Por serviço]`, com `id_servico` em branco e
  `nome = "(sem serviço)"`.

## 7. Frontend

### 7.1 Tipos — `frontend/lib/api.ts`

Acrescentar 3 interfaces e 3 campos a `DashboardKpis`:

```ts
export interface DocumentalKpis {
  com_id_servico_periodo: number;
  sem_id_servico_periodo: number;
  checklist_pendente: number;
  checklist_parcial: number;
  checklist_completo: number;
}

export interface ComplementacaoKpis {
  abertas_agora: number;
  solicitadas_periodo: number;
  respondidas_periodo: number;
  canceladas_periodo: number;
  processos_com_aberta_agora: number;
  tempo_medio_resposta_dias: number | null;
}

export interface ServicoBreakdownItem {
  id_servico: number | null;
  nome: string;
  count: number;
  complementacoes_abertas: number;
  complementacoes_respondidas_periodo: number;
  checklist_pendente: number;
  checklist_parcial: number;
  checklist_completo: number;
}

export interface DashboardKpis {
  // ... campos existentes ...
  documental: DocumentalKpis;
  complementacao: ComplementacaoKpis;
  por_servico: ServicoBreakdownItem[];
}
```

Atualizar `dashboardApi.kpis` + `dashboardExportCsvUrl` +
`dashboardExportPdfUrl` para aceitar `id_servico?: number` e
`incluir_legado?: boolean`.

### 7.2 Página — `frontend/app/(app)/dashboard/page.tsx`

**Estados novos:** `idServico: number | null`, `incluirLegado: boolean
= true`.

**Filtros (linha de controles existente):**
- Adicionar `<select>` de serviços (consumindo `servicosApi.list(false)`).
- Adicionar `Checkbox` "Incluir processos legados (sem serviço)".

**Cards novos (na grade KPI existente):**
- `Documental pendente` (intent=warning) → `documental.checklist_pendente`.
- `Documental completo` (intent=success) → `documental.checklist_completo`.
- `Complementações abertas` (intent=warning) →
  `complementacao.abertas_agora`.
- `Tempo médio de resposta` (neutro) → formatar
  `complementacao.tempo_medio_resposta_dias` em "X.X dias" ou "—" se
  null.

**Bloco "Ranking de serviços" (abaixo dos breakdowns por tipo/assunto/unidade):**
- Tabela com: `nome`, `processos`, `compl. abertas`,
  `compl. respondidas`, `pendente / parcial / completo`.
- Quando `por_servico` traz linha com `id_servico === null`, renderizar
  no fim, com fundo levemente destacado e rótulo `(sem serviço — legado)`.
- Quando lista vazia, mostrar "Sem dados no período".

**Estado vazio / loading / error:**
- `q.isLoading`: skeletons existentes cobrem; adicionar 1 skeleton extra
  para a tabela de ranking.
- `q.error?.status === 403`: mostrar mensagem "Sem permissão para o
  dashboard" (intent=danger) — feedback alinhado ao gate D-PERMISSAO.
- `por_servico.length === 0` e demais arrays vazios: render
  "Sem dados no período" no card de ranking.

Sem nova lib. Sem reescrever a página. Sem mover os cards existentes.

### 7.3 Query keys

A `queryKey` atual é `["dashboard-kpis", { periodo, idUnidade }]`.
Estender para `["dashboard-kpis", { periodo, idUnidade, idServico,
incluirLegado }]`. Trocar o filtro recalcula naturalmente.

## 8. Segurança e LGPD

- **Tenant pelo Host** (middleware). Toda query tem `tenant_id = :t`.
- **`require_permission("dashboard")`** nos 3 endpoints.
  Cross-tenant 404 indireto (via `require_tenant_id`).
- **Nunca** retornar: CPF, nome do cidadão, `processo.corpo`,
  `processo.observacao`, mensagem do servidor, motivo de
  cancelamento, nome original de arquivo, conteúdo. Apenas IDs,
  contadores, médias e `servico.nome` (que já é público para o
  cidadão pelo portal).
- Teste explícito de "ausência" inspeciona o JSON serializado da
  resposta e falha se qualquer campo sensível aparecer (§10.1).

## 9. Critérios de aceite

- Migration 0028 aplicada/testada; transação `dashboard` semeada
  idempotente; round-trip OK.
- `/dashboard/kpis` (e exports) exigem `require_permission("dashboard")`;
  SU bypassa; usuário com grupo concedendo `dashboard` acessa; demais
  → 403.
- `DashboardKpis` ganha `documental`, `complementacao`, `por_servico`,
  **sem** remover ou renomear campos existentes (compat byte-a-byte).
- Top 10 + linha "(sem serviço)" quando `incluir_legado=true` e há
  processos legados.
- Filtros `id_servico` e `incluir_legado` aplicáveis em **todos** os
  contadores (volume / conclusão / SLA / breakdowns existentes / novos).
- Tempo médio de resposta calculado em dias, null quando sem amostras.
- Indicadores documentais agregados conferem com `calcular_checklist`
  por processo em um set pequeno (teste de equivalência).
- Sem dados pessoais no payload (verificado por teste).
- Página `/dashboard` mostra os novos KPIs, ranking de serviços,
  controles de filtro; sem regressão visual nos cards existentes.
- Export CSV/PDF inclui as seções novas (append-only); testes
  anteriores do export continuam verdes.
- Testes backend + frontend passando; sem regressão (PRs 4a/4b/4c/4d
  verdes).
- Itens fora de escopo **não** implementados.
- Relatório final com arquivos, testes, riscos, ganchos para PRs
  futuros (SLA por serviço, alertas, dashboard global).

## 10. Testes obrigatórios

### 10.1 Backend (pytest) — `backend/tests/test_pr5a_dashboard_servicos.py`

Setup helper: cria 2 tenants (A, B); em A cria serviço com
`documentos_exigidos = [{key:"rg",obrigatorio:true},{key:"cpf",obrigatorio:true},{key:"comp",obrigatorio:false}]`,
cria cidadão, abre 4 processos por serviço + 1 processo legado (sem
`id_servico`); anexa alguns docs com `documento_exigido_key`; abre 2
complementações (1 respondida + 1 aberta); cria usuário servidor SU,
usuário servidor não-SU sem `dashboard`, usuário servidor não-SU com
`dashboard` via grupo.

**Casos:**

1. **Migration 0028** aplica em banco limpo; `utils.transacao`
   contém `('Dashboard executivo','dashboard')`. Reaplicar é
   no-op (mesma linha). `downgrade` remove a linha e suas concessões.
2. **Sem permissão** (não-SU sem `dashboard`) → **403** em
   `/dashboard/kpis`, `/dashboard/export.csv`, `/dashboard/export.pdf`.
3. **SU bypassa** os 3 endpoints e devolve payload.
4. **Não-SU com `dashboard` via grupo** acessa.
5. **Cross-tenant:** SU do tenant B chama `/kpis` e vê **zero**
   dos dados de A (volume.abertos = 0, por_servico = []).
6. **Filtro `id_servico=X`** isola contadores para esse serviço (top
   só com aquele; documental/complementacao só dos processos do
   serviço).
7. **Filtro `incluir_legado=false`** remove a linha "(sem serviço)"
   de `por_servico` e zera `documental.sem_id_servico_periodo` na
   visão filtrada **dos contadores periodais correlatos** (ver
   §4.2: filtro aplica-se a todas as queries de
   processo-no-período).
8. **`documental.checklist_*`** confere com soma do
   `calcular_checklist` chamado por cada processo do set (teste de
   equivalência: pequena suíte de 4 processos + 1 legado).
9. **`complementacao.abertas_agora == 1`**, `solicitadas_periodo ==
   2`, `respondidas_periodo == 1`, `canceladas_periodo == 0`,
   `processos_com_aberta_agora == 1`.
10. **`complementacao.tempo_medio_resposta_dias`** ≈ valor
    esperado calculado em Python a partir de
    `respondido_em - criado_em` do mesmo set; `None` quando 0
    amostras.
11. **`por_servico`** ordenado desc por `count`, top 10, linha
    `id_servico=null` aparece quando `incluir_legado=True` e existe
    legado.
12. **Sem dados pessoais no payload**: serializa o JSON de
    `/dashboard/kpis` para string e afirma que `"Maria"`, CPF do
    cidadão, `"Pedido de teste"` (corpo), nome de arquivo do anexo,
    mensagem da complementação e motivo de cancelamento **não**
    aparecem.
13. **Filtros existentes (`periodo`, `id_unidade`)** continuam
    funcionando (smoke do payload). Não regredir testes existentes
    da Fase 18 (rodar a suíte de dashboard como um todo).
14. **Export CSV** contém os títulos das 3 seções novas
    (`[Documental]`, `[Complementação]`, `[Por serviço]`); seções
    antigas seguem presentes (smoke por substring).
15. **Export PDF** retorna 200 e Content-Type `application/pdf`
    (não validamos layout pixel-perfect).

### 10.2 Frontend (vitest)

Arquivo: `frontend/app/(app)/dashboard/__tests__/page.test.tsx`
(ou similar, alinhado ao padrão do projeto).

1. **Sem regressão**: dashboard renderiza os cards existentes com
   payload mock contendo todos os campos novos vazios/zerados.
2. **Cards novos** renderizam quando o payload traz dados em
   `documental` e `complementacao`.
3. **Ranking de serviços**: tabela renderiza linhas para cada item
   de `por_servico`; quando há `id_servico === null`, mostra rótulo
   `(sem serviço — legado)` em destaque.
4. **Filtro `<select>` de serviço** chama `dashboardApi.kpis` com
   `id_servico` correto na mudança.
5. **Checkbox `Incluir legado`** alterna `incluir_legado` e dispara
   refetch.
6. **Tratamento de 403**: simular erro 403 → mostra mensagem "Sem
   permissão para o dashboard".
7. **Estado vazio**: `por_servico = []` mostra "Sem dados no
   período" no card de ranking.
8. **`tempo_medio_resposta_dias = null`** mostra "—" no card.

### 10.3 E2E (Playwright — opcional, baixo custo)

Não obrigatório neste PR. Se houver folga, abrir
`/dashboard` como SU, validar visual dos novos cards e do ranking;
trocar serviço no filtro e confirmar refetch.

## 11. Fora de escopo (anti-objetivos confirmados)

- Endpoints paralelos `/dashboard/servicos` / `/dashboard/unidades`;
- Nova biblioteca de gráficos;
- Modificação de tabelas de domínio (`processo`/`anexo`/`servico`/
  `complementacao_documental`);
- Status enum em `processo`;
- Drill-down com dados pessoais (clicar num serviço e listar
  processos com manifestante);
- **SLA por serviço** completo (PR futuro);
- **Alertas / notificações** por desvio de KPI;
- **IA / previsão de demanda**;
- **Cobrança**;
- **Dashboard global** da plataforma / métricas cross-tenant;
- Nova exportação (Excel `.xlsx`, JSON push) — manter `csv/pdf`
  existentes com seções append-only;
- **Cache** (Redis/materialização) — adiar até medir necessidade.

## 12. Anti-objetivos técnicos (lembrete operacional)

- Não chamar `calcular_checklist` por processo — usar SQL agregada.
- Não duplicar lógica de status documental fora da CTE — manter o
  cálculo em **um** ponto na §4.3 (function `_documental_periodo`).
- Não renomear/deletar campos atuais de `DashboardKpis` (D-ESTRUTURA).
- Não criar `service`/`router` paralelo para complementação no
  dashboard — integrar no `services/dashboard.py` atual.
- Não introduzir `notificacao` ou `audit` neste PR (dashboard é
  leitura).
- Não modificar `processo.corpo`, `processo.observacao`, ou qualquer
  outro campo de processo — só **lê**.
- Não vazar dado pessoal em nenhum lugar (verificado por teste
  §10.1.12).
