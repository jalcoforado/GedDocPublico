from pydantic import BaseModel, ConfigDict, Field, field_validator


def so_digitos_cpf_cnpj(v: object) -> object:
    """CPF/CNPJ é guardado só com dígitos, venha com máscara ou não.

    O portal do cidadão liga cidadão a processo por igualdade exata de
    `cpf_cnpj`, e o do cidadão é guardado sem máscara: gravado com pontos e
    traço, o manifestante nunca aparecia para ele. Vazio vira `None`.
    """
    if isinstance(v, str):
        digitos = "".join(ch for ch in v if ch.isdigit())
        return digitos or None
    return v


class TipoManifestanteBase(BaseModel):
    tipo_manifestante: str = Field(min_length=1, max_length=150)
    id_categoria: int
    ativo: bool = True


class TipoManifestanteCreate(TipoManifestanteBase):
    pass


class TipoManifestanteUpdate(BaseModel):
    tipo_manifestante: str | None = Field(default=None, min_length=1, max_length=150)
    id_categoria: int | None = None
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

    _cpf_cnpj = field_validator("cpf_cnpj", mode="before")(so_digitos_cpf_cnpj)


class ManifestanteCreate(ManifestanteBase):
    pass


class ManifestanteUpdate(BaseModel):
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

    _cpf_cnpj = field_validator("cpf_cnpj", mode="before")(so_digitos_cpf_cnpj)


class ManifestanteOut(ManifestanteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
