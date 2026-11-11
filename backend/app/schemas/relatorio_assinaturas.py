from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from .relatorio import ModoUnidade

StatusSolicitacao = Literal["pendente", "concluida", "cancelada"]


class AssinaturasFiltro(BaseModel):
    # SI-34 — o mesmo recorte dos outros relatórios, sobre o PROCESSO da
    # solicitação (unidade, assunto, tipo), mais os filtros próprios.
    id_unidade: int | None = None
    modo_unidade: ModoUnidade = "envolvida"
    id_assunto: int | None = None
    id_tipo_processo: int | None = None
    # Dias LOCAIS (Brasília), inclusive; pela data do pedido ou da conclusão.
    desde: date | None = None
    ate: date | None = None
    data_base: Literal["pedido", "conclusao"] = "pedido"
    id_solicitante: int | None = None
    id_assinante: int | None = None
    status: StatusSolicitacao | None = None


class AssinaturasTotais(BaseModel):
    total: int
    pendentes: int
    concluidas: int
    canceladas: int
    minutos_medio_conclusao: float  # apenas concluídas


class AssinanteAgregado(BaseModel):
    id_assinante: int
    nome: str | None
    pendentes: int
    concluidas: int
    minutos_medio: float  # tempo entre solicitação e última assinatura do assinante


class SolicitanteAgregado(BaseModel):
    id_solicitante: int
    nome: str | None
    total: int
    pendentes: int
    concluidas: int
    canceladas: int


class SolicitacaoRow(BaseModel):
    id: int
    id_processo: int
    numero_processo: str | None
    id_solicitante: int
    nome_solicitante: str | None
    status: StatusSolicitacao
    # Hora local (Brasília), sem fuso.
    dt_inicio: datetime
    dt_fim: datetime | None
    minutos_decorridos: int | None  # dt_fim - dt_inicio (ou now - dt_inicio se pendente)
    qtd_assinantes: int
    qtd_assinantes_concluidos: int
    qtd_anexos: int
    qtd_anexos_assinados: int
    assinantes_resumo: list[str]  # nomes


class RelatorioAssinaturasResposta(BaseModel):
    filtros_aplicados: AssinaturasFiltro
    descricao_filtros: list[str]
    # Totais e agregados contam o recorte INTEIRO; só a lista tem teto.
    totais: AssinaturasTotais
    por_assinante: list[AssinanteAgregado]
    por_solicitante: list[SolicitanteAgregado]
    solicitacoes: list[SolicitacaoRow]
    cortado: bool = False
