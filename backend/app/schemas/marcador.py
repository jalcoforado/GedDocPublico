from pydantic import BaseModel, ConfigDict, Field


class MarcadorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    id_unidade_trabalho: int | None
    nome: str
    cor: str
    ativo: bool


class MarcadorMini(BaseModel):
    """Só o que a listagem/badge de processo precisa — sem o catálogo inteiro."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    cor: str


class MarcadorCreate(BaseModel):
    id_unidade_trabalho: int | None = None
    nome: str = Field(min_length=1, max_length=60)
    cor: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    ativo: bool = True


class MarcadorUpdate(BaseModel):
    id_unidade_trabalho: int | None = None
    nome: str | None = Field(default=None, min_length=1, max_length=60)
    cor: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    ativo: bool | None = None


class DefinirMarcadoresRequest(BaseModel):
    """Substitui o conjunto inteiro de marcadores do processo — mais simples
    no cliente (envia a seleção completa) do que marcar/desmarcar um a um."""

    ids_marcador: list[int] = Field(default_factory=list)
