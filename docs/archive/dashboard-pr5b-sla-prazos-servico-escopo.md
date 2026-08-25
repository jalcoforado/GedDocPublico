# PR 5b — Escopo: SLA e prazos por serviço

**Autor:** Jorge + assistente · **Status:** PROPOSTA DE ESCOPO (aguardando autorização para implementar)

> Transforma `servico.prazo_estimado_dias` em controle operacional de prazo
> end-to-end de processos abertos a partir da Carta de Serviços. Estende o
> dashboard executivo do PR 5a com cards/ranking de SLA por serviço e o
> detalhe do processo com `prazo_previsto_em` + status. **Não** introduz
> calendário de feriados, dias úteis, alertas, notificações, suspensão de
> prazo nem reabertura. **Nada será alterado em código até autorização
> explícita.**

---

## 1. Contraponto com o que já existe (importante)

O sistema **já possui** um conceito de SLA — `WorkflowSlaAlerta` /
`WorkflowInstance` no [models/workflow.py](../backend/app/models/workflow.py) — mas
ele opera **por nó de workflow** (cada step do fluxo interno tem seu próprio
SLA). É o que alimenta o bloco `sla: { pendentes, resolvidos_periodo }` do
dashboard atual ([services/dashboard.py:1045-1048](../backend/app/services/dashboard.py#L1045-L1048)).

O PR 5b é coisa **diferente** e complementar: SLA **do processo inteiro**
(abertura → conclusão), parametrizado pelo `servico.prazo_estimado_dias`.

Eles coexistem sem conflito. Nomenclatura proposta para evitar confusão:

| Conceito atual | Conceito PR 5b |
|----------------|----------------|
| `sla` (WorkflowSlaAlerta) — alertas de nó | `prazos` (PR 5b) — SLA end-to-end do processo |

O bloco novo do payload se chama **`prazos`**, não `sla`, para não colidir
com o bloco existente. Schema atual permanece byte-compatível.

---

## 2. Decisões a fechar

Cinco pontos onde existe trade-off real. Recomendação minha em **negrito**;
podemos discutir antes do código.

### D-SNAPSHOT — congelar o prazo no momento da abertura?

**Decisão pedida:** ao mudar `servico.prazo_estimado_dias` depois, processos
antigos mantêm o prazo original ou recalculam?

**Recomendação: SNAPSHOT IMUTÁVEL.** Adicionar coluna nova:

```sql
ALTER TABLE protocolos.processo
    ADD COLUMN prazo_servico_dias_snapshot INTEGER NULL;
```

- Preenchida 1× na abertura (com `servico.prazo_estimado_dias` corrente).
- Imutável depois — mesmo que o servidor edite o serviço.
- `prazo_previsto_em` = `data_hora_abertura + snapshot dias` (sempre
  calculada dinamicamente; só o **número de dias** é persistido).

**Justificativa:** o prazo é uma promessa publicada na Carta de Serviços no
momento da abertura. Se o servidor reduz de 30 → 15 dias depois, processos
antigos não podem virar "atrasados" retroativamente; se aumenta de 30 → 60,
não podem ganhar folga indevida. LAI/transparência espera estabilidade
histórica.

**Alternativa rejeitada:** cálculo 100% dinâmico (sempre lendo
`servico.prazo_estimado_dias` atual). Mais simples, evita migration — mas
quebra a promessa ao cidadão e cria inconsistência nos relatórios
históricos. Não vale a economia.

**Backfill da migration:** popular `prazo_servico_dias_snapshot` com o
valor atual de `servico.prazo_estimado_dias` para todo processo que tenha
`id_servico`. Documentar que os processos abertos ANTES do PR 5b recebem o
prazo vigente do serviço no momento da migration (não há como reconstruir
"qual era o prazo no dia da abertura" para esses).

### D-CONCLUSAO — incluir `concluido_no_prazo`/`concluido_atrasado` já no PR 5b?

**Decisão pedida:** "se houver base confiável de conclusão/arquivamento,
incluir; senão limitar a 4 status".

**Recomendação: SIM, incluir.** A base é confiável: o dashboard já usa
`Movimentacao.id_arquivamento IS NOT NULL` como sinal de conclusão (ver
[services/dashboard.py:126-143](../backend/app/services/dashboard.py#L126-L143)). Conclusão = data da
**última movimentação de arquivamento ativa** do processo.

Status final: **6 valores** (não 4):

- `sem_prazo`
- `dentro_do_prazo`
- `vencendo`
- `atrasado`
- `concluido_no_prazo`
- `concluido_atrasado`

Sem custo extra de modelagem — só uma comparação `data_arquivamento <=
prazo_previsto_em` no momento de classificar processos concluídos.

### D-VENCENDO — regra do limiar

**Recomendação: `limiar_dias = min(5, ceil(prazo_snapshot * 0.2))`** com
mínimo de 1 dia útil de janela.

- Prazo 30 → 5 dias (teto)
- Prazo 15 → 3 dias (20%)
- Prazo 5 → 1 dia
- Prazo 1 → 1 dia (piso)

`vencendo` = `0 ≤ dias_restantes ≤ limiar_dias`. Atrasado = `dias_restantes
< 0`. Regra única, sem configuração por tenant neste PR.

### D-LISTA — incluir prazo na lista de processos ou só no detalhe?

**Recomendação: SÓ NO DETALHE neste PR.** Cálculo de status na lista exige
JOIN extra com `servico` + agregação por linha; pode entrar em PR
posterior se for útil para filtros. No PR 5b a lista permanece como hoje;
apenas o detalhe ganha o bloco `prazo`. Dashboard usa o cálculo agregado,
não passa pela lista.

**Alternativa:** computar status na lista via VIEW materializada. Fora de
escopo do PR 5b.

### D-CIDADAO — expor no Portal do Cidadão neste PR?

**Recomendação: SIM, mas com payload reduzido.** Detalhe do processo no
Portal mostra apenas:

- `prazo_estimado_em` (data ISO)
- `status` num enum reduzido: `em_andamento` / `em_andamento_proximo_do_prazo`
  / `prazo_vencido` / `concluido`

**Não expor** dias contados, número exato em atraso, nem o termo "SLA".
Texto de UI: "Prazo estimado de atendimento" / "Previsão de conclusão" —
nunca "garantia" ou "vencimento". A linguagem segue o que a Carta de
Serviços já expõe publicamente.

**Alternativa conservadora:** deixar para PR 5c após validação jurídica
local. Decida você — se há dúvida regulatória no município-alvo, prefiro
deixar fora.

---

## 3. Modelo

### 3.1 Migration nova `0030_processo_prazo_snapshot.py`

Idempotente, padrão alembic do projeto:

```py
def upgrade() -> None:
    op.add_column(
        "processo",
        sa.Column("prazo_servico_dias_snapshot", sa.Integer(), nullable=True),
        schema="protocolos",
    )
    # Backfill: processos com id_servico recebem o prazo corrente do serviço.
    op.execute(
        """
        UPDATE protocolos.processo p
        SET prazo_servico_dias_snapshot = s.prazo_estimado_dias
        FROM protocolos.servico s
        WHERE p.id_servico = s.id
          AND p.tenant_id = s.tenant_id
          AND p.prazo_servico_dias_snapshot IS NULL
        """
    )
```

Sem índice extra. Não precisa de RLS adicional — coluna está em
`processo`, que já é tenant-scoped.

### 3.2 Modelo ORM

Adicionar 1 linha em [models/processo.py](../backend/app/models/processo.py):

```py
prazo_servico_dias_snapshot: Mapped[int | None] = mapped_column(
    Integer, nullable=True
)
```

### 3.3 Service novo `app/services/prazos.py`

Helper puro (sem I/O), reaproveitável por detalhe + dashboard + portal
cidadão:

```py
from datetime import datetime, timedelta
from math import ceil
from typing import Literal

StatusPrazo = Literal[
    "sem_prazo",
    "dentro_do_prazo",
    "vencendo",
    "atrasado",
    "concluido_no_prazo",
    "concluido_atrasado",
]

def calcular_limiar_vencendo(prazo_dias: int) -> int:
    return max(1, min(5, ceil(prazo_dias * 0.2)))

def status_prazo(
    *,
    data_abertura: datetime,
    prazo_snapshot_dias: int | None,
    data_conclusao: datetime | None,
    now: datetime,
) -> tuple[StatusPrazo, datetime | None, int | None]:
    """Devolve (status, prazo_previsto_em, dias_restantes_ou_atraso).

    `dias_restantes_ou_atraso` é positivo quando há folga, negativo quando
    em atraso, None quando sem_prazo.
    """
    if prazo_snapshot_dias is None:
        return ("sem_prazo", None, None)
    prazo_previsto = data_abertura + timedelta(days=prazo_snapshot_dias)
    if data_conclusao is not None:
        return (
            "concluido_no_prazo" if data_conclusao <= prazo_previsto
            else "concluido_atrasado",
            prazo_previsto,
            (prazo_previsto - data_conclusao).days,
        )
    delta_dias = (prazo_previsto - now).days
    if delta_dias < 0:
        return ("atrasado", prazo_previsto, delta_dias)
    if delta_dias <= calcular_limiar_vencendo(prazo_snapshot_dias):
        return ("vencendo", prazo_previsto, delta_dias)
    return ("dentro_do_prazo", prazo_previsto, delta_dias)
```

Sem dependência de SQLAlchemy. Testável isoladamente.

---

## 4. Backend — endpoints alterados

### 4.1 `GET /processos/{id}` — detalhe (admin)

Estender [schemas/processo.py](../backend/app/schemas/processo.py) `ProcessoDetail` com bloco novo:

```py
class PrazoInfo(BaseModel):
    status: StatusPrazo
    prazo_servico_dias_snapshot: int | None
    prazo_previsto_em: datetime | None
    dias_restantes_ou_atraso: int | None  # >0 folga, <0 atraso

class ProcessoDetail(BaseModel):
    # ... campos existentes ...
    prazo: PrazoInfo
```

No service de leitura, popular `prazo` com o helper. **Sem** alteração no
modelo de leitura; só uma pós-projeção.

### 4.2 `GET /dashboard/kpis` — bloco novo `prazos`

Estender [schemas/dashboard.py](../backend/app/schemas/dashboard.py):

```py
class PrazosKpis(BaseModel):
    # Snapshot (estado atual, processos não concluídos).
    sem_prazo: int
    dentro_do_prazo: int
    vencendo: int
    atrasado: int
    # Período (concluídos no recorte).
    concluido_no_prazo_periodo: int
    concluido_atrasado_periodo: int
    # Derivados.
    pct_dentro_do_prazo: float | None  # snapshot, exclui sem_prazo
    tempo_medio_atraso_dias: float | None  # média sobre atrasados+conc_atrasado

class DashboardKpis(BaseModel):
    # ... blocos existentes preservados ...
    prazos: PrazosKpis  # PR 5b
```

Estender `por_servico` e `por_unidade` (já é `BreakdownItem`) com campo
`atrasados`:

```py
class ServicoBreakdownItem(BaseModel):
    # ... existente ...
    atrasados: int  # PR 5b — processos não-concluídos com status='atrasado'
```

Cálculo no service: 1 query SQL agregada com `CASE WHEN` em
`prazo_servico_dias_snapshot + data_hora_abertura`. Sem N+1, sem chamar o
helper por processo. Honra `id_unidade` / `id_servico` /
`incluir_legado` via o `_aplicar_filtros_processo` já existente em
[services/dashboard.py:48-62](../backend/app/services/dashboard.py#L48-L62).

### 4.3 `GET /cidadao/processos/{id}` — portal do cidadão

Estender [schemas/cidadao.py](../backend/app/schemas/cidadao.py) `CidadaoProcessoDetail` com:

```py
class PrazoCidadao(BaseModel):
    prazo_estimado_em: datetime | None
    status: Literal[
        "em_andamento",
        "em_andamento_proximo_do_prazo",
        "prazo_vencido",
        "concluido",
    ]

class CidadaoProcessoDetail(BaseModel):
    # ... existente ...
    prazo: PrazoCidadao
```

Mapeamento `status_prazo` (admin) → `status` (cidadão):

| Admin | Cidadão |
|-------|---------|
| `sem_prazo` | `em_andamento` |
| `dentro_do_prazo` | `em_andamento` |
| `vencendo` | `em_andamento_proximo_do_prazo` |
| `atrasado` | `prazo_vencido` |
| `concluido_no_prazo` | `concluido` |
| `concluido_atrasado` | `concluido` |

Cidadão **não** vê "atrasado em X dias" nem "no prazo com X dias de
folga". Apenas o enum acima + a data prevista.

### 4.4 Abertura de processo

[services/abertura_processo.py](../backend/app/services/abertura_processo.py) — gravar o snapshot:

```py
servico = await load_servico(db, id_servico, tenant_id) if id_servico else None
processo.prazo_servico_dias_snapshot = (
    servico.prazo_estimado_dias if servico else None
)
```

1 linha de mudança. Idempotente: edições posteriores do serviço não tocam
no snapshot.

---

## 5. Dashboard — extensão da query

Estratégia: **1 query SQL com `CASE WHEN`** sobre `processo` somado a 1
query separada para `concluidos_periodo` (precisa do JOIN com
`movimentacao` arquivada — mesmo pattern de `_counts_intervalo`).

Pseudo-SQL do snapshot atual:

```sql
SELECT
    COUNT(*) FILTER (WHERE p.prazo_servico_dias_snapshot IS NULL) AS sem_prazo,
    COUNT(*) FILTER (
        WHERE p.prazo_servico_dias_snapshot IS NOT NULL
          AND (p.data_hora_abertura + p.prazo_servico_dias_snapshot * INTERVAL '1 day')
              - NOW() > (
                  LEAST(5, CEIL(p.prazo_servico_dias_snapshot * 0.2)) * INTERVAL '1 day'
              )
    ) AS dentro_do_prazo,
    COUNT(*) FILTER (
        WHERE p.prazo_servico_dias_snapshot IS NOT NULL
          AND NOW() <= (p.data_hora_abertura + p.prazo_servico_dias_snapshot * INTERVAL '1 day')
          AND (p.data_hora_abertura + p.prazo_servico_dias_snapshot * INTERVAL '1 day')
              - NOW() <= (
                  LEAST(5, CEIL(p.prazo_servico_dias_snapshot * 0.2)) * INTERVAL '1 day'
              )
    ) AS vencendo,
    COUNT(*) FILTER (
        WHERE p.prazo_servico_dias_snapshot IS NOT NULL
          AND NOW() > (p.data_hora_abertura + p.prazo_servico_dias_snapshot * INTERVAL '1 day')
    ) AS atrasado
FROM protocolos.processo p
WHERE p.tenant_id = :tenant_id
  AND p.excluido = false
  AND p.ativo = true
  -- + filtros de id_unidade / id_servico / incluir_legado
```

Concluídos no período: variação do `arq_stmt` existente
([dashboard.py:125-143](../backend/app/services/dashboard.py#L125-L143)) com `CASE WHEN data_arquivamento
<= prazo_previsto_em`.

**Por serviço (ranking de atrasados):** estender `_breakdown_servico`
([dashboard.py:502](../backend/app/services/dashboard.py#L502)) com 1 subquery a mais por linha
(`atrasados`). Reusa o pattern existente.

---

## 6. Frontend admin

### 6.1 Detalhe do processo

Em [app/(app)/processos/[id]/page.tsx](../frontend/app/(app)/processos/[id]/page.tsx) — junto dos badges
existentes (Ativo/Sigiloso/Externo do PR 5a-UX), incluir badge de prazo:

| Status | Badge intent | Ícone | Texto |
|--------|-------------|-------|-------|
| `dentro_do_prazo` | `success` | `Clock` | Dentro do prazo (X dias restantes) |
| `vencendo` | `warning` | `AlertTriangle` | Vencendo (X dias) |
| `atrasado` | `danger` | `AlertCircle` | Atrasado em X dias |
| `concluido_no_prazo` | `success` | `CheckCircle2` | Concluído no prazo |
| `concluido_atrasado` | `warning` | `CheckCircle2` | Concluído com atraso |
| `sem_prazo` | `neutral` | — | (não exibe badge) |

Bloco textual no card "Detalhes": "Prazo previsto: dd/mm/aaaa". Sob o
prazo, "Baseado no prazo estimado do serviço (X dias)".

### 6.2 Dashboard

Em [app/(app)/dashboard/page.tsx](../frontend/app/(app)/dashboard/page.tsx) — adicionar seção "Prazos
operacionais":

- 4 cards de snapshot: Sem prazo / Dentro / Vencendo / Atrasado.
- 1 card grande: % dentro do prazo.
- 1 card: tempo médio de atraso (em dias) — só se >0.
- Ranking dos 5 serviços com mais processos atrasados (lista textual).
- Ranking dos 5 unidades com mais processos atrasados.

Reaproveitar componentes do PR 5a (Card, ranking, filtros — `id_unidade`,
`id_servico`, `incluir_legado` já existem na URL e propagam).

### 6.3 Lista de processos

**Não muda neste PR** (ver D-LISTA).

---

## 7. Frontend cidadão

Em [app/cidadao/processos/[id]/page.tsx](../frontend/app/cidadao/processos/[id]/page.tsx) — abaixo da info
de "aberto em", incluir 1 linha:

- "Prazo estimado de atendimento: dd/mm/aaaa" (quando `prazo_estimado_em != null`)
- Badge único conforme tabela:

| Status cidadão | Badge | Texto |
|----------------|-------|-------|
| `em_andamento` | `info` | Em andamento |
| `em_andamento_proximo_do_prazo` | `warning` | Próximo do prazo |
| `prazo_vencido` | `danger` | Prazo estimado vencido |
| `concluido` | `success` | Concluído |

Em "Meus processos" (lista): nada novo. Só o detalhe.

Linguagem fixa em UI: "prazo estimado", "previsão". Nunca "garantido",
"vencimento contratual", "obrigação".

---

## 8. Permissões

- `/dashboard/kpis` — já exige permissão `dashboard` (PR 5a). Nada novo.
- `/processos/{id}` — já exige permissão `processo` + sigilo. Bloco
  `prazo` herda. Sem novo gate.
- `/cidadao/processos/{id}` — autenticação cidadão por CPF/CNPJ + dono do
  processo (regra existente). Sem novo gate.

Não cria transação nova. Não toca `0028_dashboard_perm`.

---

## 9. LGPD

- Payload `prazos` no dashboard: agregados (counts, médias, %), sem
  `processo.id` no bloco.
- Ranking por serviço/unidade: nome do serviço/unidade + counts. Nenhum
  CPF, nome de cidadão, corpo de pedido, mensagem ou documento.
- Detalhe admin: prazo é metadado operacional (não-pessoal). Sigilo
  segue regra existente (`require_visibilidade(processo)`).
- Detalhe cidadão: já filtrado pelo dono do processo.
- Teste valida ausência de PII no `/dashboard/kpis` (mesmo padrão dos
  testes PR 5a).

---

## 10. Testes obrigatórios

### Backend (`backend/tests/test_prazos.py` + extensões)

Helper puro (`status_prazo`):

1. `prazo_snapshot_dias=None` → `sem_prazo`.
2. Concluído antes do prazo → `concluido_no_prazo` + dias positivos.
3. Concluído após o prazo → `concluido_atrasado` + dias negativos.
4. Em andamento, folga > limiar → `dentro_do_prazo`.
5. Em andamento, folga ≤ limiar → `vencendo`.
6. Em andamento, prazo já passou → `atrasado` + dias negativos.
7. Limiar: prazo=30 → 5d; prazo=15 → 3d; prazo=5 → 1d.

Abertura (`test_abertura_processo.py` — extensão):

8. Abrir processo com `id_servico` → `prazo_servico_dias_snapshot` =
   valor do serviço naquele momento.
9. Editar serviço depois → snapshot do processo antigo **não muda**
   (regra crítica do D-SNAPSHOT).
10. Abrir processo sem `id_servico` → `prazo_servico_dias_snapshot` é
    `None`.

Endpoint detalhe (`test_processos.py` — extensão):

11. Detalhe traz `prazo` com `status` correto p/ processo recém-aberto.
12. Detalhe de processo arquivado dentro do prazo → `concluido_no_prazo`.
13. Detalhe de processo legado (`id_servico=None`) → `status=sem_prazo`,
    `prazo_previsto_em=null`.

Dashboard (`test_dashboard.py` — extensão):

14. Bloco `prazos` agrega contadores corretamente em fixtures com mix de
    status.
15. Filtro `id_servico` propaga p/ `prazos` (PR 5b respeita o pattern do PR 5a).
16. Filtro `id_unidade` propaga p/ `prazos`.
17. Filtro `incluir_legado=false` zera `sem_prazo` p/ processos com
    `id_servico=null`.
18. Ranking `por_servico` traz coluna `atrasados`.
19. RLS: tenant B não vê contadores de tenant A.
20. LGPD: nenhum CPF/nome/mensagem no payload.

### Frontend (`tests-e2e/specs/prazos.spec.ts`)

1. Detalhe admin de processo dentro do prazo mostra badge de status correto.
2. Detalhe admin de processo atrasado mostra badge `danger` + "X dias em atraso".
3. Detalhe admin de processo legado **não** mostra badge de prazo.
4. Dashboard mostra 4 cards de prazo (Sem prazo / Dentro / Vencendo / Atrasado).
5. Filtro de serviço no dashboard altera os cards de prazo.
6. Detalhe cidadão mostra "Prazo estimado de atendimento" + badge curto.
7. Detalhe cidadão **não** mostra contagem em dias (segurança jurídica).

---

## 11. Fora de escopo (reafirmado)

Nada do que segue entra no PR 5b — fica para PRs posteriores se for
contratado:

- Notificações por e-mail / SMS / WhatsApp / push de prazo.
- Alertas em tela em tempo real.
- Indeferimento ou arquivamento automático por prazo.
- Workflow complexo com etapas com prazo próprio (já existe via
  `WorkflowSlaAlerta`, não é mexido aqui).
- Calendário de feriados municipais.
- Dias úteis (PR 5b conta dias corridos).
- Suspensão automática de prazo durante complementação aberta.
- Reabertura de prazo após complementação respondida.
- Pausa manual de prazo por servidor.
- SLA contratual com clientes / cláusulas penais / cobrança.
- Dashboard global da plataforma SaaS (cross-tenant).
- IA / sugestão de prazo / previsão preditiva.

---

## 12. Entregáveis e ordem de implementação (quando autorizado)

1. Migration `0030_processo_prazo_snapshot.py` (idempotente, com
   backfill).
2. Coluna no ORM + `app/services/prazos.py` + testes unitários do helper.
3. Gravação do snapshot em `services/abertura_processo.py` + testes.
4. Bloco `prazo` em `ProcessoDetail` (schema + service) + testes.
5. Bloco `prazos` + `atrasados` por_servico/por_unidade no dashboard
   (schema + SQL agregado + testes).
6. Bloco `prazo` em `CidadaoProcessoDetail` + mapeamento de status
   reduzido + testes.
7. Frontend admin: badge no detalhe + cards no dashboard + filtros
   propagados.
8. Frontend cidadão: badge + texto cuidadoso + nenhum número.
9. e2e (Playwright) cobrindo os 7 cenários.

Mantém o padrão de revisão do PR 5a: backend primeiro, frontend depois,
1 commit por camada.

---

## 13. Decisões pendentes p/ fechar antes de codar

1. **D-SNAPSHOT** — snapshot imutável (recomendado) ou cálculo dinâmico?
2. **D-CONCLUSAO** — incluir 2 status de conclusão já agora (recomendado)
   ou só os 4 ativos?
3. **D-VENCENDO** — `min(5, ceil(prazo * 0.2))` (recomendado) ou
   parametrizável por tenant?
4. **D-LISTA** — só detalhe (recomendado) ou já na lista também?
5. **D-CIDADAO** — expor já neste PR (recomendado) ou postergar p/ PR 5c
   após revisão jurídica?

Aguardando sua decisão antes de começar a implementação.
