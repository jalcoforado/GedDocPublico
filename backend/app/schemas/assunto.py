from pydantic import BaseModel, ConfigDict, Field


class TipoProcessoBase(BaseModel):
    tipo_processo: str = Field(min_length=1, max_length=200)
    exige_processo_pai: bool = False
    ativo: bool = True


class TipoProcessoCreate(TipoProcessoBase):
    pass


class TipoProcessoUpdate(BaseModel):
    tipo_processo: str | None = Field(default=None, min_length=1, max_length=200)
    exige_processo_pai: bool | None = None
    ativo: bool | None = None


class TipoProcessoOut(TipoProcessoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class AssuntoBase(BaseModel):
    assunto: str = Field(min_length=1, max_length=1000)
    id_tipo_processo: int
    exige_processo_pai: bool = False
    ativo: bool = True


class AssuntoCreate(AssuntoBase):
    pass


class AssuntoUpdate(BaseModel):
    assunto: str | None = Field(default=None, min_length=1, max_length=1000)
    id_tipo_processo: int | None = None
    exige_processo_pai: bool | None = None
    ativo: bool | None = None


class AssuntoOut(AssuntoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TipoAnexoBase(BaseModel):
    tipo_anexo: str = Field(min_length=1, max_length=150)


class TipoAnexoCreate(TipoAnexoBase):
    pass


class TipoAnexoUpdate(BaseModel):
    tipo_anexo: str | None = Field(default=None, min_length=1, max_length=150)


class TipoAnexoOut(TipoAnexoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class AssuntoTipoAnexoBase(BaseModel):
    id_assunto: int | None = None
    id_tipo_processo: int | None = None
    id_tipo_anexo: int
    obrigatorio: bool = False
    opcional: bool = False


class AssuntoTipoAnexoCreate(AssuntoTipoAnexoBase):
    pass


class AssuntoTipoAnexoUpdate(BaseModel):
    obrigatorio: bool | None = None
    opcional: bool | None = None


class AssuntoTipoAnexoOut(AssuntoTipoAnexoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
