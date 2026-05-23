from pydantic import BaseModel, ConfigDict, Field


class EstadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    estado: str
    uf: str


class CidadeBase(BaseModel):
    cidade: str = Field(min_length=1, max_length=255)
    id_estado: int | None = None


class CidadeCreate(CidadeBase):
    pass


class CidadeUpdate(BaseModel):
    cidade: str | None = Field(default=None, min_length=1, max_length=255)
    id_estado: int | None = None


class CidadeOut(CidadeBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class BairroBase(BaseModel):
    bairro: str = Field(min_length=1, max_length=255)
    id_cidade: int | None = None
    ativo: bool = True


class BairroCreate(BairroBase):
    pass


class BairroUpdate(BaseModel):
    bairro: str | None = Field(default=None, min_length=1, max_length=255)
    id_cidade: int | None = None
    ativo: bool | None = None


class BairroOut(BairroBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class EnderecoBase(BaseModel):
    id_cidade: int | None = None
    id_bairro: int | None = None
    id_estado: int | None = None
    rua: str | None = None
    numero: str | None = None
    complemento: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class EnderecoCreate(EnderecoBase):
    pass


class EnderecoUpdate(EnderecoBase):
    pass


class EnderecoOut(EnderecoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
