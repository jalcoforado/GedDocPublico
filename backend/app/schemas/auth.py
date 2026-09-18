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


class LotacaoOut(BaseModel):
    """Uma lotação (principal ou secundária) que o usuário pode ativar.

    E1 (benchmark SUiTE) — ver `services/permissoes.py::listar_lotacoes`.
    """

    id: int
    nome: str
    principal: bool


class MeResponse(BaseModel):
    id: int
    nome: str
    email: str
    cargo: str | None = None
    id_unidade_trabalho: int | None = None
    must_change_password: bool = False
    is_super_usuario: bool
    permissoes: list[PermissaoItem]
    # E1 — lotação ATIVA da sessão (claim do JWT) e o cardápio de lotações
    # (principal + secundárias) que o usuário pode escolher no "alterar
    # setor". `unidade_contexto_id` pode divergir de `id_unidade_trabalho`
    # quando o usuário trocou para uma secundária.
    unidade_contexto_id: int | None = None
    lotacoes: list[LotacaoOut] = []


class TrocarLotacaoRequest(BaseModel):
    """E1 — corpo de `POST /auth/lotacao-ativa`. O alvo tem de estar entre as
    lotações do próprio usuário (`listar_lotacoes`); outro valor é 403, não
    404 — não há dado sensível a esconder aqui, é só um contexto de sessão."""

    id_unidade_trabalho: int


class AlterarSenhaRequest(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=255)
    nova_senha: str = Field(min_length=SENHA_MINIMA, max_length=255)
