from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProcessoCreate(BaseModel):
    id_assunto: int
    id_manifestante: int
    id_unidade_proprietaria: int
    observacao: str | None = Field(default=None, max_length=10000)
    corpo: str | None = Field(default=None, max_length=50000)
    numero_origem: str | None = None
    # `publico` é entrada legada; `nivel_sigilo` (ostensivo|interno) tem
    # precedência quando != ostensivo. Sigilo legal (reservado+) só via
    # endpoint de classificação, que captura o TCI.
    publico: bool = True
    nivel_sigilo: str = "ostensivo"
    externo: bool = False
    virtual: bool = True


class ClassificarSigiloRequest(BaseModel):
    """Classifica/reclassifica o sigilo de um processo (LAI).

    Graus de sigilo legal (reservado/secreto/ultrassecreto) exigem
    `fundamento_legal` + `autoridade`; `prazo_anos` default = máximo legal.
    """

    nivel: str = Field(..., description="ostensivo|interno|reservado|secreto|ultrassecreto")
    fundamento_legal: str | None = Field(default=None, max_length=2000)
    autoridade: str | None = Field(default=None, max_length=300)
    prazo_anos: int | None = Field(default=None, ge=1, le=25)


class EncaminharRequest(BaseModel):
    id_unidade_destino: int
    id_prioridade: int
    quantidade_folhas: int = Field(default=0, ge=0)
    data_prazo: date | None = None
    despacho: str | None = Field(default=None, max_length=10000)
    # Strict workflow override: super-usuário pode quebrar o trilho do
    # workflow informando motivo. Será auditado.
    override_motivo: str | None = Field(default=None, max_length=500)


class CancelarEncaminhamentoRequest(BaseModel):
    despacho: str | None = Field(default=None, max_length=2000)
    override_motivo: str | None = Field(default=None, max_length=500)


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
    nup: str | None = None  # Fase P2 — NUP federal (preenchido só se tenant tem flag)
    numero_origem: str | None
    data_hora_abertura: datetime
    ativo: bool
    publico: bool
    nivel_sigilo: str = "ostensivo"
    externo: bool

    assunto: str | None
    tipo_processo: str | None
    manifestante: str | None
    manifestante_cpf_cnpj: str | None
    unidade_proprietaria: str | None
    local_atual: str | None


class AnexoNoProcesso(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int  # id do Anexo (file row)
    id_anexo_processo: int | None = None  # id do join AnexoProcesso (pra desentranhar)
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


class PrazoInfo(BaseModel):
    """Bloco de prazo no detalhe do processo (admin). PR 5b.

    `status` reflete o cálculo end-to-end do processo a partir de
    `prazo_servico_dias_snapshot` (congelado na abertura). Cidadão recebe
    versão reduzida em `PrazoCidadao` (schemas/cidadao.py).
    """

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
    dias_restantes: int | None  # >0 quando há folga; None se sem_prazo/atrasado
    dias_atraso: int | None  # >0 quando em atraso; None se não atrasado
    concluido_em: datetime | None
    origem: Literal["servico"] | None  # None quando status='sem_prazo'


class ProcessoDetail(ProcessoListItem):
    observacao: str | None
    corpo: str | None
    virtual: bool
    migrado: bool
    id_processo_pai: int | None

    # Sigilo gradual — TCI (preenchido só para graus de sigilo legal).
    sigilo_fundamento_legal: str | None = None
    sigilo_autoridade: str | None = None
    sigilo_prazo_anos: int | None = None
    sigilo_data_classificacao: datetime | None = None
    sigilo_data_desclassificacao: date | None = None

    movimentacoes: list[MovimentacaoItem]
    anexos: list[AnexoNoProcesso]

    # PR 5b — bloco de prazo end-to-end (sempre presente; status='sem_prazo'
    # em processos legados ou sem prazo definido no serviço).
    prazo: PrazoInfo
