from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

# SI-34 — por qual data o período é contado. Cada relatório aceita um
# subconjunto (o router valida): processos = abertura|arquivamento,
# tramitação = abertura|chegada.
DataBase = Literal["abertura", "arquivamento", "chegada"]
# Filtros próprios da lista de processos (os cartões Sigilosos e Externos).
FiltroSigilo = Literal["ostensivo", "sigiloso"]
FiltroOrigem = Literal["interna", "externa"]
ModoUnidade = Literal["envolvida", "dona", "atual"]
Situacao = Literal["em_andamento", "em_transito", "arquivado"]
# Status do prazo do serviço — os de `prazos.StatusPrazo`.
StatusPrazoRelatorio = Literal[
    "sem_prazo", "dentro_do_prazo", "vencendo", "atrasado",
    "concluido_no_prazo", "concluido_atrasado",
]


class RelatorioFiltro(BaseModel):
    id_unidade: int | None = None
    modo_unidade: ModoUnidade = "envolvida"
    id_assunto: int | None = None
    id_tipo_processo: int | None = None
    id_servico: int | None = None
    # Dias LOCAIS (Brasília), inclusive nas duas pontas. A conversão para o
    # UTC das colunas é de `relatorios_comum.intervalo_utc`.
    desde: date | None = None
    ate: date | None = None
    data_base: DataBase = "abertura"
    # Lista de uma seção da página gerencial: "Andamento" filtra a situação de
    # hoje; "parados" são os não arquivados sem movimentação há N dias.
    situacao: Situacao | None = None
    parado_ha_dias: int | None = None
    # Lista de um número do bloco Prazos (status do prazo do serviço).
    prazo: StatusPrazoRelatorio | None = None
    # Lista de processos: sigiloso = qualquer nível acima de ostensivo (dentro
    # do que a credencial de quem consulta alcança); origem pelo `externo`.
    sigilo: FiltroSigilo | None = None
    origem: FiltroOrigem | None = None
    # Tramitação: só processos com alguma etapa atrasada (prazo do envio).
    com_atraso: bool = False


class RelatorioTotais(BaseModel):
    total: int
    em_andamento: int
    em_transito: int
    arquivados: int
    sigilosos: int
    externos: int


class RelatorioBreakdownItem(BaseModel):
    label: str
    count: int
    pct: float


class RelatorioProcessoRow(BaseModel):
    id: int
    numero_processo: str
    # Hora local (Brasília), sem fuso — ver `relatorios_comum.hora_local`.
    data_hora_abertura: datetime
    data_hora_arquivamento: datetime | None = None
    # Última movimentação registrada (ou a abertura, se nenhuma) — é dela que
    # se contam os dias parado.
    ultima_movimentacao: datetime | None = None
    situacao: Situacao
    manifestante: str | None
    tipo_processo: str | None
    assunto: str | None
    unidade_proprietaria: str | None
    local_atual: str | None
    publico: bool
    nivel_sigilo: str = "ostensivo"
    externo: bool


class RelatorioResposta(BaseModel):
    filtros_aplicados: RelatorioFiltro
    # O recorte em texto, igual na tela, no CSV e no PDF: dois arquivos com
    # números diferentes têm de dizer por que são diferentes.
    descricao_filtros: list[str]
    nome_unidade: str | None
    totais: RelatorioTotais
    por_tipo_processo: list[RelatorioBreakdownItem]
    por_unidade_proprietaria: list[RelatorioBreakdownItem]
    por_local_atual: list[RelatorioBreakdownItem]
    por_assunto: list[RelatorioBreakdownItem]
    por_servico: list[RelatorioBreakdownItem]
    processos: list[RelatorioProcessoRow]
    # A lista tem teto; os totais, não. `cortado` avisa quando a lista mostra
    # menos processos do que `totais.total` — antes o corte era silencioso.
    cortado: bool = False
