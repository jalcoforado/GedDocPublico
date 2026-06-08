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


# Veículo regulado — situação masculina (mesmo conjunto do permissionário).
VeiculoReguladoSituacao = Literal["ativo", "pendente", "suspenso", "cassado", "inativo"]
VeiculoCategoria = Literal[
    "automovel",
    "motocicleta",
    "van",
    "micro_onibus",
    "onibus",
    "utilitario",
    "outro",
]
TipoCombustivel = Literal[
    "gasolina",
    "etanol",
    "diesel",
    "flex",
    "gnv",
    "eletrico",
    "hibrido",
    "outro",
]


def _validar_placa(v: str) -> str:
    """Normaliza a placa: uppercase, sem hífen/espaço. Aceita Mercosul e padrão
    antigo de forma simples: 7 caracteres alfanuméricos após normalização."""
    import re

    v = re.sub(r"[\s\-]", "", v).upper()
    if not re.fullmatch(r"[A-Z0-9]{7}", v):
        raise ValueError(
            "Placa inválida. Deve conter 7 caracteres alfanuméricos (Mercosul ou padrão antigo)."
        )
    return v


def _validar_renavam(v: str | None) -> str | None:
    if v is None:
        return v
    v = _so_digitos(v)
    if v == "":
        return None
    if not (9 <= len(v) <= 11):
        raise ValueError("RENAVAM inválido. Deve conter de 9 a 11 dígitos.")
    return v


def _validar_chassi(v: str | None) -> str | None:
    if v is None:
        return v
    import re

    v = re.sub(r"\s", "", v).upper()
    if v == "":
        return None
    if len(v) > 17:
        raise ValueError("Chassi inválido. Deve conter no máximo 17 caracteres.")
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


# ============================ Veículo regulado ==============================
class VeiculoReguladoCreate(BaseModel):
    """Veículo regulado. Pelo menos um de `id_permissionario`/`id_empresa` deve ser
    informado (validado aqui e no serviço; coerência de tenant no serviço).
    `tenant_id`/`id`/`excluido` nunca aceitos."""

    id_permissionario: int | None = None
    id_empresa: int | None = None
    placa: str = Field(min_length=1, max_length=10)
    renavam: str | None = Field(default=None, max_length=14)
    chassi: str | None = Field(default=None, max_length=20)
    marca: str = Field(min_length=1, max_length=60)
    modelo: str = Field(min_length=1, max_length=60)
    ano_fabricacao: int | None = None
    ano_modelo: int | None = None
    cor: str | None = Field(default=None, max_length=30)
    categoria: VeiculoCategoria | None = None
    tipo_servico: TipoServico
    capacidade_passageiros: int | None = Field(default=None, ge=1)
    tipo_combustivel: TipoCombustivel | None = None
    adaptado: bool = False
    numero_autorizacao: str | None = Field(default=None, max_length=40)
    data_inicio_autorizacao: date | None = None
    data_validade_autorizacao: date | None = None
    situacao: VeiculoReguladoSituacao = "pendente"
    observacoes: str | None = None

    @field_validator("placa")
    @classmethod
    def _placa(cls, v: str) -> str:
        return _validar_placa(v)

    @field_validator("renavam")
    @classmethod
    def _renavam(cls, v: str | None) -> str | None:
        return _validar_renavam(v)

    @field_validator("chassi")
    @classmethod
    def _chassi(cls, v: str | None) -> str | None:
        return _validar_chassi(v)

    @model_validator(mode="after")
    def _coerencia(self) -> "VeiculoReguladoCreate":
        if self.id_permissionario is None and self.id_empresa is None:
            raise ValueError(
                "Informe ao menos um vínculo: id_permissionario ou id_empresa."
            )
        if (
            self.ano_fabricacao is not None
            and self.ano_modelo is not None
            and self.ano_modelo < self.ano_fabricacao
        ):
            raise ValueError("ano_modelo deve ser maior ou igual a ano_fabricacao.")
        if (
            self.data_inicio_autorizacao is not None
            and self.data_validade_autorizacao is not None
            and self.data_validade_autorizacao < self.data_inicio_autorizacao
        ):
            raise ValueError(
                "data_validade_autorizacao deve ser posterior ou igual à data_inicio_autorizacao."
            )
        return self


class VeiculoReguladoUpdate(BaseModel):
    """Whitelist de edição — `tenant_id`/`id`/`excluido`/`criado_em`/
    `atualizado_em` nunca aceitos. Coerências revalidadas no serviço."""

    id_permissionario: int | None = None
    id_empresa: int | None = None
    placa: str | None = Field(default=None, min_length=1, max_length=10)
    renavam: str | None = Field(default=None, max_length=14)
    chassi: str | None = Field(default=None, max_length=20)
    marca: str | None = Field(default=None, min_length=1, max_length=60)
    modelo: str | None = Field(default=None, min_length=1, max_length=60)
    ano_fabricacao: int | None = None
    ano_modelo: int | None = None
    cor: str | None = Field(default=None, max_length=30)
    categoria: VeiculoCategoria | None = None
    tipo_servico: TipoServico | None = None
    capacidade_passageiros: int | None = Field(default=None, ge=1)
    tipo_combustivel: TipoCombustivel | None = None
    adaptado: bool | None = None
    numero_autorizacao: str | None = Field(default=None, max_length=40)
    data_inicio_autorizacao: date | None = None
    data_validade_autorizacao: date | None = None
    situacao: VeiculoReguladoSituacao | None = None
    observacoes: str | None = None

    @field_validator("placa")
    @classmethod
    def _placa(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validar_placa(v)

    @field_validator("renavam")
    @classmethod
    def _renavam(cls, v: str | None) -> str | None:
        return _validar_renavam(v)

    @field_validator("chassi")
    @classmethod
    def _chassi(cls, v: str | None) -> str | None:
        return _validar_chassi(v)


class VeiculoReguladoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_permissionario: int | None = None
    id_empresa: int | None = None
    placa: str
    renavam: str | None = None
    chassi: str | None = None
    marca: str
    modelo: str
    ano_fabricacao: int | None = None
    ano_modelo: int | None = None
    cor: str | None = None
    categoria: str | None = None
    tipo_servico: str
    capacidade_passageiros: int | None = None
    tipo_combustivel: str | None = None
    adaptado: bool
    numero_autorizacao: str | None = None
    data_inicio_autorizacao: date | None = None
    data_validade_autorizacao: date | None = None
    situacao: str
    observacoes: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None
