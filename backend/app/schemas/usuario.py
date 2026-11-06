from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UsuarioBase(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    cpf: str = Field(min_length=11, max_length=11)
    id_unidade_trabalho: int | None = None
    cargo: str | None = None
    ativo: bool = True


class UsuarioCreate(UsuarioBase):
    # Sem senha (o padrão da tela desde 0136): a conta nasce com convite por
    # e-mail e a própria pessoa escolhe a senha. Com senha: comportamento
    # antigo (senha temporária, troca obrigatória no primeiro acesso).
    senha: str | None = Field(default=None, min_length=4, max_length=255)
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
    # NULL = convite enviado e ainda não aceito ("Convite pendente" na tela).
    email_verificado_em: datetime | None = None


class UsuarioDetail(UsuarioOut):
    grupos: list[int] = Field(default_factory=list)
    unidades_extras: list[int] = Field(default_factory=list)
