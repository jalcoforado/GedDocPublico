from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    senha: str = Field(min_length=1, max_length=255)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    usuario_id: int
    usuario_email: str
    nome: str
    # SEC-1 Commit 4 — sinaliza ao frontend se o usuário caiu em estado de
    # senha temporária. Apenas boolean: nada de hash, senha em claro ou token
    # extra. Default False para compatibilidade com clientes legados que não
    # leem o campo.
    must_change_password: bool = False


class MeResponse(BaseModel):
    id: int
    nome: str
    email: str
    cargo: str | None = None
    id_unidade_trabalho: int | None = None
    # SEC-1 Commit 4 — espelho da flag para que o frontend possa verificar o
    # estado em qualquer momento após o login (não só na resposta de /login).
    # /auth/me já está na whitelist do guard (Commit 2), então retorna
    # normalmente mesmo com flag=true.
    must_change_password: bool = False


class AlterarSenhaRequest(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=255)
    nova_senha: str = Field(min_length=6, max_length=255)
