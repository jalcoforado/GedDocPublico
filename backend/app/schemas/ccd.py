"""Schemas CCD + TTD + Temporalidade (Fase P4)."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DestinoFinal = Literal["ELIMINACAO", "GUARDA_PERMANENTE"]


class CcdClasseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nome: str
    descricao: str | None
    id_classe_pai: int | None
    palavras_chave: str | None
    ativo: bool


class CcdClasseTreeNode(BaseModel):
    """Versão com filhos aninhados pra UI de árvore."""

    id: int
    codigo: str
    nome: str
    descricao: str | None
    palavras_chave: str | None
    ativo: bool
    filhos: list["CcdClasseTreeNode"] = Field(default_factory=list)


class CcdClasseCreate(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=20)
    nome: str = Field(..., min_length=2, max_length=200)
    descricao: str | None = Field(default=None, max_length=1000)
    id_classe_pai: int | None = None
    palavras_chave: str | None = Field(default=None, max_length=500)


class CcdClasseUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=20)
    nome: str | None = Field(default=None, min_length=2, max_length=200)
    descricao: str | None = Field(default=None, max_length=1000)
    id_classe_pai: int | None = None
    palavras_chave: str | None = Field(default=None, max_length=500)
    ativo: bool | None = None


class TtdRegraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    id_ccd_classe: int
    id_especie_documental: int | None
    anos_corrente: int
    anos_intermediario: int
    destino_final: DestinoFinal
    observacao: str | None
    ativo: bool


class TtdRegraDetail(TtdRegraOut):
    """Enriquecida pra listas — inclui rótulos de classe + espécie."""

    classe_codigo: str
    classe_nome: str
    especie_nome: str | None


class TtdRegraCreate(BaseModel):
    id_ccd_classe: int
    id_especie_documental: int | None = None
    anos_corrente: int = Field(default=0, ge=0, le=999)
    anos_intermediario: int = Field(default=0, ge=0, le=999)
    destino_final: DestinoFinal
    observacao: str | None = Field(default=None, max_length=1000)


class TtdRegraUpdate(BaseModel):
    id_especie_documental: int | None = None
    anos_corrente: int | None = Field(default=None, ge=0, le=999)
    anos_intermediario: int | None = Field(default=None, ge=0, le=999)
    destino_final: DestinoFinal | None = None
    observacao: str | None = Field(default=None, max_length=1000)
    ativo: bool | None = None


class TemporalidadeOut(BaseModel):
    """Resultado do cálculo de temporalidade pra um processo específico."""

    id_processo: int
    numero_processo: str
    id_ccd_classe: int | None
    classe_codigo: str | None
    classe_nome: str | None
    id_especie_documental: int | None
    especie_nome: str | None
    regra_aplicada: TtdRegraOut | None
    data_referencia: datetime | None  # data_recepcao ou data_hora_abertura
    fim_fase_corrente: date | None
    fim_fase_intermediaria: date | None
    destino_final: DestinoFinal | None
    motivo_sem_regra: str | None  # quando regra_aplicada é None


class SugestaoCcdOut(BaseModel):
    """Sugestão de classe CCD baseada em palavras-chave do assunto."""

    id_ccd_classe: int
    codigo: str
    nome: str
    score: float  # 0..1 — confiança relativa
    matched_keywords: list[str]


CcdClasseTreeNode.model_rebuild()
