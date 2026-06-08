"""Schemas do módulo de Transporte Regulado — Permissionário (fundação).

`cpf`/`cnh_numero` são normalizados (só dígitos). `PermissionarioUpdate` é
whitelist: `tenant_id`/`id`/`excluido`/`criado_em`/`atualizado_em` nunca aceitos.
"""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TipoServico = Literal[
    "taxi",
    "mototaxi",
    "transporte_escolar",
    "motofrete",
    "transporte_distrital",
    "aplicativo",
    "outro",
]
PermissionarioSituacao = Literal["ativo", "pendente", "suspenso", "cassado", "inativo"]
# Empresa usa a forma feminina da situação (empresa ativa/suspensa/cassada/inativa).
EmpresaSituacao = Literal["ativa", "pendente", "suspensa", "cassada", "inativa"]
CnhCategoria = Literal["A", "B", "AB", "C", "D", "E", "AC", "AD", "AE"]
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _so_digitos(v: str) -> str:
    import re

    return re.sub(r"\D", "", v)


def _validar_cnpj(v: str) -> str:
    v = _so_digitos(v)
    if len(v) != 14:
        raise ValueError("CNPJ inválido. Deve conter 14 dígitos.")
    return v


def _validar_uf(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip().upper()
    if v == "":
        return None
    if len(v) != 2:
        raise ValueError("UF inválida. Deve conter 2 caracteres.")
    return v


def _validar_email(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip()
    if v == "":
        return None
    import re

    if not re.match(EMAIL_PATTERN, v):
        raise ValueError("E-mail inválido.")
    return v


def _validar_cnh(v: str | None) -> str | None:
    if v is None:
        return v
    v = _so_digitos(v)
    if v == "":
        return None
    if len(v) != 11:
        raise ValueError("Número da CNH inválido. Deve conter 11 dígitos.")
    return v


class PermissionarioCreate(BaseModel):
    """`situacao` default 'pendente'; `tenant_id`/`id`/`excluido` nunca aceitos."""

    nome: str = Field(min_length=1, max_length=150)
    cpf: str = Field(min_length=11, max_length=14)
    rg: str | None = Field(default=None, max_length=20)
    data_nascimento: date | None = None
    telefone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    cnh_numero: str | None = Field(default=None, max_length=14)
    cnh_categoria: CnhCategoria | None = None
    cnh_validade: date | None = None
    tipo_servico: TipoServico
    numero_permissao: str | None = Field(default=None, max_length=40)
    data_inicio_permissao: date | None = None
    data_validade_permissao: date | None = None
    situacao: PermissionarioSituacao = "pendente"
    observacoes: str | None = None

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v: str) -> str:
        v = _so_digitos(v)
        if len(v) != 11:
            raise ValueError("CPF inválido. Deve conter 11 dígitos.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return _validar_email(v)

    @field_validator("cnh_numero")
    @classmethod
    def _cnh(cls, v: str | None) -> str | None:
        return _validar_cnh(v)

    @model_validator(mode="after")
    def _coerencia(self) -> "PermissionarioCreate":
        # CNH com validade obrigatória quando a CNH é informada.
        if self.cnh_numero and self.cnh_validade is None:
            raise ValueError("cnh_validade é obrigatória quando a CNH é informada.")
        # Coerência das datas da permissão.
        if (
            self.data_inicio_permissao is not None
            and self.data_validade_permissao is not None
            and self.data_validade_permissao < self.data_inicio_permissao
        ):
            raise ValueError(
                "data_validade_permissao deve ser posterior ou igual à data_inicio_permissao."
            )
        return self


class PermissionarioUpdate(BaseModel):
    """Whitelist de edição — `tenant_id`/`id`/`excluido`/`criado_em`/
    `atualizado_em` nunca aceitos. `situacao` é editável (também há ações
    dedicadas inativar/reativar/suspender). Coerências revalidadas no serviço."""

    nome: str | None = Field(default=None, min_length=1, max_length=150)
    cpf: str | None = Field(default=None, min_length=11, max_length=14)
    rg: str | None = Field(default=None, max_length=20)
    data_nascimento: date | None = None
    telefone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    cnh_numero: str | None = Field(default=None, max_length=14)
    cnh_categoria: CnhCategoria | None = None
    cnh_validade: date | None = None
    tipo_servico: TipoServico | None = None
    numero_permissao: str | None = Field(default=None, max_length=40)
    data_inicio_permissao: date | None = None
    data_validade_permissao: date | None = None
    situacao: PermissionarioSituacao | None = None
    observacoes: str | None = None

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = _so_digitos(v)
        if len(v) != 11:
            raise ValueError("CPF inválido. Deve conter 11 dígitos.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return _validar_email(v)

    @field_validator("cnh_numero")
    @classmethod
    def _cnh(cls, v: str | None) -> str | None:
        return _validar_cnh(v)


class PermissionarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    cpf: str
    rg: str | None = None
    data_nascimento: date | None = None
    telefone: str | None = None
    email: str | None = None
    cnh_numero: str | None = None
    cnh_categoria: str | None = None
    cnh_validade: date | None = None
    tipo_servico: str
    numero_permissao: str | None = None
    data_inicio_permissao: date | None = None
    data_validade_permissao: date | None = None
    situacao: str
    observacoes: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None


# ============================ Empresa =======================================
class EmpresaCreate(BaseModel):
    """`situacao` default 'pendente'; `tenant_id`/`id`/`excluido` nunca aceitos.
    `id_representante_permissionario` opcional — coerência de tenant no serviço."""

    razao_social: str = Field(min_length=1, max_length=200)
    nome_fantasia: str | None = Field(default=None, max_length=200)
    cnpj: str = Field(min_length=14, max_length=18)
    inscricao_municipal: str | None = Field(default=None, max_length=30)
    inscricao_estadual: str | None = Field(default=None, max_length=30)
    telefone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    cep: str | None = Field(default=None, max_length=9)
    logradouro: str | None = Field(default=None, max_length=200)
    numero: str | None = Field(default=None, max_length=20)
    complemento: str | None = Field(default=None, max_length=100)
    bairro: str | None = Field(default=None, max_length=100)
    municipio: str | None = Field(default=None, max_length=100)
    uf: str | None = Field(default=None, max_length=2)
    tipo_servico: TipoServico
    numero_autorizacao: str | None = Field(default=None, max_length=40)
    data_inicio_autorizacao: date | None = None
    data_validade_autorizacao: date | None = None
    id_representante_permissionario: int | None = None
    situacao: EmpresaSituacao = "pendente"
    observacoes: str | None = None

    @field_validator("cnpj")
    @classmethod
    def _cnpj(cls, v: str) -> str:
        return _validar_cnpj(v)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return _validar_email(v)

    @field_validator("uf")
    @classmethod
    def _uf(cls, v: str | None) -> str | None:
        return _validar_uf(v)

    @model_validator(mode="after")
    def _coerencia(self) -> "EmpresaCreate":
        if (
            self.data_inicio_autorizacao is not None
            and self.data_validade_autorizacao is not None
            and self.data_validade_autorizacao < self.data_inicio_autorizacao
        ):
            raise ValueError(
                "data_validade_autorizacao deve ser posterior ou igual à data_inicio_autorizacao."
            )
        return self


class EmpresaUpdate(BaseModel):
    """Whitelist de edição — `tenant_id`/`id`/`excluido`/`criado_em`/
    `atualizado_em` nunca aceitos. `situacao` é editável (também há ações
    dedicadas inativar/reativar/suspender). Coerências revalidadas no serviço."""

    razao_social: str | None = Field(default=None, min_length=1, max_length=200)
    nome_fantasia: str | None = Field(default=None, max_length=200)
    cnpj: str | None = Field(default=None, min_length=14, max_length=18)
    inscricao_municipal: str | None = Field(default=None, max_length=30)
    inscricao_estadual: str | None = Field(default=None, max_length=30)
    telefone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    cep: str | None = Field(default=None, max_length=9)
    logradouro: str | None = Field(default=None, max_length=200)
    numero: str | None = Field(default=None, max_length=20)
    complemento: str | None = Field(default=None, max_length=100)
    bairro: str | None = Field(default=None, max_length=100)
    municipio: str | None = Field(default=None, max_length=100)
    uf: str | None = Field(default=None, max_length=2)
    tipo_servico: TipoServico | None = None
    numero_autorizacao: str | None = Field(default=None, max_length=40)
    data_inicio_autorizacao: date | None = None
    data_validade_autorizacao: date | None = None
    id_representante_permissionario: int | None = None
    situacao: EmpresaSituacao | None = None
    observacoes: str | None = None

    @field_validator("cnpj")
    @classmethod
    def _cnpj(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validar_cnpj(v)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return _validar_email(v)

    @field_validator("uf")
    @classmethod
    def _uf(cls, v: str | None) -> str | None:
        return _validar_uf(v)


class EmpresaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    razao_social: str
    nome_fantasia: str | None = None
    cnpj: str
    inscricao_municipal: str | None = None
    inscricao_estadual: str | None = None
    telefone: str | None = None
    email: str | None = None
    cep: str | None = None
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    municipio: str | None = None
    uf: str | None = None
    tipo_servico: str
    numero_autorizacao: str | None = None
    data_inicio_autorizacao: date | None = None
    data_validade_autorizacao: date | None = None
    id_representante_permissionario: int | None = None
    situacao: str
    observacoes: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None
