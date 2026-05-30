"""Schemas do checklist documental (PR 4c).

Status calculados em runtime (sem tabela), a partir de `servico.documentos_exigidos`
e dos anexos do processo agrupados por `anexo.documento_exigido_key`.
"""
from typing import Literal

from pydantic import BaseModel


StatusDocumental = Literal["sem_documentos_exigidos", "pendente", "parcial", "completo"]


class ChecklistAnexo(BaseModel):
    """Anexo associado a um item exigido (projeção segura — sem dados sensíveis)."""

    id_anexo: int
    descricao: str | None = None


class ChecklistItem(BaseModel):
    key: str
    nome: str
    obrigatorio: bool
    descricao: str | None = None
    enviado: bool
    anexos: list[ChecklistAnexo]


class ChecklistDocumentosResponse(BaseModel):
    id_processo: int
    id_servico: int | None = None
    status_documental: StatusDocumental
    obrigatorios_total: int
    obrigatorios_enviados: int
    itens: list[ChecklistItem]
