from pydantic import BaseModel, ConfigDict, Field


class UsuarioBase(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    cpf: str = Field(min_length=11, max_length=11)
    id_unidade_trabalho: int | None = None
    cargo: str | None = None
    ativo: bool = True


class UsuarioCreate(UsuarioBase):
    senha: str = Field(min_length=4, max_length=255)
    grupos: list[int] = Field(default_factory=list)


class UsuarioUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    cpf: str | None = Field(default=None, min_length=11, max_length=11)
    id_unidade_trabalho: int | None = None
    cargo: str | None = None
    ativo: bool | None = None
    senha: str | None = Field(default=None, min_length=4, max_length=255)
    # Sigilo gradual — credencial de acesso. Alterar exige super-usuário.
    nivel_acesso_sigilo: str | None = None


class UsuarioOut(UsuarioBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nivel_acesso_sigilo: str = "interno"


class UsuarioDetail(UsuarioOut):
    grupos: list[int] = Field(default_factory=list)
    unidades_extras: list[int] = Field(default_factory=list)
