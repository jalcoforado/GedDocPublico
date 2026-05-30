"""Schemas de complementação documental (PR 4d).

`SolicitarComplementacaoRequest` recebe **keys** dos itens em
`documentos_exigidos` do serviço (validadas no service layer).
`ComplementacaoOut` projeta cada item solicitado já cruzado com os anexos
(`enviado: bool`) para a UI poder mostrar progresso sem refetch do checklist.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


StatusComplementacao = Literal["aberta", "respondida", "cancelada"]


class SolicitarComplementacaoRequest(BaseModel):
    mensagem: str = Field(min_length=1, max_length=2000)
    documentos_solicitados: list[str] = Field(min_length=1)


class CancelarComplementacaoRequest(BaseModel):
    motivo: str | None = Field(default=None, max_length=500)


class ComplementacaoDocSolicitadoOut(BaseModel):
    """Projeção segura do item solicitado (sem dados sensíveis)."""

    key: str
    nome: str
    descricao: str | None = None
    enviado: bool


class ComplementacaoOut(BaseModel):
    id: int
    status: StatusComplementacao
    mensagem: str
    documentos_solicitados: list[ComplementacaoDocSolicitadoOut]
    id_usuario_solicitante: int
    nome_solicitante: str | None = None
    # `criado_em` = dt_solicitacao por convenção do projeto.
    criado_em: datetime
    atualizado_em: datetime | None = None
    respondido_em: datetime | None = None
    cancelado_em: datetime | None = None
    motivo_cancelamento: str | None = None
