"""Schemas da avaliação de documento (SI-73, RF-04 V2).

Campos server-side (solicitante, situação, decisor, datas) não entram nos
schemas de entrada (CLAUDE.md §Multi-tenancy).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Resultado = Literal["aprovado", "devolvido"]


def _limpa(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


class AvaliacaoPedidoCreate(BaseModel):
    id_avaliador: int
    id_anexos: list[int] = Field(min_length=1, max_length=50)
    orientacao: str | None = Field(None, max_length=2000)
    prazo: date | None = None

    _orientacao = field_validator("orientacao")(_limpa)

    @field_validator("id_anexos")
    @classmethod
    def _sem_repetidos(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v):
            raise ValueError("Documento repetido no pedido")
        return v


class DecisaoDocumento(BaseModel):
    id_item: int
    resultado: Resultado
    justificativa: str | None = Field(None, max_length=2000)

    _justificativa = field_validator("justificativa")(_limpa)

    @model_validator(mode="after")
    def _devolucao_justificada(self) -> DecisaoDocumento:
        if self.resultado == "devolvido" and not self.justificativa:
            raise ValueError("A devolução exige justificativa")
        return self


class AvaliacaoDecisoes(BaseModel):
    decisoes: list[DecisaoDocumento] = Field(min_length=1, max_length=50)

    @field_validator("decisoes")
    @classmethod
    def _sem_repetidos(cls, v: list[DecisaoDocumento]) -> list[DecisaoDocumento]:
        ids = [d.id_item for d in v]
        if len(set(ids)) != len(ids):
            raise ValueError("Documento repetido nas decisões")
        return v


class AvaliacaoItemOut(BaseModel):
    id: int
    id_anexo: int
    descricao_anexo: str | None = None
    versao: int
    # `aguardando` | `aprovado` | `devolvido`
    situacao: str
    justificativa: str | None = None
    id_usuario_decisao: int | None = None
    decidido_em: datetime | None = None
    id_avaliacao_anterior: int | None = None
    # Devolvido que já foi reenviado com a versão corrigida (o item novo).
    id_avaliacao_reenvio: int | None = None
    # Devolvido cujo documento já recebeu versão nova, ainda não reenviada.
    pode_reenviar: bool = False


class AvaliacaoPedidoOut(BaseModel):
    id: int
    id_processo: int
    numero_processo: str | None = None
    id_usuario_solicitante: int
    nome_solicitante: str | None = None
    id_usuario_avaliador: int
    nome_avaliador: str | None = None
    orientacao: str | None = None
    prazo: date | None = None
    situacao: str
    criado_em: datetime
    concluido_em: datetime | None = None
    itens: list[AvaliacaoItemOut]
