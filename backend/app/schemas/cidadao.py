from datetime import datetime

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


class ProcessoCidadaoListItem(BaseModel):
    id: int
    numero_processo: str
    data_hora_abertura: datetime
    assunto: str | None
    tipo_processo: str | None
    local_atual: str | None
    ativo: bool
    publico: bool


class ProcessoCidadaoDetail(ProcessoCidadaoListItem):
    observacao: str | None
    corpo: str | None
    movimentacoes: list["MovimentacaoCidadaoItem"]


class MovimentacaoCidadaoItem(BaseModel):
    id: int
    data_hora_movimentacao: datetime
    acao: str
    unidade_responsavel: str | None
    despacho_publico: str | None  # só mostra despacho de processos públicos


ProcessoCidadaoDetail.model_rebuild()
