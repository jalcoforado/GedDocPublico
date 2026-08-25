# PR 5b — Escopo Implementável: Prazos por serviço

**Autor:** Jorge + assistente · **Status:** ESCOPO FECHADO (aguardando autorização para implementar)

> Consolida a [proposta](dashboard-pr5b-sla-prazos-servico-escopo.md) com as
> **6 decisões (D-SNAPSHOT / D-NOME / D-CONCLUSAO / D-VENCENDO / D-LISTA /
> D-CIDADAO)** fechadas. Transforma `servico.prazo_estimado_dias` em
> controle operacional end-to-end do processo, complementando — sem colidir —
> o SLA por nó do workflow já existente (`WorkflowSlaAlerta`). Estende o
> dashboard executivo do PR 5a com bloco `prazos` e o detalhe do processo
> (admin + cidadão) com previsão e status. **Não** introduz dias úteis,
> feriados, suspensão de prazo, notificações nem reabertura. **Nada será
> alterado em código até autorização explícita.**

---

## 1. Decisões travadas

| Tag | Decisão |
|-----|---------|
| **D-SNAPSHOT** | Persistir snapshot imutável (`processo.prazo_servico_dias_snapshot`). Mudanças no `servico.prazo_estimado_dias` **não** afetam processos já abertos. |
| **D-NOME** | Bloco novo se chama **`prazos`**, campos usam **`prazo_servico_*`** e **`status_prazo`**. Não usar "sla" no PR 5b — reservado para `WorkflowSlaAlerta` existente. |
| **D-CONCLUSAO** | 6 status: `sem_prazo`, `dentro_do_prazo`, `vencendo`, `atrasado`, `concluido_no_prazo`, `concluido_atrasado`. Conclusão = última `Movimentacao` ativa com `id_arquivamento IS NOT NULL`. Fallback: sem movimentação de arquivamento ativa → tratar como "em andamento" (não usar `processo.ativo` como proxy, pois pode ser desligado por outra razão). |
| **D-VENCENDO** | `limiar_dias = max(1, ceil(prazo_snapshot * 0.2))`. Regra **única**, sem teto de 5 dias (correção vs. proposta) — usuário pediu 20% com mínimo de 1; sem teto deixa serviços longos com janela maior, que é o comportamento esperado. SQL trivial: `CEIL(prazo * 0.2)` com `GREATEST(1, …)`. |
| **D-LISTA** | Lista geral de processos **não** muda neste PR. Detalhe (admin + cidadão) + dashboard. |
| **D-CIDADAO** | Visão reduzida: 5 valores de `status_prazo_cidadao` (`sem_previsao` / `dentro_da_previsao` / `proximo_do_prazo` / `fora_da_previsao` / `concluido`) + `prazo_estimado_em` (data ISO). **Sem** contagem de dias. Linguagem: "prazo estimado", "previsão de atendimento", "situação do prazo". **Proibido**: "garantia", "SLA", "prazo legal". |

**LGPD (regra travada do PR 5a, repetida aqui):** payload aceita apenas
agregados, IDs e nomes de serviço/unidade. **Nunca** CPF, nome do cidadão,
`corpo`, `observacao`, mensagem de complementação, motivo de cancelamento,
nome de arquivo nem conteúdo. Teste valida ausência.

---

## 2. Migration `0029_processo_prazo_snapshot`

Próxima revisão livre (a última é [`0028_dashboard_perm.py`](../backend/alembic/versions/0028_dashboard_perm.py)).
Padrão: 1 coluna nullable + backfill condicional, idempotente, downgrade
seguro.

```python
# backend/alembic/versions/0029_processo_prazo_snapshot.py
"""Snapshot do prazo do serviço no processo (PR 5b).

Revision ID: 0029
Revises: 0028
Create Date: 2026-06-04

Adiciona `protocolos.processo.prazo_servico_dias_snapshot` (INT nullable)
para congelar `servico.prazo_estimado_dias` no momento da abertura. Mudanças
posteriores no prazo do serviço NÃO afetam processos já abertos
(decisão D-SNAPSHOT do PR 5b).

Backfill: processos com `id_servico` IS NOT NULL recebem o valor corrente
de `servico.prazo_estimado_dias`. Processos legados (sem id_servico) ou com
serviço sem prazo definido ficam com snapshot NULL.

Coluna herda RLS e GRANTs do schema `protocolos.processo` (Fase 0006).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | Sequence[str] | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Adiciona coluna nullable — não bloqueia escritas concorrentes.
    op.add_column(
        "processo",
        sa.Column("prazo_servico_dias_snapshot", sa.Integer(), nullable=True),
        schema="protocolos",
    )

    # 2. Backfill: copia prazo do serviço para processos já abertos.
    # Mesmo tenant_id em ambos os lados (defesa em profundidade — FK já garante).
    op.execute(
        """
        UPDATE protocolos.processo p
        SET prazo_servico_dias_snapshot = s.prazo_estimado_dias
        FROM protocolos.servico s
        WHERE p.id_servico = s.id
          AND p.tenant_id = s.tenant_id
          AND p.prazo_servico_dias_snapshot IS NULL
          AND s.prazo_estimado_dias IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column(
        "processo", "prazo_servico_dias_snapshot", schema="protocolos"
    )
```

**Sem índice extra.** A coluna entra em queries agregadas com filtros já
indexados (`tenant_id`, `id_servico`, `data_hora_abertura`). Caso o EXPLAIN
do dashboard mostre seq scan no futuro, índice composto pode ser adicionado
em PR seguinte.

---

## 3. ORM

1 linha em [models/processo.py](../backend/app/models/processo.py) (logo após `id_servico` para
manter agrupamento PR 5b/5b):

```python
# PR 5b — snapshot do prazo do serviço no momento da abertura. Imutável.
# None = processo sem serviço OU serviço sem prazo definido.
prazo_servico_dias_snapshot: Mapped[int | None] = mapped_column(
    Integer, nullable=True
)
```

---

## 4. Helper puro `app/services/prazos.py`

Lib pequena, sem I/O, testável isoladamente. Único ponto de cálculo de
status — reutilizado por detalhe admin, detalhe cidadão, dashboard e
testes.

```python
# backend/app/services/prazos.py
"""Cálculo de prazo end-to-end de processo, baseado em snapshot do serviço.

PR 5b. Função pura: recebe dados já carregados, devolve dados derivados.
Não acessa banco. Não conhece schemas Pydantic. Reutilizada por:
- routers/processos detail
- routers/cidadao detail (com mapeamento reduzido)
- services/dashboard (cálculos agregados; ver dashboard.py para versão SQL)
- testes
"""
from __future__ import annotations

from dataclasses import dataclass
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

StatusPrazoCidadao = Literal[
    "sem_previsao",
    "dentro_da_previsao",
    "proximo_do_prazo",
    "fora_da_previsao",
    "concluido",
]


@dataclass(frozen=True)
class PrazoCalculado:
    status: StatusPrazo
    prazo_servico_dias_snapshot: int | None
    prazo_previsto_em: datetime | None
    dias_restantes: int | None  # >0 quando há folga; None quando sem_prazo
    dias_atraso: int | None     # >0 quando em atraso; None se não atrasado
    concluido_em: datetime | None


def limiar_vencendo_dias(prazo_snapshot_dias: int) -> int:
    """20% do prazo, com mínimo de 1 dia. Sem teto.

    Prazo 30 → 6 dias; prazo 10 → 2 dias; prazo 3 → 1 dia; prazo 1 → 1 dia.
    """
    if prazo_snapshot_dias <= 0:
        return 1
    return max(1, ceil(prazo_snapshot_dias * 0.2))


def calcular_prazo(
    *,
    data_abertura: datetime,
    prazo_snapshot_dias: int | None,
    data_conclusao: datetime | None,
    now: datetime,
) -> PrazoCalculado:
    """Calcula status e datas derivadas.

    - `data_conclusao` = data da última Movimentacao ativa de arquivamento.
      None quando o processo segue em andamento.
    - `data_conclusao` sem `prazo_snapshot_dias` ainda devolve `sem_prazo`
      (legado concluído também é sem_prazo — a categorização exige snapshot).
    """
    if prazo_snapshot_dias is None:
        return PrazoCalculado(
            status="sem_prazo",
            prazo_servico_dias_snapshot=None,
            prazo_previsto_em=None,
            dias_restantes=None,
            dias_atraso=None,
            concluido_em=data_conclusao,
        )

    prazo_previsto = data_abertura + timedelta(days=prazo_snapshot_dias)

    if data_conclusao is not None:
        no_prazo = data_conclusao <= prazo_previsto
        delta = (prazo_previsto - data_conclusao).days
        return PrazoCalculado(
            status="concluido_no_prazo" if no_prazo else "concluido_atrasado",
            prazo_servico_dias_snapshot=prazo_snapshot_dias,
            prazo_previsto_em=prazo_previsto,
            dias_restantes=delta if no_prazo else None,
            dias_atraso=(-delta) if not no_prazo else None,
            concluido_em=data_conclusao,
        )

    delta = (prazo_previsto - now).days
    if delta < 0:
        return PrazoCalculado(
            status="atrasado",
            prazo_servico_dias_snapshot=prazo_snapshot_dias,
            prazo_previsto_em=prazo_previsto,
            dias_restantes=None,
            dias_atraso=-delta,
            concluido_em=None,
        )
    if delta <= limiar_vencendo_dias(prazo_snapshot_dias):
        return PrazoCalculado(
            status="vencendo",
            prazo_servico_dias_snapshot=prazo_snapshot_dias,
            prazo_previsto_em=prazo_previsto,
            dias_restantes=delta,
            dias_atraso=None,
            concluido_em=None,
        )
    return PrazoCalculado(
        status="dentro_do_prazo",
        prazo_servico_dias_snapshot=prazo_snapshot_dias,
        prazo_previsto_em=prazo_previsto,
        dias_restantes=delta,
        dias_atraso=None,
        concluido_em=None,
    )


_CIDADAO_MAP: dict[StatusPrazo, StatusPrazoCidadao] = {
    "sem_prazo": "sem_previsao",
    "dentro_do_prazo": "dentro_da_previsao",
    "vencendo": "proximo_do_prazo",
    "atrasado": "fora_da_previsao",
    "concluido_no_prazo": "concluido",
    "concluido_atrasado": "concluido",
}


def status_cidadao(status_admin: StatusPrazo) -> StatusPrazoCidadao:
    """Mapeamento p/ portal cidadão. Concluído (no prazo ou com atraso)
    vira sempre 'concluido' — o cidadão não recebe juízo de valor sobre
    a tempestividade do atendimento."""
    return _CIDADAO_MAP[status_admin]
```

Notas de design:

- **Fallback de conclusão (D-CONCLUSAO).** `data_conclusao` é responsabilidade
  do chamador (resolver via última `Movimentacao` ativa de arquivamento).
  Se nenhuma movimentação de arquivamento ativa existir, passa `None` → o
  helper trata como "em andamento". **Não** usar `processo.ativo` como
  proxy — esse flag pode ser desligado por outras razões.
- **Sem teto no limiar.** Diferença vs. proposta inicial — usuário pediu
  20% com mínimo de 1; sem teto deixa serviços longos (90 dias → 18 dias
  de janela "vencendo") com a janela proporcional esperada.

---

## 5. Abertura — grava o snapshot

A abertura por serviço **só acontece pelo portal do cidadão** hoje. O
admin abre processo via [services/abertura_processo.py](../backend/app/services/abertura_processo.py) **sem**
`id_servico` (deixa em legado por definição). Portanto, **uma única
mudança** em [services/cidadao_processos.py](../backend/app/services/cidadao_processos.py) cobre todos
os pontos onde `id_servico` é gravado:

**Linhas a tocar:** `cidadao_processos.py:384` e `:563` — ambos constroem
o `Processo` com `id_servico=servico.id`. Logo após carregar o `servico`,
incluir:

```python
processo.prazo_servico_dias_snapshot = servico.prazo_estimado_dias
# `prazo_estimado_dias` é Optional[int] em Servico — snapshot fica None
# quando o serviço da Carta não tem prazo definido. Regra D-SNAPSHOT:
# nunca recalcula depois.
```

**Defesa em profundidade:** acrescentar uma asserção opcional no helper de
abertura cidadã para garantir que `prazo_servico_dias_snapshot` só seja
escrito uma vez (não há rota administrativa que edite snapshot, mas vale
um teste de regressão).

**Sem mudança em `abertura_processo.py`** — admin sem `id_servico` deixa
snapshot None, que é coerente com `status=sem_prazo`.

---

## 6. Endpoint admin — detalhe do processo

### 6.1 Schema

Estender [schemas/processo.py](../backend/app/schemas/processo.py):

```python
class PrazoInfo(BaseModel):
    """Bloco de prazo no detalhe do processo (admin). PR 5b."""

    status: Literal[
        "sem_prazo",
        "dentro_do_prazo",
        "vencendo",
        "atrasado",
        "concluido_no_prazo",
        "concluido_atrasado",
    ]
    prazo_servico_dias_snapshot: int | None
    prazo_previsto_em: datetime | None
    dias_restantes: int | None  # >0 quando há folga
    dias_atraso: int | None     # >0 quando em atraso
    concluido_em: datetime | None
    origem: Literal["servico"] | None  # None quando sem_prazo


class ProcessoDetail(BaseModel):
    # ... campos existentes preservados byte-a-byte ...
    prazo: PrazoInfo  # PR 5b
```

### 6.2 Service

Em [services/processos.py](../backend/app/services/processos.py), no carregamento do detalhe:

1. Buscar a última `Movimentacao` ativa com `id_arquivamento IS NOT NULL`
   do processo (1 query agregada — já existe lógica próxima em
   `_montar_movimentacoes`). Capturar `data_conclusao`.
2. Chamar `prazos.calcular_prazo(...)` com `data_hora_abertura`,
   `prazo_servico_dias_snapshot`, `data_conclusao`, `now`.
3. Projetar o resultado em `PrazoInfo` (origem é `"servico"` quando
   `prazo_servico_dias_snapshot is not None`, senão `None`).

**Permissão:** herda a do endpoint atual (`processo` + sigilo). Sem novo
gate.

### 6.3 Endpoint

[routers/processos.py](../backend/app/routers/processos.py) — sem mudança de rota; o response model
é o `ProcessoDetail` estendido. Backward-compatível: clients antigos
ignoram o bloco novo.

---

## 7. Endpoint cidadão — detalhe reduzido

### 7.1 Schema

Estender [schemas/cidadao.py](../backend/app/schemas/cidadao.py):

```python
class PrazoCidadao(BaseModel):
    """Visão reduzida do prazo no portal do cidadão. PR 5b — D-CIDADAO.

    Sem contagem de dias. Status num enum cuidadoso. Linguagem em UI:
    "prazo estimado de atendimento" / "previsão" / "situação do prazo".
    """

    prazo_estimado_em: datetime | None
    status: Literal[
        "sem_previsao",
        "dentro_da_previsao",
        "proximo_do_prazo",
        "fora_da_previsao",
        "concluido",
    ]


class CidadaoProcessoDetail(BaseModel):
    # ... campos existentes ...
    prazo: PrazoCidadao  # PR 5b
```

### 7.2 Service

Em [services/cidadao_processos.py](../backend/app/services/cidadao_processos.py), no detalhe (rota
`getProcesso`):

1. Mesmo fetch de `data_conclusao` que o detalhe admin.
2. Chama `prazos.calcular_prazo(...)`.
3. Aplica `prazos.status_cidadao(resultado.status)`.
4. Devolve `PrazoCidadao(prazo_estimado_em=resultado.prazo_previsto_em,
   status=...)`.

Cidadão **nunca** vê: `dias_restantes`, `dias_atraso`,
`prazo_servico_dias_snapshot`, `concluido_em` (estes nomes não aparecem
no payload reduzido).

---

## 8. Dashboard — bloco `prazos`

### 8.1 Schema

Estender [schemas/dashboard.py](../backend/app/schemas/dashboard.py) (preservando todos os campos
existentes do PR 5a):

```python
class PrazosKpis(BaseModel):
    """Indicadores de prazo end-to-end. PR 5b.

    Snapshot atual (processos NÃO concluídos):
    """
    sem_prazo: int
    dentro_do_prazo: int
    vencendo: int
    atrasado: int

    """Período (processos concluídos no recorte):"""
    concluido_no_prazo_periodo: int
    concluido_atrasado_periodo: int

    """Derivados (None quando denominador zero):"""
    percentual_no_prazo: float | None       # snapshot — exclui sem_prazo
    tempo_medio_atraso_dias: float | None   # média sobre atrasado + concluido_atrasado_periodo


class ServicoBreakdownItem(BaseModel):
    # ... campos do PR 5a preservados ...
    atrasados: int  # PR 5b — processos NÃO concluídos com status='atrasado'


class DashboardKpis(BaseModel):
    # ... blocos PR 5a preservados ...
    prazos: PrazosKpis  # PR 5b
```

**Atenção:** `sla: SlaKpis` (do PR 5a, alimentado pelo workflow) **fica
intocado**. O novo `prazos: PrazosKpis` é independente. Frontend desenha
os dois lado a lado se for o caso, mas isso é decisão visual — backend
não os mistura.

### 8.2 Cálculo SQL

Adicionar função em [services/dashboard.py](../backend/app/services/dashboard.py):

```python
async def _prazos_kpis(
    db: AsyncSession,
    *,
    tenant_id: int,
    desde: datetime,
    ate: datetime,
    id_unidade: int | None,
    id_servico: int | None,
    incluir_legado: bool,
) -> dict[str, Any]:
    """Computa bloco `prazos` agregado. 2 queries SQL (snapshot + período).

    Snapshot conta processos NÃO concluídos (sem Movimentacao ativa de
    arquivamento). Período conta processos concluídos por arquivamento no
    intervalo [desde, ate).

    Honra filtros do gestor via `_aplicar_filtros_processo` /
    `_processo_filtros_sql` (PR 5a). Sem N+1, sem chamar helper Python
    por linha — a regra de status é replicada em SQL puro.
    """
    extra_where, extra_params = _processo_filtros_sql(
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )
    extra_clause = f" AND {extra_where}" if extra_where else ""

    # ===== Snapshot — processos NÃO concluídos =====
    sql_snapshot = text(f"""
        WITH em_andamento AS (
            SELECT p.id,
                   p.data_hora_abertura,
                   p.prazo_servico_dias_snapshot AS snap
            FROM protocolos.processo p
            WHERE p.tenant_id = :tenant_id
              AND p.excluido = false
              AND NOT EXISTS (
                  SELECT 1
                  FROM protocolos.movimentacao mv
                  WHERE mv.id_processo = p.id
                    AND mv.tenant_id = :tenant_id
                    AND mv.excluido = false
                    AND mv.ativo = true
                    AND mv.id_arquivamento IS NOT NULL
              )
              {extra_clause}
        ),
        com_prazo AS (
            SELECT id,
                   data_hora_abertura + (snap * INTERVAL '1 day') AS prazo_previsto,
                   GREATEST(1, CEIL(snap * 0.2)) AS limiar
            FROM em_andamento
            WHERE snap IS NOT NULL
        )
        SELECT
            (SELECT COUNT(*) FROM em_andamento WHERE snap IS NULL) AS sem_prazo,
            COUNT(*) FILTER (
                WHERE (prazo_previsto - NOW()) > (limiar * INTERVAL '1 day')
            ) AS dentro_do_prazo,
            COUNT(*) FILTER (
                WHERE NOW() <= prazo_previsto
                  AND (prazo_previsto - NOW()) <= (limiar * INTERVAL '1 day')
            ) AS vencendo,
            COUNT(*) FILTER (WHERE NOW() > prazo_previsto) AS atrasado,
            AVG(EXTRACT(EPOCH FROM (NOW() - prazo_previsto)) / 86400.0)
                FILTER (WHERE NOW() > prazo_previsto) AS atraso_medio_andamento,
            COUNT(*) FILTER (WHERE NOW() > prazo_previsto) AS qtd_atrasado_for_avg
        FROM com_prazo;
    """)
    snap_row = (await db.execute(
        sql_snapshot,
        {"tenant_id": tenant_id, **extra_params},
    )).one()

    # ===== Período — concluídos por arquivamento em [desde, ate) =====
    # Última Movimentacao ativa de arquivamento por processo (LATERAL join).
    sql_periodo = text(f"""
        WITH ultimo_arquiv AS (
            SELECT DISTINCT ON (mv.id_processo)
                   mv.id_processo,
                   mv.data_hora_movimentacao AS data_conclusao
            FROM protocolos.movimentacao mv
            WHERE mv.tenant_id = :tenant_id
              AND mv.excluido = false
              AND mv.ativo = true
              AND mv.id_arquivamento IS NOT NULL
              AND mv.data_hora_movimentacao >= :desde
              AND mv.data_hora_movimentacao <  :ate
            ORDER BY mv.id_processo, mv.data_hora_movimentacao DESC
        ),
        concluidos AS (
            SELECT p.id,
                   p.data_hora_abertura,
                   p.prazo_servico_dias_snapshot AS snap,
                   ua.data_conclusao
            FROM ultimo_arquiv ua
            JOIN protocolos.processo p ON p.id = ua.id_processo
            WHERE p.tenant_id = :tenant_id
              AND p.excluido = false
              {extra_clause}
        )
        SELECT
            COUNT(*) FILTER (
                WHERE snap IS NOT NULL
                  AND data_conclusao <= data_hora_abertura + (snap * INTERVAL '1 day')
            ) AS concluido_no_prazo,
            COUNT(*) FILTER (
                WHERE snap IS NOT NULL
                  AND data_conclusao >  data_hora_abertura + (snap * INTERVAL '1 day')
            ) AS concluido_atrasado,
            AVG(
                EXTRACT(
                    EPOCH FROM (data_conclusao
                                - (data_hora_abertura + (snap * INTERVAL '1 day')))
                ) / 86400.0
            ) FILTER (
                WHERE snap IS NOT NULL
                  AND data_conclusao >  data_hora_abertura + (snap * INTERVAL '1 day')
            ) AS atraso_medio_concluidos,
            COUNT(*) FILTER (
                WHERE snap IS NOT NULL
                  AND data_conclusao >  data_hora_abertura + (snap * INTERVAL '1 day')
            ) AS qtd_concluido_atrasado_for_avg
        FROM concluidos;
    """)
    per_row = (await db.execute(
        sql_periodo,
        {"tenant_id": tenant_id, "desde": desde, "ate": ate, **extra_params},
    )).one()

    # ===== Derivados =====
    sem_prazo = int(snap_row.sem_prazo or 0)
    dentro = int(snap_row.dentro_do_prazo or 0)
    vencendo = int(snap_row.vencendo or 0)
    atrasado = int(snap_row.atrasado or 0)
    conc_no_prazo = int(per_row.concluido_no_prazo or 0)
    conc_atrasado = int(per_row.concluido_atrasado or 0)

    com_prazo_andamento = dentro + vencendo + atrasado
    pct = (
        round(((dentro + vencendo) / com_prazo_andamento) * 100, 1)
        if com_prazo_andamento > 0
        else None
    )

    # Tempo médio de atraso: média ponderada do atraso de em-andamento atrasado
    # E do atraso de concluídos atrasado no período.
    qtd_at_a = int(snap_row.qtd_atrasado_for_avg or 0)
    qtd_at_c = int(per_row.qtd_concluido_atrasado_for_avg or 0)
    soma_at = (
        (float(snap_row.atraso_medio_andamento or 0.0) * qtd_at_a)
        + (float(per_row.atraso_medio_concluidos or 0.0) * qtd_at_c)
    )
    qtd_total_at = qtd_at_a + qtd_at_c
    tempo_medio_atraso = (
        round(soma_at / qtd_total_at, 1) if qtd_total_at > 0 else None
    )

    return {
        "sem_prazo": sem_prazo,
        "dentro_do_prazo": dentro,
        "vencendo": vencendo,
        "atrasado": atrasado,
        "concluido_no_prazo_periodo": conc_no_prazo,
        "concluido_atrasado_periodo": conc_atrasado,
        "percentual_no_prazo": pct,
        "tempo_medio_atraso_dias": tempo_medio_atraso,
    }
```

### 8.3 Estender `_breakdown_servico`

Em [services/dashboard.py:502-819](../backend/app/services/dashboard.py#L502), adicionar 1 subquery
escalar por linha do ranking para `atrasados` (mesmo padrão de
`complementacoes_abertas`):

```sql
(
    SELECT COUNT(*)
    FROM protocolos.processo pp
    WHERE pp.tenant_id = :tenant_id
      AND pp.excluido = false
      AND pp.id_servico = s.id
      AND pp.prazo_servico_dias_snapshot IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM protocolos.movimentacao mv
          WHERE mv.id_processo = pp.id
            AND mv.tenant_id = :tenant_id
            AND mv.excluido = false
            AND mv.ativo = true
            AND mv.id_arquivamento IS NOT NULL
      )
      AND NOW() > pp.data_hora_abertura + (pp.prazo_servico_dias_snapshot * INTERVAL '1 day')
      {pp_id_unidade_clause}
) AS atrasados
```

E preencher `breakdown[i]["atrasados"]`. Linha "(sem serviço)" recebe
`atrasados: 0` (legado é `sem_prazo` por definição).

### 8.4 Plug no `kpis()`

Em [services/dashboard.py:822](../backend/app/services/dashboard.py#L822) (função principal), incluir
chamada:

```python
prazos = await _prazos_kpis(
    db,
    tenant_id=tenant_id,
    desde=desde_atual,
    ate=now,
    id_unidade=id_unidade,
    id_servico=id_servico,
    incluir_legado=incluir_legado,
)
```

E adicionar `"prazos": prazos` no `return` final.

### 8.5 Endpoints `export.csv` / `export.pdf`

[services/dashboard_export.py](../backend/app/services/dashboard_export.py) — adicionar seção
`[Prazos]` no CSV multi-seção (mesmo padrão de `[Documental]` /
`[Complementação]` do PR 5a) e bloco análogo no PDF. Sem novos parâmetros
nem novos endpoints.

### 8.6 Permissão

`/dashboard/kpis`, `/dashboard/export.csv`, `/dashboard/export.pdf` já
exigem `require_permission("dashboard")` (PR 5a). **Sem mudança.**

---

## 9. Frontend admin

### 9.1 Detalhe do processo

Em [app/(app)/processos/[id]/page.tsx](../frontend/app/(app)/processos/[id]/page.tsx) — junto dos
badges existentes (Ativo/Sigiloso/Externo), incluir badge novo de prazo:

| `status` | Badge intent | Ícone Lucide | Texto |
|----------|-------------|--------------|-------|
| `dentro_do_prazo` | `success` | `Clock` | Dentro do prazo (`dias_restantes` dias restantes) |
| `vencendo` | `warning` | `AlertTriangle` | Vencendo (`dias_restantes` d.) |
| `atrasado` | `danger` | `AlertCircle` | Atrasado em `dias_atraso` d. |
| `concluido_no_prazo` | `success` | `CheckCircle2` | Concluído no prazo |
| `concluido_atrasado` | `warning` | `CheckCircle2` | Concluído com atraso |
| `sem_prazo` | (não renderiza badge) | — | — |

Bloco textual abaixo dos badges:

- "Prazo previsto: dd/mm/aaaa" (do `prazo_previsto_em`)
- "Baseado no prazo estimado do serviço (`prazo_servico_dias_snapshot` dias)"

Tipos TypeScript em [lib/api.ts](../frontend/lib/api.ts) — adicionar `PrazoInfo` e estender
`ProcessoDetail`. Sem mudança de URL nem de método.

### 9.2 Dashboard

Em [app/(app)/dashboard/page.tsx](../frontend/app/(app)/dashboard/page.tsx) — adicionar seção
"Prazos operacionais" abaixo da seção SLA do PR 5a:

- **4 cards de snapshot:** Sem prazo / Dentro / Vencendo / Atrasado.
  Usa o componente Card já existente, com Badge correspondente.
- **1 card grande:** `percentual_no_prazo` em destaque (oculto se `null`).
- **1 card menor:** `tempo_medio_atraso_dias` (oculto se `null`).
- **Ranking top 5 serviços com mais `atrasados`** — lista textual a
  partir do `por_servico` já existente (campo novo `atrasados`).

Filtros propagam automaticamente (são da URL — `periodo`, `id_unidade`,
`id_servico`, `incluir_legado`).

### 9.3 Lista de processos

**Sem alteração** (D-LISTA). Lista geral fica como hoje.

---

## 10. Frontend cidadão

### 10.1 Detalhe do processo

Em [app/cidadao/processos/[id]/page.tsx](../frontend/app/cidadao/processos/[id]/page.tsx) — abaixo do
título do processo (junto da data de abertura), incluir 1 linha:

- "Prazo estimado de atendimento: dd/mm/aaaa" (quando
  `prazo.prazo_estimado_em != null`)
- Badge único:

| `prazo.status` | Badge intent | Texto |
|----------------|-------------|-------|
| `sem_previsao` | `neutral` | Sem previsão |
| `dentro_da_previsao` | `info` | Dentro da previsão |
| `proximo_do_prazo` | `warning` | Próximo do prazo |
| `fora_da_previsao` | `danger` | Fora da previsão |
| `concluido` | `success` | Concluído |

**Tipos TypeScript** em [lib/api.ts](../frontend/lib/api.ts) — adicionar `PrazoCidadao` e
estender `CidadaoProcessoDetail`.

**Linguagem fixa em UI cidadão**: "prazo estimado", "previsão de
atendimento", "situação do prazo". **Vetadas:** "garantia", "SLA",
"prazo legal garantido", "vencimento contratual".

### 10.2 Lista cidadão

**Sem alteração.** Status reduzido aparece só no detalhe.

---

## 11. Segurança / LGPD

- Bloco `prazos` no dashboard: counts, médias e %. Nenhum `processo.id`,
  CPF, nome, corpo, observação, documento, mensagem ou motivo.
- Bloco `prazo` no detalhe admin: metadado operacional. Sigilo segue regra
  vigente do detalhe (`require_visibilidade(processo)`).
- Bloco `prazo` no detalhe cidadão: já filtrado pela regra existente de
  "dono do processo".
- Teste valida ausência de PII no payload `/dashboard/kpis` (mesmo padrão
  PR 5a — extensão do teste existente em `test_dashboard.py`).

---

## 12. Testes obrigatórios

### 12.1 Backend (`backend/tests/`)

**Helper puro** (`test_prazos_helper.py` — novo):

1. `prazo_snapshot_dias=None` → `sem_prazo`, prazo previsto None.
2. Em andamento, folga maior que limiar → `dentro_do_prazo`,
   `dias_restantes>0`, `dias_atraso=None`.
3. Em andamento, folga ≤ limiar (20% do prazo, mínimo 1d) → `vencendo`.
4. Em andamento, prazo já passou → `atrasado`, `dias_atraso>0`.
5. Concluído antes do prazo previsto → `concluido_no_prazo`,
   `concluido_em` preenchido.
6. Concluído após o prazo previsto → `concluido_atrasado`, `dias_atraso>0`.
7. Limiar: prazo=30 → 6d; prazo=10 → 2d; prazo=3 → 1d; prazo=1 → 1d.
8. `status_cidadao()` mapeia os 6 valores admin nos 5 valores cidadão.

**Abertura** (`test_cidadao_processos.py` — extensão):

9. Abrir processo por serviço com `prazo_estimado_dias=15` →
   `processo.prazo_servico_dias_snapshot == 15`.
10. Abrir processo por serviço com `prazo_estimado_dias=None` →
    snapshot None; helper devolve `sem_prazo`.
11. Editar `servico.prazo_estimado_dias` depois → snapshot do processo
    **não muda**. (regra crítica D-SNAPSHOT)
12. Abrir processo admin sem `id_servico` (caminho
    `abertura_processo.py`) → snapshot None.

**Migration backfill** (`test_migration_0029.py` — novo):

13. Processo com `id_servico` + serviço com `prazo_estimado_dias=10`,
    snapshot inicialmente NULL → após `upgrade()`, snapshot=10.
14. Processo legado (`id_servico=NULL`) → snapshot continua NULL.
15. Processo com `id_servico` cujo serviço tem `prazo_estimado_dias=NULL`
    → snapshot continua NULL.
16. Idempotência: rodar `upgrade()` 2 vezes (após criar coluna manualmente)
    não duplica nem reverte snapshots.

**Endpoint detalhe admin** (`test_processos.py` — extensão):

17. `GET /processos/{id}` de processo recém-aberto por serviço com prazo
    longo → `prazo.status="dentro_do_prazo"`.
18. `GET /processos/{id}` de processo legado → `prazo.status="sem_prazo"`,
    `prazo.prazo_previsto_em=None`.
19. `GET /processos/{id}` de processo arquivado dentro do prazo →
    `prazo.status="concluido_no_prazo"`, `prazo.concluido_em` preenchido.

**Endpoint detalhe cidadão** (`test_cidadao.py` — extensão):

20. `GET /cidadao/processos/{id}` traz `prazo.status` no enum reduzido e
    `prazo.prazo_estimado_em`. **Sem** `dias_restantes`, `dias_atraso`,
    `prazo_servico_dias_snapshot`, `concluido_em` no payload.

**Dashboard** (`test_dashboard.py` — extensão):

21. Bloco `prazos` agrega corretamente em fixture com mix: 2 dentro, 1
    vencendo, 1 atrasado, 1 sem_prazo, 1 concluído no prazo, 1 concluído
    atrasado.
22. Filtro `id_servico=X` propaga p/ `prazos` — zera contadores de outros
    serviços.
23. Filtro `incluir_legado=false` zera `sem_prazo` p/ processos sem
    `id_servico`.
24. Filtro `id_unidade` propaga p/ `prazos`.
25. `por_servico[i].atrasados` é coerente com `prazos.atrasado`.
26. RLS: tenant B não vê contadores de tenant A no bloco `prazos`.
27. Payload `/dashboard/kpis` não contém CPF, nome, corpo, observação,
    mensagem nem motivo (verificação de strings).

### 12.2 Frontend e2e (`tests-e2e/specs/`)

`prazos-admin.spec.ts` (novo):

1. Detalhe admin de processo dentro do prazo mostra Badge `success`
   com texto "Dentro do prazo".
2. Detalhe admin de processo atrasado mostra Badge `danger` com
   "Atrasado em X d." e `prazo_previsto_em` formatado.
3. Detalhe admin de processo legado **não** renderiza Badge de prazo.
4. Dashboard mostra 4 cards do bloco `prazos` (Sem prazo, Dentro,
   Vencendo, Atrasado).
5. Mudar filtro `id_servico` no dashboard atualiza os 4 cards.

`prazos-cidadao.spec.ts` (novo):

6. Detalhe cidadão mostra "Prazo estimado de atendimento: …" + Badge
   reduzido.
7. Detalhe cidadão de processo legado mostra "Sem previsão" (Badge
   `neutral`); a página **não** contém "dias", "vencido", "garantido"
   nem "SLA" no DOM.

---

## 13. Fora de escopo (confirmado)

Não entra no PR 5b. Listado para evitar incremental scope creep:

- Notificações de prazo (e-mail / SMS / WhatsApp / push / in-app).
- Alertas em tempo real em tela.
- Indeferimento ou arquivamento automático por vencimento de prazo.
- Workflow avançado / SLA por nó (já existe via `WorkflowSlaAlerta`, **não**
  é tocado).
- SLA contratual / cláusulas penais / cobrança.
- Calendário de feriados municipais.
- Contagem em dias úteis (PR 5b usa **dias corridos**).
- Suspensão automática de prazo durante complementação aberta.
- Reabertura de prazo após complementação respondida.
- Pausa manual de prazo por servidor.
- Dashboard cross-tenant (visão global da plataforma SaaS).
- IA / previsão preditiva de atraso / recomendação de prazo.

---

## 14. Ordem de implementação (quando autorizado)

| # | Camada | Arquivo principal |
|---|--------|-------------------|
| 1 | Migration | `backend/alembic/versions/0029_processo_prazo_snapshot.py` |
| 2 | ORM | `backend/app/models/processo.py` (+1 linha) |
| 3 | Helper puro | `backend/app/services/prazos.py` (novo) |
| 4 | Testes helper | `backend/tests/test_prazos_helper.py` (novo) |
| 5 | Abertura | `backend/app/services/cidadao_processos.py` (snapshot em 2 pontos) |
| 6 | Testes abertura | `backend/tests/test_cidadao_processos.py` (extensão) |
| 7 | Schema admin | `backend/app/schemas/processo.py` (`PrazoInfo`) |
| 8 | Detalhe admin | `backend/app/services/processos.py` + `routers/processos.py` |
| 9 | Schema cidadão | `backend/app/schemas/cidadao.py` (`PrazoCidadao`) |
| 10 | Detalhe cidadão | `backend/app/services/cidadao_processos.py` (extensão do detalhe) |
| 11 | Schema dashboard | `backend/app/schemas/dashboard.py` (`PrazosKpis`, `atrasados`) |
| 12 | Dashboard service | `backend/app/services/dashboard.py` (`_prazos_kpis`, extensão `_breakdown_servico`) |
| 13 | Exports | `backend/app/services/dashboard_export.py` (seção `[Prazos]`) |
| 14 | Testes dashboard | `backend/tests/test_dashboard.py` (extensão) |
| 15 | Testes migration | `backend/tests/test_migration_0029.py` (novo) |
| 16 | Tipos frontend | `frontend/lib/api.ts` (PrazoInfo, PrazoCidadao) |
| 17 | Detalhe admin UI | `frontend/app/(app)/processos/[id]/page.tsx` |
| 18 | Detalhe cidadão UI | `frontend/app/cidadao/processos/[id]/page.tsx` |
| 19 | Dashboard UI | `frontend/app/(app)/dashboard/page.tsx` |
| 20 | e2e | `tests-e2e/specs/prazos-admin.spec.ts` + `prazos-cidadao.spec.ts` |

Sugestão de commits: 1 commit por bloco (1-2-3-4 / 5-6 / 7-8 / 9-10 /
11-12-13-14-15 / 16-17-18 / 19 / 20). Total ~8 commits, seguindo a
disciplina do PR 5a.

---

## 15. Resumo executivo

PR 5b é **enxuto e cirúrgico**: 1 coluna nova, 1 helper puro, 1 bloco
agregado no dashboard, 2 blocos no detalhe (admin + cidadão), 27 testes
backend, 7 testes e2e. Sem novas tabelas, sem novas libs, sem novas
permissões, sem novos endpoints. Estende o que o PR 5a já entregou
(transação `dashboard`, filtros `id_servico` / `incluir_legado` /
`id_unidade`, ranking `por_servico`, padrão de exports CSV/PDF).

Aguardando autorização explícita para começar pela migration 0029.
