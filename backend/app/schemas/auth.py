from pydantic import BaseModel, Field

from ..auth.password import SENHA_MINIMA


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    # `min_length=1` de propósito: o piso de `SENHA_MINIMA` vale para senha NOVA,
    # não para autenticar. Aplicá-lo aqui trancaria para fora quem já tem senha
    # curta — e ainda contaria ao atacante, pelo 422, quantos caracteres não são.
    senha: str = Field(min_length=1, max_length=255)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    usuario_id: int
    usuario_email: str
    nome: str
    must_change_password: bool = False


class PermissaoItem(BaseModel):
    codigo: str
    transacao: str
    inserir: bool
    atualizar: bool
    excluir: bool


class MeResponse(BaseModel):
    id: int
    nome: str
    email: str
    cargo: str | None = None
    id_unidade_trabalho: int | None = None
    must_change_password: bool = False
    is_super_usuario: bool
    permissoes: list[PermissaoItem]


class AlterarSenhaRequest(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=255)
    nova_senha: str = Field(min_length=SENHA_MINIMA, max_length=255)
