"""Schemas de Template de Documento e Minuta.

`*Update` são whitelist: `tenant_id`/`id`/`status`/`excluido`/timestamps nunca
aceitos do cliente. `MinutaUpdate.versao` é usado para lock otimista (o cliente
envia a versão que estava editando; divergência → 409 no serviço).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MinutaOrigem = Literal["interno", "google"]
MinutaStatus = Literal["rascunho", "finalizada", "cancelada"]


# ============================ Template de documento =========================
class TemplateDocumentoCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    descricao: str | None = Field(default=None, max_length=300)
    categoria: str | None = Field(default=None, max_length=80)
    corpo_html: str = Field(min_length=1)
    ativo: bool = True


class TemplateDocumentoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    descricao: str | None = Field(default=None, max_length=300)
    categoria: str | None = Field(default=None, max_length=80)
    corpo_html: str | None = Field(default=None, min_length=1)
    ativo: bool | None = None


class TemplateDocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    descricao: str | None
    categoria: str | None
    corpo_html: str
    placeholders_utilizados: list | None
    ativo: bool
    id_usuario_criacao: int | None
    criado_em: datetime
    atualizado_em: datetime | None


class PlaceholderInfo(BaseModel):
    chave: str
    descricao: str


# ==================================== Minuta ================================
class MinutaCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=255)
    origem: MinutaOrigem = "interno"
    id_template_origem: int | None = None
    # corpo_html só para origem="interno" sem template (documento em branco). Quando
    # um template é informado, o corpo é gerado pela resolução de placeholders.
    corpo_html: str | None = None


class MinutaUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=255)
    corpo_html: str | None = None
    # Lock otimista: versão que o cliente carregou. Se divergir da atual → 409.
    versao: int | None = None


class MinutaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_processo: int
    id_template_origem: int | None
    titulo: str
    origem: MinutaOrigem
    status: MinutaStatus
    versao: int
    corpo_html: str | None
    google_doc_id: str | None
    google_doc_url: str | None
    id_anexo_final: int | None
    id_usuario_criacao: int
    id_usuario_finalizacao: int | None
    finalizada_em: datetime | None
    criado_em: datetime
    atualizado_em: datetime | None


class MinutaListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_processo: int
    titulo: str
    origem: MinutaOrigem
    status: MinutaStatus
    versao: int
    id_anexo_final: int | None
    id_usuario_criacao: int
    criado_em: datetime
    atualizado_em: datetime | None
