from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ProcessoCreate(BaseModel):
    id_assunto: int
    id_manifestante: int
    id_unidade_proprietaria: int
    observacao: str | None = Field(default=None, max_length=10000)
    corpo: str | None = Field(default=None, max_length=50000)
    numero_origem: str | None = None
    publico: bool = True
    externo: bool = False
    virtual: bool = True


class EncaminharRequest(BaseModel):
    id_unidade_destino: int
    id_prioridade: int
    quantidade_folhas: int = Field(default=0, ge=0)
    data_prazo: date | None = None
    despacho: str | None = Field(default=None, max_length=10000)


class CancelarEncaminhamentoRequest(BaseModel):
    despacho: str | None = Field(default=None, max_length=2000)


class PrioridadeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    prioridade: str
    fator: int
    cor: str


class ProcessoListItem(BaseModel):
    """Visão para listagem — campos enriquecidos com nomes via JOIN."""
    id: int
    numero_processo: str
    numero_origem: str | None
    data_hora_abertura: datetime
    ativo: bool
    publico: bool
    externo: bool

    assunto: str | None
    tipo_processo: str | None
    manifestante: str | None
    manifestante_cpf_cnpj: str | None
    unidade_proprietaria: str | None
    local_atual: str | None


class AnexoNoProcesso(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    descricao: str | None
    publico: bool
    qtd_paginas: int | None
    e_doc: str | None
    tipo_anexo: str | None = None
    ordem: int | None = None


class EncaminhamentoOut(BaseModel):
    id: int
    unidade_origem: str | None
    unidade_destino: str
    prioridade: str | None
    quantidade_folhas: int
    data_prazo: date | None
    recebido: bool
    data_hora_recebimento: datetime | None
    cancelado: bool


class DespachoOut(BaseModel):
    id: int
    despacho: str
    usuario: str | None


class MovimentacaoItem(BaseModel):
    """Item da timeline — agrega acao + despacho + encaminhamento opcionais."""
    id: int
    data_hora_movimentacao: datetime
    acao_flag: str
    acao: str
    status_acao: str
    status_movimentacao: str
    unidade_responsavel: str | None
    usuario: str | None
    despacho: DespachoOut | None = None
    encaminhamento: EncaminhamentoOut | None = None


class ProcessoDetail(ProcessoListItem):
    observacao: str | None
    corpo: str | None
    virtual: bool
    migrado: bool
    id_processo_pai: int | None

    movimentacoes: list[MovimentacaoItem]
    anexos: list[AnexoNoProcesso]
