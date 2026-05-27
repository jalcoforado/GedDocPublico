"""Schemas — Fase P6 (Apensamento + Desentranhamento + Volumes)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
#  Apensamento
# ============================================================================

class ApensarRequest(BaseModel):
    id_processo_principal: int
    motivo: str = Field(..., min_length=3, max_length=1000)


class DesapensarRequest(BaseModel):
    motivo: str = Field(..., min_length=3, max_length=1000)


class ApensamentoOut(BaseModel):
    """Detalhe do registro de apensamento — vivo ou histórico."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    id_processo_apensado: int
    id_processo_principal: int
    id_usuario: int
    motivo: str
    criado_em: datetime
    desapensado_em: datetime | None
    id_usuario_desapensamento: int | None
    motivo_desapensamento: str | None
    # Enriquecidos via JOIN no router
    numero_processo_apensado: str | None = None
    numero_processo_principal: str | None = None
    usuario_nome: str | None = None
    usuario_desapensamento_nome: str | None = None
    ativo: bool = True  # = desapensado_em IS NULL


class ProcessoApensadoItem(BaseModel):
    """Linha resumida pra mostrar filhos atuais de um processo pai."""

    id_apensamento: int
    id_processo: int
    numero_processo: str
    nup: str | None = None
    manifestante: str | None
    apensado_em: datetime
    motivo: str


# ============================================================================
#  Desentranhamento
# ============================================================================

class DesentranhamentoRequest(BaseModel):
    motivo: str = Field(..., min_length=3, max_length=1000)
    autoridade: str = Field(
        ..., min_length=2, max_length=300,
        description="Cargo/órgão que autoriza o desentranhamento "
                    "(ex: 'Diretor de Protocolo, Portaria 123/2026')",
    )


class DesentranhamentoOut(BaseModel):
    """Estado do desentranhamento de um anexo de processo."""

    model_config = ConfigDict(from_attributes=True)
    id_anexo_processo: int
    id_anexo: int
    descricao_anexo: str | None
    desentranhado_em: datetime
    motivo: str
    autoridade: str
    usuario_nome: str | None


# ============================================================================
#  Volumes
# ============================================================================

class VolumeCreate(BaseModel):
    numero: int = Field(..., ge=1, le=999)
    pagina_inicial: int | None = Field(default=None, ge=1)
    pagina_final: int | None = Field(default=None, ge=1)
    observacao: str | None = Field(default=None, max_length=500)


class VolumeUpdate(BaseModel):
    pagina_inicial: int | None = Field(default=None, ge=1)
    pagina_final: int | None = Field(default=None, ge=1)
    observacao: str | None = Field(default=None, max_length=500)


class VolumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    id_processo: int
    numero: int
    pagina_inicial: int | None
    pagina_final: int | None
    observacao: str | None
    id_usuario: int
    criado_em: datetime
    usuario_nome: str | None = None
