from datetime import datetime

from pydantic import BaseModel

from .relatorio import RelatorioFiltro


class TramitacaoEtapa(BaseModel):
    """Uma 'estação' do processo numa unidade: chegou, ficou X tempo, saiu."""
    id_unidade: int | None
    unidade: str | None
    chegou_em: datetime | None  # data_hora_recebimento ou abertura
    saiu_em: datetime | None  # data_hora_movimentacao do próximo encaminhamento (None se ainda lá)
    minutos_no_local: int | None  # None se ainda lá
    prazo_estipulado: datetime | None  # da data_prazo do encaminhamento que trouxe o processo
    atrasou: bool


class TramitacaoProcesso(BaseModel):
    id: int
    numero_processo: str
    data_hora_abertura: datetime
    ativo: bool
    manifestante: str | None
    assunto: str | None
    qtd_encaminhamentos: int
    qtd_unidades_visitadas: int
    minutos_total: int
    minutos_em_andamento: int  # tempo desde abertura ou último recebimento
    teve_atraso: bool
    qtd_atrasos: int
    local_atual: str | None
    etapas: list[TramitacaoEtapa]


class TramitacaoPorUnidade(BaseModel):
    id_unidade: int | None
    unidade: str | None
    qtd_passagens: int  # quantas vezes processos passaram por aqui
    qtd_atrasos: int
    minutos_total: int
    minutos_medio: float


class RelatorioTramitacaoResposta(BaseModel):
    filtros_aplicados: RelatorioFiltro
    nome_unidade: str | None
    qtd_processos: int
    qtd_processos_com_atraso: int
    minutos_medio_por_processo: float
    por_unidade: list[TramitacaoPorUnidade]
    processos: list[TramitacaoProcesso]
