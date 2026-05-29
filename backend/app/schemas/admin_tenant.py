"""Schemas do painel admin de plataforma (PR3a)."""
from datetime import datetime

from pydantic import BaseModel, Field


class AdminTenantOut(BaseModel):
    id: int
    slug: str
    nome: str
    cnpj: str | None = None
    id_cidade: int | None = None
    ativo: bool
    plano: str
    cor_primaria: str | None = None
    logo_url: str | None = None
    codigo_orgao_nup: str | None = None
    usar_nup_federal: bool
    limite_usuarios: int | None = None
    limite_armazenamento_mb: int | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None
    # Derivado do plano (apenas exibição; sem enforcement neste PR).
    modulos: list[str] = []


class AdminTenantCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=50)
    nome: str = Field(min_length=1, max_length=150)
    admin_email: str = Field(min_length=3, max_length=255)
    admin_nome: str = Field(min_length=1, max_length=255)
    admin_cpf: str = Field(min_length=11, max_length=11)
    cnpj: str | None = Field(default=None, max_length=20)
    id_cidade: int | None = None
    plano: str = "basico"
    cor_primaria: str | None = Field(default=None, max_length=7)
    logo_url: str | None = Field(default=None, max_length=500)
    limite_usuarios: int | None = Field(default=None, ge=0)
    limite_armazenamento_mb: int | None = Field(default=None, ge=0)


class AdminTenantUpdate(BaseModel):
    # slug é IMUTÁVEL — não aparece aqui de propósito.
    nome: str | None = Field(default=None, max_length=150)
    cnpj: str | None = Field(default=None, max_length=20)
    id_cidade: int | None = None
    plano: str | None = None
    cor_primaria: str | None = Field(default=None, max_length=7)
    logo_url: str | None = Field(default=None, max_length=500)
    limite_usuarios: int | None = Field(default=None, ge=0)
    limite_armazenamento_mb: int | None = Field(default=None, ge=0)


class AdminTenantCreated(BaseModel):
    tenant: AdminTenantOut
    admin_email: str
    # Exibida UMA ÚNICA VEZ; não é persistida em claro.
    senha_temporaria: str
    aviso: str = (
        "Senha temporária exibida uma única vez. Repasse ao administrador da "
        "prefeitura e oriente a troca após o primeiro acesso."
    )


class AdminMeOut(BaseModel):
    email: str
    is_platform_admin: bool
