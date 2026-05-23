from pydantic import BaseModel, ConfigDict, Field


class GrupoBase(BaseModel):
    grupo: str = Field(min_length=1, max_length=255)
    id_nivel: int
    id_sistema: int


class GrupoCreate(GrupoBase):
    pass


class GrupoUpdate(BaseModel):
    grupo: str | None = Field(default=None, min_length=1, max_length=255)
    id_nivel: int | None = None
    id_sistema: int | None = None


class GrupoOut(GrupoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TransacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    transacao: str
    codigo: str


class GrupoTransacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_transacao: int
    inserir: bool
    atualizar: bool
    excluir: bool


class GrupoTransacaoSet(BaseModel):
    id_transacao: int
    inserir: bool = False
    atualizar: bool = False
    excluir: bool = False


class GrupoTransacoesUpdate(BaseModel):
    transacoes: list[GrupoTransacaoSet]


class NivelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nivel: str
    valor: int


class SistemaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sistema: str
    app: str | None = None
