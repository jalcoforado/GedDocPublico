from pydantic import BaseModel, ConfigDict, Field


class TenantMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    nome: str
    plano: str
    cor_primaria: str | None = None
    logo_url: str | None = None
    # Fase P2 — NUP federal
    codigo_orgao_nup: str | None = None
    usar_nup_federal: bool = False


class TenantNupConfigUpdate(BaseModel):
    """Body do PUT /api/v2/tenants/me/nup-config.

    `codigo_orgao_nup` precisa ser preenchido (5 dígitos) antes de ativar a flag.
    """

    codigo_orgao_nup: str | None = Field(
        default=None, min_length=5, max_length=5, pattern=r"^[0-9]{5}$"
    )
    usar_nup_federal: bool | None = None
