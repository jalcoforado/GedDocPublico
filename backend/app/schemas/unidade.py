from pydantic import BaseModel, ConfigDict, Field


class UnidadeTrabalhoBase(BaseModel):
    unidade_trabalho: str = Field(min_length=1, max_length=255)
    sigla: str | None = None
    id_unidade_pai: int | None = None
    id_tipo_unidade_trabalho: int | None = None


class UnidadeTrabalhoCreate(UnidadeTrabalhoBase):
    pass


class UnidadeTrabalhoUpdate(BaseModel):
    unidade_trabalho: str | None = Field(default=None, min_length=1, max_length=255)
    sigla: str | None = None
    id_unidade_pai: int | None = None
    id_tipo_unidade_trabalho: int | None = None


class UnidadeTrabalhoOut(UnidadeTrabalhoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TipoUnidadeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo_unidade_trabalho: str
    codigo: str | None = None
