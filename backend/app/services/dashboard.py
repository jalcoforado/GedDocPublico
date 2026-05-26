"""Agregações para o dashboard executivo — Fases 18a + 18b.

Objetivo: dar a um gestor uma visão rápida do volume e saúde dos processos
do tenant. Não substitui o relatório operacional (Fase 6) — este é
sumário visual.

Filtros:
- `periodo` (dias atrás a partir de hoje): 7 | 30 | 90 | 365
- `id_unidade` (opcional): restringe a processos proprietários OU em local
  atual nessa unidade

Métricas (período atual):
- volume: abertos no período, ativos hoje, externos no período
- conclusão: arquivados no período + tempo médio (data abertura → última
  arquivamento)
- SLA: alertas pendentes hoje, alertas resolvidos no período
- breakdown: top 5 por tipo_processo, top 10 por assunto, top 10 por
  unidade proprietária
- série temporal: abertos por dia no período (agrupado por dia)

Métricas (período anterior — para comparativo na 18b):
- mesmos contadores numéricos (sem breakdown nem série temporal), com
  janela `[now - 2*periodo, now - periodo)`. Frontend calcula delta % e
  desenha seta de tendência.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Assunto,
    Movimentacao,
    Processo,
    TipoProcesso,
    UnidadeTrabalho,
    WorkflowSlaAlerta,
)


async def _counts_intervalo(
    db: AsyncSession,
    *,
    tenant_id: int,
    desde: datetime,
    ate: datetime,
    id_unidade: int | None,
) -> dict[str, Any]:
    """Computa contadores numéricos pro intervalo `[desde, ate)`.

    Usado pelo período atual E pelo anterior. NÃO inclui:
    - `ativos_hoje` (snapshot, não é janelado)
    - `sla.pendentes` (snapshot)
    - breakdowns + série temporal (só atual usa)
    """
    # Filtro por unidade reusado em vários WHERE
    unid_filter = []
    if id_unidade is not None:
        unid_filter = [
            (Processo.id_unidade_proprietaria == id_unidade)
            | (Processo.id_local_atual == id_unidade)
        ]

    # Abertos
    abertos = (
        await db.execute(
            select(func.count(Processo.id)).where(
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
                Processo.data_hora_abertura >= desde,
                Processo.data_hora_abertura < ate,
                *unid_filter,
            )
        )
    ).scalar_one()

    # Externos
    externos = (
        await db.execute(
            select(func.count(Processo.id)).where(
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
                Processo.data_hora_abertura >= desde,
                Processo.data_hora_abertura < ate,
                Processo.externo.is_(True),
                *unid_filter,
            )
        )
    ).scalar_one()

    # Sigilosos
    sigilosos = (
        await db.execute(
            select(func.count(Processo.id)).where(
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
                Processo.data_hora_abertura >= desde,
                Processo.data_hora_abertura < ate,
                Processo.publico.is_(False),
                *unid_filter,
            )
        )
    ).scalar_one()

    # Arquivados (via Movimentacao com id_arquivamento NOT NULL)
    arq_stmt = (
        select(func.count(Movimentacao.id))
        .select_from(Movimentacao)
        .join(Processo, Processo.id == Movimentacao.id_processo)
        .where(
            Movimentacao.tenant_id == tenant_id,
            Movimentacao.id_arquivamento.is_not(None),
            Movimentacao.data_hora_movimentacao >= desde,
            Movimentacao.data_hora_movimentacao < ate,
            Processo.excluido.is_(False),
            *unid_filter,
        )
    )
    arquivados = (await db.execute(arq_stmt)).scalar_one()

    # Tempo médio de conclusão
    tm_stmt = (
        select(
            func.avg(
                func.extract(
                    "epoch",
                    Movimentacao.data_hora_movimentacao - Processo.data_hora_abertura,
                )
                / 86400.0
            )
        )
        .select_from(Movimentacao)
        .join(Processo, Processo.id == Movimentacao.id_processo)
        .where(
            Movimentacao.tenant_id == tenant_id,
            Movimentacao.id_arquivamento.is_not(None),
            Movimentacao.data_hora_movimentacao >= desde,
            Movimentacao.data_hora_movimentacao < ate,
            Processo.excluido.is_(False),
            *unid_filter,
        )
    )
    tempo_medio = (await db.execute(tm_stmt)).scalar_one()
    tempo_medio = float(tempo_medio) if tempo_medio is not None else None

    # SLA resolvidos no intervalo
    sla_resolv = (
        await db.execute(
            select(func.count(WorkflowSlaAlerta.id)).where(
                WorkflowSlaAlerta.tenant_id == tenant_id,
                WorkflowSlaAlerta.resolvido_em.is_not(None),
                WorkflowSlaAlerta.resolvido_em >= desde,
                WorkflowSlaAlerta.resolvido_em < ate,
            )
        )
    ).scalar_one()

    # Taxa de conclusão
    taxa = None
    if abertos and abertos > 0:
        taxa = round((arquivados / abertos) * 100, 1)

    return {
        "abertos": int(abertos),
        "externos": int(externos),
        "sigilosos": int(sigilosos),
        "arquivados": int(arquivados),
        "tempo_medio_dias": tempo_medio,
        "taxa_conclusao_pct": taxa,
        "sla_resolvidos": int(sla_resolv),
    }


async def kpis(
    db: AsyncSession,
    *,
    tenant_id: int,
    periodo_dias: int = 30,
    id_unidade: int | None = None,
) -> dict[str, Any]:
    """Devolve um payload pronto pra UI render. Forma JSON estável documentada
    no schema Pydantic correspondente."""
    if periodo_dias not in (7, 30, 90, 365):
        periodo_dias = 30
    now = datetime.utcnow()
    desde_atual = now - timedelta(days=periodo_dias)
    desde_anterior = now - timedelta(days=2 * periodo_dias)

    # Filtro de tenant + unidade comum a quase todos os queries
    def _base_processo():
        stmt = select(Processo).where(
            Processo.tenant_id == tenant_id,
            Processo.excluido.is_(False),
        )
        if id_unidade is not None:
            stmt = stmt.where(
                (Processo.id_unidade_proprietaria == id_unidade)
                | (Processo.id_local_atual == id_unidade)
            )
        return stmt

    # Contadores janelados — atual e anterior
    atual = await _counts_intervalo(
        db,
        tenant_id=tenant_id,
        desde=desde_atual,
        ate=now,
        id_unidade=id_unidade,
    )
    anterior = await _counts_intervalo(
        db,
        tenant_id=tenant_id,
        desde=desde_anterior,
        ate=desde_atual,
        id_unidade=id_unidade,
    )

    # Ativos hoje (snapshot — não janelado)
    ativos_hoje_stmt = _base_processo().where(Processo.ativo.is_(True))
    sq_ah = ativos_hoje_stmt.subquery()
    ativos_hoje = (await db.execute(select(func.count(sq_ah.c.id)))).scalar_one()

    # SLA pendentes agora (snapshot)
    sla_pendentes = (
        await db.execute(
            select(func.count(WorkflowSlaAlerta.id)).where(
                WorkflowSlaAlerta.tenant_id == tenant_id,
                WorkflowSlaAlerta.resolvido_em.is_(None),
            )
        )
    ).scalar_one()

    # ===== Breakdown por tipo_processo (top 5) =====
    tipo_q = (
        select(
            TipoProcesso.tipo_processo.label("label"),
            func.count(Processo.id).label("count"),
        )
        .select_from(Processo)
        .join(Assunto, Assunto.id == Processo.id_assunto)
        .join(TipoProcesso, TipoProcesso.id == Assunto.id_tipo_processo)
        .where(
            Processo.tenant_id == tenant_id,
            Processo.excluido.is_(False),
            Processo.data_hora_abertura >= desde_atual,
        )
        .group_by(TipoProcesso.tipo_processo)
        .order_by(func.count(Processo.id).desc())
        .limit(5)
    )
    if id_unidade is not None:
        tipo_q = tipo_q.where(
            (Processo.id_unidade_proprietaria == id_unidade)
            | (Processo.id_local_atual == id_unidade)
        )
    por_tipo = [
        {"label": lbl, "count": int(cnt)}
        for lbl, cnt in (await db.execute(tipo_q)).all()
    ]

    # ===== Breakdown por assunto (top 10) =====
    assunto_q = (
        select(
            Assunto.assunto.label("label"),
            func.count(Processo.id).label("count"),
        )
        .select_from(Processo)
        .join(Assunto, Assunto.id == Processo.id_assunto)
        .where(
            Processo.tenant_id == tenant_id,
            Processo.excluido.is_(False),
            Processo.data_hora_abertura >= desde_atual,
        )
        .group_by(Assunto.assunto)
        .order_by(func.count(Processo.id).desc())
        .limit(10)
    )
    if id_unidade is not None:
        assunto_q = assunto_q.where(
            (Processo.id_unidade_proprietaria == id_unidade)
            | (Processo.id_local_atual == id_unidade)
        )
    por_assunto = [
        {"label": lbl, "count": int(cnt)}
        for lbl, cnt in (await db.execute(assunto_q)).all()
    ]

    # ===== Breakdown por unidade proprietária (top 10) =====
    unid_q = (
        select(
            UnidadeTrabalho.unidade_trabalho.label("label"),
            func.count(Processo.id).label("count"),
        )
        .select_from(Processo)
        .join(UnidadeTrabalho, UnidadeTrabalho.id == Processo.id_unidade_proprietaria)
        .where(
            Processo.tenant_id == tenant_id,
            Processo.excluido.is_(False),
            Processo.data_hora_abertura >= desde_atual,
        )
        .group_by(UnidadeTrabalho.unidade_trabalho)
        .order_by(func.count(Processo.id).desc())
        .limit(10)
    )
    por_unidade = [
        {"label": lbl, "count": int(cnt)}
        for lbl, cnt in (await db.execute(unid_q)).all()
    ]

    # ===== Série temporal (abertos por dia) =====
    serie_q = (
        select(
            func.date_trunc("day", Processo.data_hora_abertura).label("dia"),
            func.count(Processo.id).label("count"),
        )
        .where(
            Processo.tenant_id == tenant_id,
            Processo.excluido.is_(False),
            Processo.data_hora_abertura >= desde_atual,
        )
        .group_by(literal_column("1"))
        .order_by(literal_column("1"))
    )
    if id_unidade is not None:
        serie_q = serie_q.where(
            (Processo.id_unidade_proprietaria == id_unidade)
            | (Processo.id_local_atual == id_unidade)
        )
    serie_rows = (await db.execute(serie_q)).all()
    serie_temporal = [
        {"dia": dia.isoformat(), "count": int(cnt)} for dia, cnt in serie_rows
    ]

    return {
        "periodo_dias": periodo_dias,
        "id_unidade": id_unidade,
        "volume": {
            "abertos_periodo": atual["abertos"],
            "ativos_hoje": int(ativos_hoje),
            "externos_periodo": atual["externos"],
            "sigilosos_periodo": atual["sigilosos"],
        },
        "conclusao": {
            "arquivados_periodo": atual["arquivados"],
            "taxa_conclusao_pct": atual["taxa_conclusao_pct"],
            "tempo_medio_dias": atual["tempo_medio_dias"],
        },
        "sla": {
            "pendentes": int(sla_pendentes),
            "resolvidos_periodo": atual["sla_resolvidos"],
        },
        # Fase 18b — comparativo com período anterior do mesmo tamanho
        "comparativo": {
            "abertos_anterior": anterior["abertos"],
            "externos_anterior": anterior["externos"],
            "sigilosos_anterior": anterior["sigilosos"],
            "arquivados_anterior": anterior["arquivados"],
            "tempo_medio_dias_anterior": anterior["tempo_medio_dias"],
            "taxa_conclusao_pct_anterior": anterior["taxa_conclusao_pct"],
            "sla_resolvidos_anterior": anterior["sla_resolvidos"],
        },
        "por_tipo": por_tipo,
        "por_assunto": por_assunto,
        "por_unidade": por_unidade,
        "serie_temporal": serie_temporal,
    }
