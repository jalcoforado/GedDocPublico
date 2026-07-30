"""Schemas do catálogo de módulos: launcher (`/modulos/me`) e admin de tenant."""
from pydantic import BaseModel


class ModuloOut(BaseModel):
    slug: str
    nome: str
    icone: str | None = None
    ordem: int


class ModulosMeResponse(BaseModel):
    itens: list[ModuloOut]


class ModuloAdminOut(BaseModel):
    id: int
    slug: str
    nome: str
    icone: str | None = None
    ordem: int
    contratado: bool
    # `modulos_do_tenant` lista também o módulo inativo, para o admin não perder
    # de vista um contrato vivo. Ver a correção da Task 4.
    ativo: bool


class ContratacaoIn(BaseModel):
    slugs: list[str]
