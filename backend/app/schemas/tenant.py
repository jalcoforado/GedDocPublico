from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

COR_HEX = r"^#[0-9A-Fa-f]{6}$"

# Fontes de título que o município pode escolher. Lista FECHADA: cada chave é
# um arquivo hospedado no frontend (`frontend/app/fonts/`). Tem de casar com o
# CHECK da migration 0132 e com `FONTES` em `frontend/lib/tema-cores.ts` —
# fonte nova pede migration nova.
FonteDeTitulo = Literal["montserrat", "inter", "roboto_slab", "nunito"]
FONTES_DE_TITULO: tuple[str, ...] = ("montserrat", "inter", "roboto_slab", "nunito")


class TenantMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    nome: str
    plano: str
    cor_primaria: str | None = None
    cor_destaque: str | None = None
    cor_lateral: str | None = None
    cor_titulos: str | None = None
    fonte_titulos: str | None = None
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
    # Tema do município. `#RRGGBB` e nada além: o valor vira CSS no navegador
    # de todo usuário do tenant.
    cor_primaria: str | None = Field(default=None, pattern=COR_HEX)
    cor_destaque: str | None = Field(default=None, pattern=COR_HEX)
    cor_lateral: str | None = Field(default=None, pattern=COR_HEX)
    cor_titulos: str | None = Field(default=None, pattern=COR_HEX)
    # Chave da lista, nunca nome de fonte: o valor vira `font-family`.
    fonte_titulos: FonteDeTitulo | None = None
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
