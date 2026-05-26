"""Schemas Pydantic — Dashboard (Fase 18a)."""
from __future__ import annotations

from pydantic import BaseModel


class VolumeKpis(BaseModel):
    abertos_periodo: int
    ativos_hoje: int
    externos_periodo: int
    sigilosos_periodo: int


class ConclusaoKpis(BaseModel):
    arquivados_periodo: int
    taxa_conclusao_pct: float | None
    tempo_medio_dias: float | None


class SlaKpis(BaseModel):
    pendentes: int
    resolvidos_periodo: int


class ComparativoKpis(BaseModel):
    """Contadores do período anterior (mesma duração, deslocado pra trás).
    Frontend calcula delta % vs período atual e desenha seta de tendência."""

    abertos_anterior: int
    externos_anterior: int
    sigilosos_anterior: int
    arquivados_anterior: int
    tempo_medio_dias_anterior: float | None
    taxa_conclusao_pct_anterior: float | None
    sla_resolvidos_anterior: int


class BreakdownItem(BaseModel):
    label: str
    count: int


class SerieTemporalItem(BaseModel):
    dia: str  # ISO date "YYYY-MM-DDTHH:MM:SS"
    count: int


class DashboardKpis(BaseModel):
    periodo_dias: int
    id_unidade: int | None
    volume: VolumeKpis
    conclusao: ConclusaoKpis
    sla: SlaKpis
    comparativo: ComparativoKpis
    por_tipo: list[BreakdownItem]
    por_assunto: list[BreakdownItem]
    por_unidade: list[BreakdownItem]
    serie_temporal: list[SerieTemporalItem]
