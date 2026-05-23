from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TipoAssinaturaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo_assinatura: str
    flag: str | None = None
    externa: bool


class SolicitarAssinaturaRequest(BaseModel):
    id_assinantes: list[int] = Field(min_length=1)
    id_anexos: list[int] = Field(min_length=1)
    id_tipo_assinatura: int | None = None


class AssinarRequest(BaseModel):
    senha: str = Field(min_length=1)


class AssinaturaAnexoStatus(BaseModel):
    id: int
    id_anexo: int
    anexo_descricao: str | None
    assinado: bool
    dt_assinatura: datetime | None


class AssinanteStatus(BaseModel):
    id_usuario_assinatura: int
    id_assinante: int
    nome_assinante: str | None
    realizada: bool
    ordem: int
    anexos: list[AssinaturaAnexoStatus]


class SolicitacaoOut(BaseModel):
    id: int
    id_processo: int
    numero_processo: str | None = None
    id_solicitante: int
    nome_solicitante: str | None
    realizada: bool
    cancelada: bool
    dt_inicio: datetime
    dt_fim: datetime | None
    assinantes: list[AssinanteStatus]


class PendenciaAssinatura(BaseModel):
    """Item da lista 'para assinar': cada par assinatura_anexo pendente do usuário corrente."""
    id_assinatura_anexo: int
    id_anexo: int
    anexo_descricao: str | None
    id_solicitacao: int
    id_processo: int
    numero_processo: str
    nome_solicitante: str | None
    dt_inicio: datetime
