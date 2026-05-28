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
    # Assinatura v2 (aditivo)
    status: str = "pendente"
    nivel: str = "legado"
    tem_hash: bool = False


class AssinanteStatus(BaseModel):
    id_usuario_assinatura: int
    id_assinante: int
    nome_assinante: str | None
    realizada: bool
    ordem: int
    # Assinatura v2 (aditivo)
    status: str = "pendente"
    motivo_recusa: str | None = None
    anexos: list[AssinaturaAnexoStatus]


class RecusarRequest(BaseModel):
    motivo: str = Field(min_length=3, max_length=1000)


class ValidacaoOut(BaseModel):
    """Resultado da validação on-demand de uma assinatura de anexo."""
    id_assinatura_anexo: int
    legado: bool
    integro: bool | None  # None quando legado/sem hash
    nivel: str
    status: str
    documento_hash: str | None
    hash_atual: str | None
    dt_assinatura: datetime | None
    detalhe: str


class EvidenciasOut(BaseModel):
    id_assinatura_anexo: int
    id_anexo: int
    id_processo: int | None
    numero_processo: str | None = None
    anexo_descricao: str | None = None
    nome_assinante: str | None
    nivel: str
    status: str
    metodo_autenticacao: str | None
    documento_hash: str | None
    hash_algoritmo: str | None
    documento_versao: int | None
    ip_assinatura: str | None
    user_agent_assinatura: str | None
    dt_assinatura: datetime | None
    id_audit_log: int | None
    evidencias: dict | None


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
