from pydantic import BaseModel, ConfigDict


class TenantMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    nome: str
    plano: str
    cor_primaria: str | None = None
    logo_url: str | None = None
