from datetime import datetime

from pydantic import BaseModel


class RelatorioFiltro(BaseModel):
    id_unidade: int | None = None
    id_assunto: int | None = None
    id_tipo_processo: int | None = None
    desde: datetime | None = None
    ate: datetime | None = None
    apenas_ativos: bool = False


class RelatorioTotais(BaseModel):
    total: int
    ativos: int
    inativos: int
    sigilosos: int
    externos: int


class RelatorioBreakdownItem(BaseModel):
    label: str
    count: int
    pct: float


class RelatorioProcessoRow(BaseModel):
    id: int
    numero_processo: str
    data_hora_abertura: datetime
    manifestante: str | None
    tipo_processo: str | None
    assunto: str | None
    unidade_proprietaria: str | None
    local_atual: str | None
    ativo: bool
    publico: bool
    externo: bool


class RelatorioResposta(BaseModel):
    filtros_aplicados: RelatorioFiltro
    nome_unidade: str | None
    totais: RelatorioTotais
    por_tipo_processo: list[RelatorioBreakdownItem]
    por_unidade_proprietaria: list[RelatorioBreakdownItem]
    processos: list[RelatorioProcessoRow]
