from pydantic import BaseModel


class PermissaoItem(BaseModel):
    codigo: str
    transacao: str
    inserir: bool
    atualizar: bool
    excluir: bool


class PermissaoMeResponse(BaseModel):
    usuario_id: int
    is_super_usuario: bool
    nivel_valor: int | None
    permissoes: list[PermissaoItem]


class ModuloItem(BaseModel):
    id: int
    modulo: str
    icone: str | None = None
    url: str | None = None


class ModulosMeResponse(BaseModel):
    items: list[ModuloItem]
