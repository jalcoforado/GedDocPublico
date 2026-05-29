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
    # PR 3b — dados institucionais
    sigla: str | None = None
    email_institucional: str | None = None
    telefone_institucional: str | None = None
    endereco: str | None = None
    site_oficial: str | None = None
    horario_atendimento: str | None = None
    texto_boas_vindas_portal: str | None = None
    id_unidade_padrao: int | None = None


class TenantNupConfigUpdate(BaseModel):
    """Body do PUT /api/v2/tenants/me/nup-config.

    `codigo_orgao_nup` precisa ser preenchido (5 dígitos) antes de ativar a flag.
    """

    codigo_orgao_nup: str | None = Field(
        default=None, min_length=5, max_length=5, pattern=r"^[0-9]{5}$"
    )
    usar_nup_federal: bool | None = None


class TenantInstitucionalUpdate(BaseModel):
    """Body do PUT /api/v2/tenants/me — **whitelist** de campos institucionais.

    Só estes campos são aceitos. Campos de plataforma (id, slug, plano, ativo,
    limite_*, cnpj, codigo_orgao_nup, usar_nup_federal) enviados no corpo são
    **ignorados** (Pydantic descarta extras por padrão). O endpoint nunca usa
    `tenant_id` do cliente — escopo vem de `request.state.tenant_id`.
    """

    nome: str | None = Field(default=None, min_length=1, max_length=150)
    sigla: str | None = Field(default=None, max_length=20)
    email_institucional: str | None = Field(default=None, max_length=255)
    telefone_institucional: str | None = Field(default=None, max_length=20)
    endereco: str | None = None
    site_oficial: str | None = Field(default=None, max_length=255)
    horario_atendimento: str | None = Field(default=None, max_length=255)
    texto_boas_vindas_portal: str | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    cor_primaria: str | None = Field(default=None, max_length=7)
    id_unidade_padrao: int | None = None


class OnboardingItem(BaseModel):
    """Item do checklist de onboarding. `concluido=None` = não avaliado."""

    chave: str
    rotulo: str
    concluido: bool | None


class OnboardingResponse(BaseModel):
    itens: list[OnboardingItem]
    total: int
    concluidos: int
    pendentes: int


class ResetSenhaResponse(BaseModel):
    """Resposta do reset de senha temporária — exibida **uma única vez**."""

    id_usuario: int
    senha_temporaria: str
    aviso: str
