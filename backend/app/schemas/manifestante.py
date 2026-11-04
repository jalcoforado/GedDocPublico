import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 'F' pessoa física, 'J' pessoa jurídica (migration 0136).
Natureza = Literal["F", "J"]
NOME_DO_DOCUMENTO: dict[str, str] = {"F": "CPF", "J": "CNPJ"}
FORMATO_DO_DOCUMENTO: dict[str, str] = {
    "F": "11 dígitos",
    "J": "14 caracteres: 12 letras ou dígitos e 2 dígitos finais",
}

# Conferência de forma, não de existência: o e-mail de verdade só se prova
# entregando. `EmailStr` não serve aqui — recusa os domínios reservados
# (`.test`) que a demonstração e os testes usam.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normaliza_cpf_cnpj(v: object) -> object:
    """CPF/CNPJ é guardado sem máscara, venha com ela ou não.

    O portal do cidadão liga cidadão a processo por igualdade exata de
    `cpf_cnpj`, e o do cidadão é guardado sem máscara: gravado com pontos e
    traço, o manifestante nunca aparecia para ele. Vazio vira `None`.

    Fica só letra e dígito, em maiúsculas: o CNPJ alfanumérico (IN RFB
    2.229/2024, emitido desde julho de 2026) tem letras nas 12 primeiras
    posições. Se a tela mandar letra num CPF, `_conferir_documento` recusa.
    """
    if isinstance(v, str):
        chave = "".join(ch for ch in v if ch.isascii() and ch.isalnum()).upper()
        return chave or None
    return v


def documento_valido(natureza: str, doc: str) -> bool:
    """CPF: 11 dígitos. CNPJ: 12 posições de letra ou dígito + 2 dígitos
    verificadores (o DV continua numérico também no alfanumérico)."""
    if natureza == "F":
        return len(doc) == 11 and doc.isdigit()
    return len(doc) == 14 and doc[:12].isalnum() and doc[12:].isdigit()


def telefone_formatado(v: object) -> object:
    """Telefone é guardado no formato de exibição, `(85) 99999-9999`.

    Ele aparece cru em outras telas (requerente do processo, documentos), então
    gravar formatado poupa formatar em cada uma. Aceita fixo (10 dígitos) e
    celular (11); vazio vira `None`.
    """
    if not isinstance(v, str):
        return v
    d = "".join(ch for ch in v if ch.isdigit())
    if not d:
        return None
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    raise ValueError("telefone deve ter DDD e 8 ou 9 dígitos")


def email_normalizado(v: object) -> object:
    if not isinstance(v, str):
        return v
    v = v.strip().lower()
    if not v:
        return None
    if not _EMAIL.match(v):
        raise ValueError("e-mail inválido")
    return v


def texto_aparado(v: object) -> object:
    if isinstance(v, str):
        return v.strip() or None
    return v


class TipoManifestanteBase(BaseModel):
    tipo_manifestante: str = Field(min_length=1, max_length=150)
    id_categoria: int
    natureza: Natureza = "F"
    ativo: bool = True


class TipoManifestanteCreate(TipoManifestanteBase):
    pass


class TipoManifestanteUpdate(BaseModel):
    tipo_manifestante: str | None = Field(default=None, min_length=1, max_length=150)
    id_categoria: int | None = None
    natureza: Natureza | None = None
    ativo: bool | None = None


class TipoManifestanteOut(TipoManifestanteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ManifestanteBase(BaseModel):
    id_tipo_manifestante: int
    cpf_cnpj: str | None = Field(default=None, max_length=14)
    nome: str | None = Field(default=None, max_length=255)
    responsavel: str | None = None
    organizacao: str | None = None
    telefone_celular: str | None = None
    telefone_residencial: str | None = None
    telefone_comercial: str | None = None
    email: str | None = None
    observacao: str | None = None
    ativo: bool = True

    _cpf_cnpj = field_validator("cpf_cnpj", mode="before")(normaliza_cpf_cnpj)


class ManifestanteCreate(ManifestanteBase):
    """Cadastro pela tela: nome, documento, celular e e-mail são obrigatórios.

    A obrigatoriedade mora aqui e não em `ManifestanteBase`, que também molda
    `ManifestanteOut`: há cadastros antigos sem celular, e eles continuam
    sendo lidos. O portal do cidadão cria manifestante pelo serviço
    (`cidadao_processos`), sem passar por este schema.
    Se o documento é CPF ou CNPJ depende do tipo, e por isso o formato é
    conferido no router, que carrega o tipo (`documento_valido`).
    """

    # Sem default: a chave ausente já é recusada. `| None` deixa o vazio
    # (que os validadores `before` viram `None`) chegar a `_obrigatorio`, com
    # mensagem própria em vez do "Input should be a valid string".
    cpf_cnpj: str | None = Field(max_length=14)
    nome: str | None = Field(max_length=255)
    telefone_celular: str | None
    email: str | None

    _texto = field_validator("nome", "responsavel", "organizacao", mode="before")(texto_aparado)
    _telefones = field_validator(
        "telefone_celular", "telefone_residencial", "telefone_comercial", mode="before"
    )(telefone_formatado)
    _email = field_validator("email", mode="before")(email_normalizado)

    @field_validator("nome", "cpf_cnpj", "telefone_celular", "email")
    @classmethod
    def _obrigatorio(cls, v: object) -> object:
        if v is None:
            raise ValueError("campo obrigatório")
        return v


class ManifestanteUpdate(BaseModel):
    """Edição parcial: campo ausente fica como está; os obrigatórios do
    cadastro, se vierem, não podem vir vazios."""

    id_tipo_manifestante: int | None = None
    cpf_cnpj: str | None = Field(default=None, max_length=14)
    nome: str | None = Field(default=None, max_length=255)
    responsavel: str | None = None
    organizacao: str | None = None
    telefone_celular: str | None = None
    telefone_residencial: str | None = None
    telefone_comercial: str | None = None
    email: str | None = None
    observacao: str | None = None
    ativo: bool | None = None

    _cpf_cnpj = field_validator("cpf_cnpj", mode="before")(normaliza_cpf_cnpj)
    _texto = field_validator("nome", "responsavel", "organizacao", mode="before")(texto_aparado)
    _telefones = field_validator(
        "telefone_celular", "telefone_residencial", "telefone_comercial", mode="before"
    )(telefone_formatado)
    _email = field_validator("email", mode="before")(email_normalizado)

    @field_validator("id_tipo_manifestante", "nome", "cpf_cnpj", "telefone_celular", "email", "ativo")
    @classmethod
    def _obrigatorio_nao_esvazia(cls, v: object) -> object:
        if v is None:
            raise ValueError("campo obrigatório")
        return v


class ManifestanteOut(ManifestanteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
