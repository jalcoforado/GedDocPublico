"""Schemas do módulo de Protocolo (Fase P1 — Balcão)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CanalEntrada = Literal["balcao", "portal", "email", "api", "interno"]


class EspecieDocumentalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    flag: str
    nome: str
    descricao: str | None
    ativo: bool


class EspecieDocumentalCreate(BaseModel):
    flag: str = Field(..., min_length=2, max_length=40, pattern=r"^[A-Z0-9_]+$")
    nome: str = Field(..., min_length=2, max_length=120)
    descricao: str | None = Field(default=None, max_length=500)


class EspecieDocumentalUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=120)
    descricao: str | None = Field(default=None, max_length=500)
    ativo: bool | None = None


class ProtocoloBalcaoRequest(BaseModel):
    """Body do POST /api/v2/protocolo/balcao — registra documento recebido no balcão."""

    id_manifestante: int
    id_assunto: int
    id_especie_documental: int
    id_unidade_proprietaria: int
    observacao: str | None = Field(default=None, max_length=2000)
    numero_origem: str | None = Field(default=None, max_length=255)
    publico: bool = True
    # Quando o documento chegou (default = agora). Útil quando protocolando
    # algo que foi entregue fora do horário.
    data_recepcao: datetime | None = None
    # Sempre 'balcao' para esse endpoint, mas explicitado pra deixar claro.
    canal_entrada: CanalEntrada = "balcao"
    # Fase P4 — classe documental opcional (recomendada). UI pode sugerir via /sugerir-ccd.
    id_ccd_classe: int | None = None


class ProtocoloBalcaoResponse(BaseModel):
    """Retorno enxuto pra UI focar em número + ID pra navegação/etiqueta."""

    id: int
    numero_processo: str
    nup: str | None = None  # Fase P2 — só preenchido se tenant tem usar_nup_federal=True
    data_hora_abertura: datetime
    data_recepcao: datetime | None
    canal_entrada: CanalEntrada
    id_especie_documental: int | None
    especie_documental: str | None
    manifestante: str
    assunto: str
    unidade_proprietaria: str
