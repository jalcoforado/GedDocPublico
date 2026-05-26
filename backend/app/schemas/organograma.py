"""Schema do organograma — visualização gráfica das unidades."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class OrganogramaNo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_unidade_pai: int | None
    unidade_trabalho: str
    sigla: str | None
    processos_ativos: int
    usuarios: int
    sla_pendentes: int
    tempo_medio_dias: float | None
