from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CadastroCidadaoRequest(BaseModel):
    cpf_cnpj: str = Field(min_length=11, max_length=14)
    nome: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=100)
    senha: str = Field(min_length=4, max_length=100)
    telefone: str | None = Field(default=None, max_length=20)
    telefone_whatsapp: bool = False


class LoginCidadaoRequest(BaseModel):
    cpf_cnpj: str
    senha: str


class CidadaoMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str | None
    cpf_cnpj: str | None
    email: str | None
    telefone: str | None
    telefone_whatsapp: bool
    ativo: bool


class LoginCidadaoResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    cidadao: CidadaoMeResponse


class AbrirProcessoCidadaoRequest(BaseModel):
    id_assunto: int
    corpo: str = Field(min_length=10)
    observacao: str | None = None
    id_especie_documental: int | None = None


class AbrirPorServicoRequest(BaseModel):
    """PR 4b — abertura por serviço. A classificação (assunto/unidade/tipo/
    espécie/sigilo/canal) vem dos defaults do serviço; o cidadão só descreve o
    pedido. Não há campos de classificação aqui — impossível sobrescrever."""

    corpo: str = Field(min_length=10)
    observacao: str | None = None


class EspecieCidadaoOut(BaseModel):
    id: int
    codigo: str
    nome: str


class ProcessoCidadaoListItem(BaseModel):
    id: int
    numero_processo: str
    nup: str | None = None
    data_hora_abertura: datetime
    assunto: str | None
    tipo_processo: str | None
    local_atual: str | None
    ativo: bool
    publico: bool


class AnexoCidadaoOut(BaseModel):
    id: int
    descricao: str | None
    e_doc: str | None
    qtd_paginas: int | None
    publico: bool


class PrazoCidadao(BaseModel):
    """Visão reduzida do prazo no portal do cidadão (PR 5b — D-CIDADAO).

    Sem contagem de dias. Status num enum cuidadoso para evitar promessa
    jurídica. Linguagem na UI: "prazo estimado de atendimento",
    "previsão", "situação do prazo". Vetado: "garantia", "SLA",
    "prazo legal garantido", "vencimento contratual".
    """

    prazo_estimado_em: datetime | None
    status: Literal[
        "sem_previsao",
        "dentro_da_previsao",
        "proximo_do_prazo",
        "fora_da_previsao",
        "concluido",
    ]


class ProcessoCidadaoDetail(ProcessoCidadaoListItem):
    observacao: str | None
    corpo: str | None
    especie_nome: str | None = None
    ccd_codigo: str | None = None
    ccd_nome: str | None = None
    movimentacoes: list["MovimentacaoCidadaoItem"]
    anexos: list[AnexoCidadaoOut] = []
    # PR 5b — bloco de prazo reduzido. Sempre presente.
    prazo: PrazoCidadao


class MovimentacaoCidadaoItem(BaseModel):
    id: int
    data_hora_movimentacao: datetime
    acao: str
    unidade_responsavel: str | None
    despacho_publico: str | None  # só mostra despacho de processos públicos


ProcessoCidadaoDetail.model_rebuild()
