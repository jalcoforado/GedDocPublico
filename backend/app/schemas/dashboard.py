"""Schemas Pydantic — Dashboard.

Fase 18a (KPIs) + 18b (filtros/comparativo) + 18c (export) + PR 5a
(dimensão serviço/documental/complementação). Campos antigos preservados
byte-a-byte (D-ESTRUTURA do PR 5a).
"""
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


# ===== PR 5a — blocos novos =====


class DocumentalKpis(BaseModel):
    """Agregados de checklist por processo no período (PR 4c × PR 4a)."""

    com_id_servico_periodo: int
    sem_id_servico_periodo: int
    # Processo com id_servico cujo serviço **tem** documentos exigidos e
    # **nenhum** dos obrigatórios foi enviado.
    checklist_pendente: int
    # Algum obrigatório enviado, nem todos.
    checklist_parcial: int
    # Sem obrigatórios (trivial) ou todos os obrigatórios enviados.
    checklist_completo: int


class ComplementacaoKpis(BaseModel):
    """Agregados da entidade `complementacao_documental` (PR 4d)."""

    abertas_agora: int                       # snapshot independente do período
    solicitadas_periodo: int                 # criado_em em [desde, ate)
    respondidas_periodo: int                 # respondido_em em [desde, ate)
    canceladas_periodo: int                  # cancelado_em em [desde, ate)
    processos_com_aberta_agora: int          # DISTINCT id_processo com status='aberta'
    tempo_medio_resposta_dias: float | None  # AVG sobre respondidas no período


class ServicoBreakdownItem(BaseModel):
    """Linha do ranking por serviço. `id_servico=None` → linha "(sem serviço)"
    (legado), só aparece quando `incluir_legado=True` e sem filtro de
    `id_servico`."""

    id_servico: int | None
    nome: str
    count: int
    complementacoes_abertas: int
    complementacoes_respondidas_periodo: int
    checklist_pendente: int
    checklist_parcial: int
    checklist_completo: int


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
    # PR 5a — blocos novos. Campos antigos preservados (D-ESTRUTURA).
    documental: DocumentalKpis
    complementacao: ComplementacaoKpis
    por_servico: list[ServicoBreakdownItem]
