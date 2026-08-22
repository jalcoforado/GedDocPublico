"""Schemas do módulo de Transporte Regulado — Permissionário (fundação).

`cpf`/`cnh_numero` são normalizados (só dígitos). `PermissionarioUpdate` é
whitelist: `tenant_id`/`id`/`excluido`/`criado_em`/`atualizado_em` nunca aceitos.
"""
from datetime import date, datetime, time
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


# ============================ Documento Veículo ==============================
TipoDocumento = Literal[
    "crlv", "cnh_copia", "inspecao", "vistoria", "seguro",
    "autorizacao_especial", "adaptacao", "outro"
]
StatusDocumento = Literal["pendente", "valido", "vencido", "rejeitado"]
ResultadoAvaliacao = Literal["pendente", "aprovado", "reprovado", "condicional"]


class VeiculoDocumentoCreate(BaseModel):
    """Documento de veículo regulado. `tipo_documento` em enum, `numero_documento`
    não vazio, `data_emissao <= data_validade` se ambas informadas."""

    tipo_documento: TipoDocumento
    numero_documento: str = Field(min_length=1, max_length=100)
    data_emissao: date | None = None
    data_validade: date | None = None
    observacoes: str | None = None

    @field_validator("numero_documento")
    @classmethod
    def _numero_documento(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("numero_documento não pode estar vazio.")
        return v

    @model_validator(mode="after")
    def _coerencia_datas(self) -> "VeiculoDocumentoCreate":
        if (
            self.data_emissao is not None
            and self.data_validade is not None
            and self.data_emissao > self.data_validade
        ):
            raise ValueError("data_emissao deve ser anterior ou igual a data_validade.")
        return self


class VeiculoDocumentoUpdate(BaseModel):
    """Atualização de documento — todos os campos opcional."""

    tipo_documento: TipoDocumento | None = None
    numero_documento: str | None = Field(default=None, min_length=1, max_length=100)
    data_emissao: date | None = None
    data_validade: date | None = None
    observacoes: str | None = None

    @field_validator("numero_documento")
    @classmethod
    def _numero_documento(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v.strip() == "":
            raise ValueError("numero_documento não pode estar vazio.")
        return v


class VeiculoDocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    id_veiculo: int
    tipo_documento: str
    numero_documento: str
    data_emissao: date | None = None
    data_validade: date | None = None
    situacao: str
    observacoes: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None
    excluido: bool


# ============================ Avaliação Veículo ==============================
class VeiculoAvaliacaoCreate(BaseModel):
    """Avaliação/parecer regulatório de veículo. `resultado` em enum, `parecer`
    obrigatório e com mínimo 10 caracteres, `data_avaliacao` não pode ser futura."""

    resultado: ResultadoAvaliacao
    parecer: str = Field(min_length=10, max_length=5000)
    observacoes: str | None = None
    data_avaliacao: datetime

    @field_validator("parecer")
    @classmethod
    def _parecer(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("parecer não pode estar vazio.")
        return v

    @model_validator(mode="after")
    def _coerencia_data(self) -> "VeiculoAvaliacaoCreate":
        from datetime import datetime as dt

        agora = dt.utcnow()
        if self.data_avaliacao > agora:
            raise ValueError("data_avaliacao não pode ser uma data futura.")
        return self


class VeiculoAvaliacaoUpdate(BaseModel):
    """Atualização de avaliação — todos os campos opcional."""

    resultado: ResultadoAvaliacao | None = None
    parecer: str | None = Field(default=None, min_length=10, max_length=5000)
    observacoes: str | None = None
    data_avaliacao: datetime | None = None

    @field_validator("parecer")
    @classmethod
    def _parecer(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v.strip() == "":
            raise ValueError("parecer não pode estar vazio.")
        return v


class VeiculoAvaliacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    id_veiculo: int
    id_usuario_avaliador: int
    resultado: str
    parecer: str
    observacoes: str | None = None
    data_avaliacao: datetime
    criado_em: datetime
    atualizado_em: datetime | None = None
    excluido: bool


# ============================ Vistoria Veículo ================================
class VeiculoVistoriaCreate(BaseModel):
    """Vistoria regulatória de veículo (inspeção realizada por auditor).
    `resultado` em enum, `parecer` obrigatório e com mínimo 10 caracteres,
    `data_vistoria` não pode ser futura."""

    resultado: ResultadoAvaliacao
    parecer: str = Field(min_length=10, max_length=5000)
    observacoes: str | None = None
    data_vistoria: datetime
    data_validade: date | None = None

    @field_validator("parecer")
    @classmethod
    def _parecer(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("parecer não pode estar vazio.")
        return v

    @model_validator(mode="after")
    def _coerencia_data(self) -> "VeiculoVistoriaCreate":
        from datetime import datetime as dt

        agora = dt.utcnow()
        if self.data_vistoria > agora:
            raise ValueError("data_vistoria não pode ser uma data futura.")
        return self


class VeiculoVistoriaUpdate(BaseModel):
    """Atualização de vistoria — todos os campos opcional."""

    resultado: ResultadoAvaliacao | None = None
    parecer: str | None = Field(default=None, min_length=10, max_length=5000)
    observacoes: str | None = None
    data_vistoria: datetime | None = None
    data_validade: date | None = None

    @field_validator("parecer")
    @classmethod
    def _parecer(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v.strip() == "":
            raise ValueError("parecer não pode estar vazio.")
        return v


class VeiculoVistoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    id_veiculo: int
    id_auditor: int
    resultado: str
    parecer: str
    observacoes: str | None = None
    data_vistoria: datetime
    data_validade: date | None = None
    renovada_de: int | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None
    excluido: bool


class VeiculoVistoriaRenovarInput(BaseModel):
    """Renovação de vistoria — cria nova vistoria atrelada à anterior via renovada_de.
    data_vistoria preenchida automaticamente no momento da renovação (utcnow).
    renovada_de preenchido automaticamente apontando para vistoria anterior."""

    resultado: ResultadoAvaliacao
    parecer: str = Field(min_length=10, max_length=5000)
    observacoes: str | None = None
    data_validade: date | None = None

    @field_validator("parecer")
    @classmethod
    def _parecer(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("parecer não pode estar vazio.")
        return v


# ============================ Alvara ======================================
class AlvaraCreate(BaseModel):
    """Criação de alvará — número único por tenant, ao menos um de empresa/permissionário."""

    numero_alvara: str = Field(min_length=1, max_length=40)
    data_inicio: date | None = None
    data_validade: date | None = None
    tipo_servico: str = Field(min_length=1, max_length=30)
    observacoes: str | None = None
    id_empresa: int | None = None
    id_permissionario: int | None = None

    @model_validator(mode="after")
    def _at_least_one_vinculo(self) -> "AlvaraCreate":
        if not self.id_empresa and not self.id_permissionario:
            raise ValueError("Alvará deve estar vinculado a empresa ou permissionário.")
        return self

    @model_validator(mode="after")
    def _datas_consistentes(self) -> "AlvaraCreate":
        if self.data_inicio and self.data_validade and self.data_inicio > self.data_validade:
            raise ValueError("data_inicio não pode ser posterior a data_validade.")
        return self


class AlvaraUpdate(BaseModel):
    """Atualização de alvará — todos campos opcionais."""

    numero_alvara: str | None = Field(default=None, min_length=1, max_length=40)
    data_inicio: date | None = None
    data_validade: date | None = None
    tipo_servico: str | None = Field(default=None, min_length=1, max_length=30)
    observacoes: str | None = None
    id_empresa: int | None = None
    id_permissionario: int | None = None

    @model_validator(mode="after")
    def _datas_consistentes(self) -> "AlvaraUpdate":
        if self.data_inicio and self.data_validade and self.data_inicio > self.data_validade:
            raise ValueError("data_inicio não pode ser posterior a data_validade.")
        return self


class AlvaraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    id_empresa: int | None
    id_permissionario: int | None
    numero_alvara: str
    data_inicio: date | None
    data_validade: date | None
    tipo_servico: str
    observacoes: str | None
    renovado_de: int | None = None
    criado_em: datetime
    atualizado_em: datetime | None
    excluido: bool


class AlvaraRenovarInput(BaseModel):
    """Renovação de alvará — cria novo alvará atrelado ao anterior via renovado_de.
    Mantém empresa/permissionário do original, permite atualizar datas e observacões."""

    data_inicio: date | None = None
    data_validade: date | None = None
    observacoes: str | None = None

    @model_validator(mode="after")
    def _datas_consistentes(self) -> "AlvaraRenovarInput":
        if self.data_inicio and self.data_validade and self.data_inicio > self.data_validade:
            raise ValueError("data_inicio não pode ser posterior a data_validade.")
        return self


# ============================ AlvaraDocumento ===============================
class AlvaraDocumentoCreate(BaseModel):
    """Criação de documento de alvará — tipo obrigatório, arquivo (path/filename)."""

    tipo_documento: str = Field(min_length=1, max_length=30)
    arquivo: str = Field(min_length=1, max_length=255)
    observacoes: str | None = None


class AlvaraDocumentoUpdate(BaseModel):
    """Atualização de documento — todos campos opcionais."""

    tipo_documento: str | None = Field(default=None, min_length=1, max_length=30)
    arquivo: str | None = Field(default=None, min_length=1, max_length=255)
    observacoes: str | None = None


class AlvaraDocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    id_alvara: int
    tipo_documento: str
    arquivo: str
    observacoes: str | None
    criado_em: datetime
    atualizado_em: datetime | None
    excluido: bool


# ============================ AlvaraResponsavel =============================
class AlvaraResponsavelCreate(BaseModel):
    """Adição de responsável a um alvará — usuário obrigatório, cargo opcional."""

    id_usuario: int
    cargo_funcao: str | None = Field(default=None, max_length=100)


class AlvaraResponsavelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    id_alvara: int
    id_usuario: int
    cargo_funcao: str | None
    criado_em: datetime
    atualizado_em: datetime | None
    excluido: bool


# ============================ AlvaraVeiculo (P4) ============================
class AlvaraVeiculoCreate(BaseModel):
    """Vinculação de veículo a um alvará — id_veiculo obrigatório."""

    id_veiculo: int


class AlvaraVeiculoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    id_alvara: int
    id_veiculo: int
    data_vinculo: datetime
    criado_em: datetime
    atualizado_em: datetime | None


# ============================ AlvaraAuditoria (P4) ============================
class AlvaraAuditoriaItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    acao: str
    dados_antigos: dict | None
    dados_novos: dict | None
    id_usuario: int | None
    criado_em: datetime


class AlvaraAuditoriaListResponse(BaseModel):
    """Resposta paginada de auditoria."""

    eventos: list[AlvaraAuditoriaItem]
    total: int | None = None  # Para UI opcional


# ============================ Relatório (P4.3) ================================
class AlvaraRelatorioItem(BaseModel):
    """Item de alvará com KPIs para relatório."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    numero_alvara: str
    tipo_servico: str
    id_permissionario: int | None
    id_empresa: int | None
    data_inicio: date | None
    data_validade: date | None
    criado_em: datetime
    # KPIs calculados
    status: Literal["ativo", "vencido", "a_renovar_30d", "indefinido"]
    dias_para_vencimento: int | None


class AlvaraRelatorioListResponse(BaseModel):
    """Resposta paginada de relatório de alvarás."""

    alvaras: list[AlvaraRelatorioItem]
    total: int
    limit: int
    offset: int


class AlvaraKPIsResponse(BaseModel):
    """Agregação de KPIs de alvarás."""

    total_alvaras: int
    ativos: int
    vencidos: int
    a_renovar_30d: int
    indefinidos: int


# ==================== Recadastramento (P5.1) ==============================
CriterioEscalonamento = Literal["final_documento", "sem_escalonamento"]
CicloSituacao = Literal["rascunho", "aberto", "encerrado"]


class RecadastramentoCicloCreate(BaseModel):
    """Abertura de um ciclo de recadastramento.

    `situacao` NÃO entra: ciclo nasce em `rascunho` e muda por ato próprio.
    """

    nome: str = Field(min_length=1, max_length=120)
    data_inicio: date
    data_fim: date
    criterio_escalonamento: CriterioEscalonamento = "final_documento"
    observacoes: str | None = None

    @model_validator(mode="after")
    def _janela_consistente(self) -> "RecadastramentoCicloCreate":
        if self.data_inicio > self.data_fim:
            raise ValueError("data_inicio não pode ser posterior a data_fim.")
        return self


class RecadastramentoCicloUpdate(BaseModel):
    """Atualização de ciclo — todos os campos opcionais.

    A janela só é validada aqui quando as DUAS datas vêm no payload; o caso de
    uma só (que precisa confrontar o valor já gravado) é do serviço.
    """

    nome: str | None = Field(default=None, min_length=1, max_length=120)
    data_inicio: date | None = None
    data_fim: date | None = None
    criterio_escalonamento: CriterioEscalonamento | None = None
    situacao: CicloSituacao | None = None
    observacoes: str | None = None

    @model_validator(mode="after")
    def _janela_consistente(self) -> "RecadastramentoCicloUpdate":
        if self.data_inicio and self.data_fim and self.data_inicio > self.data_fim:
            raise ValueError("data_inicio não pode ser posterior a data_fim.")
        return self


class RecadastramentoAjustePrazo(BaseModel):
    """Ajuste individual de prazo.

    A justificativa é obrigatória e não aceita espaço em branco: sem ela o
    ajuste vira favor invisível. `min_length` no campo não basta — `"   "` tem
    três caracteres.
    """

    prazo: date
    justificativa: str = Field(min_length=5, max_length=2000)

    @field_validator("justificativa")
    @classmethod
    def _justificativa_nao_vazia(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("justificativa não pode estar vazia.")
        return v


class RecadastramentoCicloOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    data_inicio: date
    data_fim: date
    criterio_escalonamento: str
    situacao: str
    observacoes: str | None
    criado_em: datetime
    atualizado_em: datetime | None


class RecadastramentoConvocacaoOut(BaseModel):
    """Convocado de um ciclo, com o nome do regulado já resolvido.

    `nome_regulado` e `tipo_regulado` são derivados no serviço: o nome mora em
    `permissionario.nome` ou em `empresa.razao_social` conforme o vínculo, e
    resolver isso na tela custaria uma consulta por linha.
    """

    id: int
    id_ciclo: int
    id_permissionario: int | None
    id_empresa: int | None
    tipo_regulado: Literal["permissionario", "empresa"]
    nome_regulado: str
    prazo: date
    prazo_original: date
    ajustado: bool
    ajuste_justificativa: str | None
    ajustado_por: int | None
    ajustado_em: datetime | None
    situacao: str
    criado_em: datetime


class RecadastramentoGeracaoOut(BaseModel):
    """Resultado da geração.

    `0/0` diz ao operador que não há regulado ativo — informação diferente de
    "funcionou", e por isso os dois números vão na resposta.
    """

    criadas: int
    ja_existentes: int


# ================= Recadastramento — atendimento (P5.2) ====================
AplicaA = Literal["permissionario", "empresa", "ambos"]
TipoDecisao = Literal["deferimento", "indeferimento", "reabertura"]


class RecadastramentoItemCreate(BaseModel):
    """Item do catálogo de documentos exigidos."""

    descricao: str = Field(min_length=1, max_length=200)
    aplica_a: AplicaA = "ambos"
    obrigatorio: bool = True
    ordem: int = 0
    ativo: bool = True


class RecadastramentoItemUpdate(BaseModel):
    """Atualização de item — todos os campos opcionais.

    Todo campo opcional significa que `{"descricao": null}` CHEGA. Em coluna
    NOT NULL isso vira `IntegrityError`, ou seja, HTTP 500 num erro de entrada.
    O descarte do nulo explícito é do serviço (`NAO_ANULAVEIS_DO_ITEM`), como
    em `atualizar_ciclo`.
    """

    descricao: str | None = Field(default=None, min_length=1, max_length=200)
    aplica_a: AplicaA | None = None
    obrigatorio: bool | None = None
    ordem: int | None = None
    ativo: bool | None = None


class RecadastramentoItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    descricao: str
    aplica_a: str
    obrigatorio: bool
    ordem: int
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime | None


class RecadastramentoMarcarInput(BaseModel):
    """Marcação de um item numa convocação. Sempre INSERE — nunca atualiza."""

    marcado: bool
    observacao: str | None = Field(default=None, max_length=255)


class RecadastramentoChecklistItemOut(BaseModel):
    """Item aplicável a uma convocação, com o estado corrente já resolvido.

    `marcado` vem da marca MAIS RECENTE do par (convocação, item); `None`
    significa que o item nunca foi tocado — diferente de marcado como `false`,
    que é uma decisão registrada de que o documento não está em ordem.
    """

    id_item: int
    descricao: str
    aplica_a: str
    obrigatorio: bool
    ordem: int
    marcado: bool | None
    observacao: str | None
    marcado_por: int | None
    marcado_em: datetime | None


class RecadastramentoVeiculoPendenteOut(BaseModel):
    id_veiculo: int
    placa: str
    motivo: str


class RecadastramentoVistoriasOut(BaseModel):
    """Três campos, e não um booleano.

    `satisfeita=true` com `total_veiculos_ativos=0` é a assunção A1 da spec:
    regulado sem veículo passa por vacuidade. A tela precisa distinguir isso de
    "todos em dia", senão cadastro incompleto vira selo verde.
    """

    satisfeita: bool
    total_veiculos_ativos: int
    pendentes: list[RecadastramentoVeiculoPendenteOut]


class RecadastramentoSituacaoAtendimentoOut(BaseModel):
    """O que a tela precisa para desenhar a ficha inteira e explicar o botão."""

    id_convocacao: int
    situacao: str
    prazo: date
    em_atraso: bool
    tipo_regulado: str
    nome_regulado: str
    itens: list[RecadastramentoChecklistItemOut]
    itens_obrigatorios_pendentes: list[str]
    vistorias: RecadastramentoVistoriasOut
    pode_deferir: bool


class RecadastramentoDecisaoInput(BaseModel):
    """Parecer obrigatório. `min_length` no campo não basta: `"   "` tem três
    caracteres e não é parecer nenhum."""

    parecer: str = Field(min_length=5, max_length=5000)

    @field_validator("parecer")
    @classmethod
    def _parecer_nao_vazio(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("parecer não pode estar vazio.")
        return v


class RecadastramentoDecisaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_convocacao: int
    tipo: str
    parecer: str
    id_usuario: int
    criado_em: datetime


# ------------------------------------------------------- P5.3 — faltosos


class RecadastramentoFaltosoOut(BaseModel):
    """Uma linha do relatório de faltosos.

    `dias_atraso` vem calculado do servidor, e não da tela: o atraso é
    derivado de `prazo < hoje`, e "hoje" do navegador pode não ser o do
    servidor — fuso e relógio errado do posto de atendimento produziriam
    contagens diferentes para o mesmo registro.
    """

    id: int
    tipo_regulado: str
    nome_regulado: str
    documento: str
    prazo: date
    dias_atraso: int
    situacao: str
    ultima_notificacao: datetime | None = None


class RecadastramentoFaltososKpis(BaseModel):
    convocados: int
    atendidos: int
    em_atraso: int
    suspensos: int


class RecadastramentoCicloResumoOut(BaseModel):
    id: int
    nome: str
    situacao: str


class RecadastramentoFaltososOut(BaseModel):
    ciclo: RecadastramentoCicloResumoOut
    kpis: RecadastramentoFaltososKpis
    itens: list[RecadastramentoFaltosoOut]
    total: int


class RecadastramentoNotificarInput(BaseModel):
    """Ids das convocações a notificar. Explícito, e não "todos os faltosos do
    ciclo": disparo em massa sem seleção é o tipo de ação que o operador não
    consegue conferir antes de confirmar."""

    convocacao_ids: list[int] = Field(min_length=1, max_length=500)


class RecadastramentoNotificacaoResultadoOut(BaseModel):
    """`sem_contato` NÃO é erro — `email` e `telefone` são anuláveis nos dois
    modelos de regulado, então cadastro incompleto é caso comum. A tela mostra
    a contagem dos dois resultados."""

    id_convocacao: int
    nome_regulado: str
    resultado: str
    canais: list[str]


# ------------------------------------------------------------------ P6: pontos


class PontoBase(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    codigo: str | None = Field(default=None, max_length=40)
    # `TipoServico`, o mesmo Literal de permissionário, empresa e veículo. A
    # coluna no banco é `String(30)` sem CHECK, também como as outras — a
    # restrição vive na borda, e o vocabulário já tem `outro` como escape.
    tipo_servico: TipoServico
    logradouro: str | None = Field(default=None, max_length=200)
    numero: str | None = Field(default=None, max_length=20)
    complemento: str | None = Field(default=None, max_length=100)
    bairro: str | None = Field(default=None, max_length=100)
    cep: str | None = Field(default=None, max_length=9)
    vagas_total: int = Field(ge=1)
    situacao: Literal["ativo", "inativo"] = "ativo"
    observacoes: str | None = None


class PontoCreate(PontoBase):
    pass


class PontoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    codigo: str | None = Field(default=None, max_length=40)
    tipo_servico: TipoServico | None = None
    logradouro: str | None = Field(default=None, max_length=200)
    numero: str | None = Field(default=None, max_length=20)
    complemento: str | None = Field(default=None, max_length=100)
    bairro: str | None = Field(default=None, max_length=100)
    cep: str | None = Field(default=None, max_length=9)
    vagas_total: int | None = Field(default=None, ge=1)
    situacao: Literal["ativo", "inativo"] | None = None
    observacoes: str | None = None


class PontoOut(PontoBase):
    id: int
    # Desnormalizado na listagem: é o número que o gestor procura, e resolvê-lo
    # por linha na tela custaria uma requisição por ponto.
    vagas_ocupadas: int = 0
    criado_em: datetime
    atualizado_em: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PontoOcupacaoOut(BaseModel):
    id: int
    id_ponto: int
    numero_vaga: int
    id_permissionario: int
    nome_permissionario: str | None = None
    cpf_permissionario: str | None = None
    desde: date
    ate: date | None = None
    motivo_liberacao: str | None = None
    observacoes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PontoVagaOut(BaseModel):
    """Uma vaga do mapa. `ocupacao` nula = vaga livre.

    O mapa devolve SEMPRE as `vagas_total` vagas, livres inclusive — a tela
    precisa desenhar a grade inteira, e deduzir os buracos no cliente é como
    "vaga 7 sumiu" vira defeito difícil de ver.
    """

    numero_vaga: int
    ocupacao: PontoOcupacaoOut | None = None


class PontoMapaOut(BaseModel):
    id_ponto: int
    nome: str
    situacao: str
    vagas_total: int
    vagas_ocupadas: int
    vagas: list[PontoVagaOut]


class PontoOcuparInput(BaseModel):
    numero_vaga: int = Field(ge=1)
    id_permissionario: int
    desde: date | None = None
    observacoes: str | None = None


class PontoLiberarInput(BaseModel):
    ate: date | None = None
    motivo_liberacao: str | None = Field(default=None, max_length=30)


# ------------------------------------------------------------- P6b: linhas

LinhaSituacao = Literal["ativa", "inativa"]


class LinhaBase(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    codigo: str | None = Field(default=None, max_length=40)
    tipo_servico: TipoServico
    id_empresa: int | None = None
    id_permissionario: int | None = None
    origem: str = Field(min_length=1, max_length=150)
    destino: str = Field(min_length=1, max_length=150)
    situacao: LinhaSituacao = "ativa"
    observacoes: str | None = None

    @model_validator(mode="after")
    def _tem_operador(self) -> "LinhaBase":
        # Espelha o CHECK ck_linha_tem_operador: 422 na borda, o banco é a rede.
        if self.id_empresa is None and self.id_permissionario is None:
            raise ValueError("Informe a empresa ou o permissionário responsável pela linha.")
        return self


class LinhaCreate(LinhaBase):
    pass


class LinhaUpdate(BaseModel):
    # Parcial: o "ao menos um operador" do estado final é conferido no serviço,
    # porque só lá o payload encontra a linha existente.
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    codigo: str | None = Field(default=None, max_length=40)
    tipo_servico: TipoServico | None = None
    id_empresa: int | None = None
    id_permissionario: int | None = None
    origem: str | None = Field(default=None, min_length=1, max_length=150)
    destino: str | None = Field(default=None, min_length=1, max_length=150)
    situacao: LinhaSituacao | None = None
    observacoes: str | None = None


class LinhaParadaOut(BaseModel):
    id: int
    ordem: int
    descricao: str
    observacoes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class LinhaHorarioOut(BaseModel):
    id: int
    dia_semana: int
    partida: time

    model_config = ConfigDict(from_attributes=True)


class LinhaOut(LinhaBase):
    id: int
    # Desnormalizados para a listagem (nome do operador, tamanho da grade).
    operador_nome: str | None = None
    total_horarios: int = 0
    criado_em: datetime
    atualizado_em: datetime | None = None
    paradas: list[LinhaParadaOut] = []
    horarios: list[LinhaHorarioOut] = []

    model_config = ConfigDict(from_attributes=True)


class LinhaParadaCreate(BaseModel):
    descricao: str = Field(min_length=1, max_length=200)
    observacoes: str | None = None


class LinhaParadaUpdate(BaseModel):
    descricao: str | None = Field(default=None, min_length=1, max_length=200)
    observacoes: str | None = None


class LinhaParadasOrdemInput(BaseModel):
    # A lista COMPLETA de ids na nova ordem — id faltando ou sobrando é 422
    # no serviço (payload não bate com o estado: cliente desatualizado).
    ids: list[int] = Field(min_length=1)


class LinhaHorarioCreate(BaseModel):
    dia_semana: int = Field(ge=0, le=6)
    partida: time


# ------------------------------------------------------------- P7: ocorrências

OcorrenciaOrigem = Literal["fiscalizacao", "denuncia", "outro"]
OcorrenciaSituacao = Literal[
    "registrada", "em_apuracao", "procedente", "improcedente", "arquivada"
]


class OcorrenciaTipoCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    descricao: str | None = None
    ativo: bool = True


class OcorrenciaTipoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    descricao: str | None = None
    ativo: bool | None = None


class OcorrenciaTipoOut(BaseModel):
    id: int
    nome: str
    descricao: str | None = None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class OcorrenciaCreate(BaseModel):
    id_tipo: int
    origem: OcorrenciaOrigem
    data_fato: date
    descricao: str = Field(min_length=1)
    id_permissionario: int | None = None
    id_empresa: int | None = None
    id_veiculo: int | None = None
    referencia_alvo: str | None = Field(default=None, max_length=200)
    observacoes: str | None = None


class OcorrenciaAndamentoOut(BaseModel):
    id: int
    ato: str
    parecer: str | None = None
    id_usuario: int | None = None
    usuario_nome: str | None = None
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class OcorrenciaOut(OcorrenciaCreate):
    id: int
    situacao: OcorrenciaSituacao
    tipo_nome: str | None = None
    alvo_resumo: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None
    andamentos: list[OcorrenciaAndamentoOut] = []

    model_config = ConfigDict(from_attributes=True)


class OcorrenciaAnotarInput(BaseModel):
    parecer: str = Field(min_length=1)


class OcorrenciaVincularInput(BaseModel):
    id_permissionario: int | None = None
    id_empresa: int | None = None
    id_veiculo: int | None = None


class OcorrenciaDecidirInput(BaseModel):
    resultado: Literal["procedente", "improcedente", "arquivada"]
    parecer: str = Field(min_length=1)

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------- P7.2: realm cidadão

class DenunciaCidadaoCreate(BaseModel):
    id_tipo: int
    descricao: str = Field(min_length=1)
    referencia_alvo: str | None = Field(default=None, max_length=200)
    data_fato: date


class DenunciaCidadaoOut(BaseModel):
    """Schema FECHADO — não herda de OcorrenciaOut. O contorno do que o
    cidadão vê é contrato: nada de trilha, parecer ou alvo formal aqui."""

    id: int
    tipo_nome: str | None = None
    descricao: str
    referencia_alvo: str | None = None
    situacao: OcorrenciaSituacao
    data_fato: date
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)
