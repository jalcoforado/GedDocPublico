from pydantic import BaseModel, Field

from ..auth.password import SENHA_MINIMA


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    # `min_length=1` de propósito: o piso de `SENHA_MINIMA` vale para senha NOVA,
    # não para autenticar. Aplicá-lo aqui trancaria para fora quem já tem senha
    # curta — e ainda contaria ao atacante, pelo 422, quantos caracteres não são.
    senha: str = Field(min_length=1, max_length=255)


class LoginResponse(BaseModel):
    """Resposta do login. Com 2FA pendente (`requer_2fa`) NÃO há sessão: vêm
    só o `desafio` (a apresentar com o código em `/auth/login/2fa`) e o e-mail
    mascarado para onde o código foi; os campos de sessão ficam vazios."""

    access_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    usuario_id: int | None = None
    usuario_email: str | None = None
    nome: str | None = None
    must_change_password: bool = False
    requer_2fa: bool = False
    desafio: str | None = None
    email_mascarado: str | None = None


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


# ---------------------------------------------------------------- conta (0136)


class DoisFatoresRequest(BaseModel):
    desafio: str = Field(min_length=1, max_length=2000)
    codigo: str = Field(min_length=6, max_length=12)
    # "Lembrar este computador por 30 dias".
    lembrar: bool = False


class ReenviarCodigoRequest(BaseModel):
    desafio: str = Field(min_length=1, max_length=2000)


class EsqueciSenhaRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class TokenContaRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class DefinirSenhaRequest(BaseModel):
    """Redefinição pelo link do e-mail ou aceite de convite."""

    token: str = Field(min_length=10, max_length=200)
    nova_senha: str = Field(min_length=SENHA_MINIMA, max_length=255)


class ConviteInfo(BaseModel):
    nome: str
    email: str


class ContaConfirmada(BaseModel):
    """Para onde mandar a pessoa depois: login do servidor ou do cidadão."""

    tipo: str  # "servidor" | "cidadao"


class AvisoEnviado(BaseModel):
    detail: str
