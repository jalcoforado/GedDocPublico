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
