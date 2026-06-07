"""Schemas do módulo de Frota — Veículo (fundação).

`placa` é normalizada (upper, sem espaços/hífen) e validada nos formatos
brasileiro antigo (ABC1234) e Mercosul (ABC1D23). `VeiculoUpdate` é whitelist:
`tenant_id`/`id`/`excluido` nunca são aceitos no corpo.
"""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Situacao = Literal["disponivel", "em_uso", "manutencao", "inativo", "baixado"]
FormaPosse = Literal["proprio", "locado", "cedido", "convenio"]

# Placa BR antiga (ABC1234) ou Mercosul (ABC1D23), já em maiúsculas.
PLACA_PATTERN = r"^[A-Z]{3}[0-9][0-9A-Z][0-9]{2}$"


def _normalizar_placa(v: str) -> str:
    return v.replace("-", "").replace(" ", "").strip().upper()


class VeiculoBase(BaseModel):
    renavam: str | None = Field(default=None, max_length=20)
    chassi: str | None = Field(default=None, max_length=30)
    marca: str | None = Field(default=None, max_length=60)
    modelo: str | None = Field(default=None, max_length=80)
    ano_fabricacao: int | None = Field(default=None, ge=1900, le=2100)
    ano_modelo: int | None = Field(default=None, ge=1900, le=2100)
    cor: str | None = Field(default=None, max_length=30)
    tipo_veiculo: str | None = Field(default=None, max_length=40)
    tipo_combustivel: str | None = Field(default=None, max_length=20)
    situacao: Situacao = "disponivel"
    id_unidade_responsavel: int | None = None
    quilometragem_atual: int = Field(default=0, ge=0)
    data_aquisicao: date | None = None
    forma_posse: FormaPosse = "proprio"
    observacoes: str | None = None


class VeiculoCreate(VeiculoBase):
    placa: str

    # mode="before": normaliza (upper, sem espaço/hífen) ANTES das constraints,
    # senão uma placa digitada com hífen/espaço estouraria max_length.
    @field_validator("placa", mode="before")
    @classmethod
    def _placa(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        v = _normalizar_placa(v)
        import re

        if not re.match(PLACA_PATTERN, v):
            raise ValueError(
                "Placa inválida. Use o formato ABC1234 ou ABC1D23 (Mercosul)."
            )
        return v


class VeiculoUpdate(BaseModel):
    """Whitelist de edição — `tenant_id`/`id`/`excluido` nunca aceitos."""

    placa: str | None = None
    renavam: str | None = Field(default=None, max_length=20)
    chassi: str | None = Field(default=None, max_length=30)
    marca: str | None = Field(default=None, max_length=60)
    modelo: str | None = Field(default=None, max_length=80)
    ano_fabricacao: int | None = Field(default=None, ge=1900, le=2100)
    ano_modelo: int | None = Field(default=None, ge=1900, le=2100)
    cor: str | None = Field(default=None, max_length=30)
    tipo_veiculo: str | None = Field(default=None, max_length=40)
    tipo_combustivel: str | None = Field(default=None, max_length=20)
    situacao: Situacao | None = None
    id_unidade_responsavel: int | None = None
    quilometragem_atual: int | None = Field(default=None, ge=0)
    data_aquisicao: date | None = None
    forma_posse: FormaPosse | None = None
    observacoes: str | None = None

    @field_validator("placa", mode="before")
    @classmethod
    def _placa(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        v = _normalizar_placa(v)
        import re

        if not re.match(PLACA_PATTERN, v):
            raise ValueError(
                "Placa inválida. Use o formato ABC1234 ou ABC1D23 (Mercosul)."
            )
        return v


class VeiculoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    placa: str
    renavam: str | None = None
    chassi: str | None = None
    marca: str | None = None
    modelo: str | None = None
    ano_fabricacao: int | None = None
    ano_modelo: int | None = None
    cor: str | None = None
    tipo_veiculo: str | None = None
    tipo_combustivel: str | None = None
    situacao: str
    id_unidade_responsavel: int | None = None
    quilometragem_atual: int
    data_aquisicao: date | None = None
    forma_posse: str
    observacoes: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None


# --- Motorista / Condutor (PR Frota-2) --------------------------------------
CnhCategoria = Literal["A", "B", "AB", "C", "D", "E", "AC", "AD", "AE"]
MotoristaSituacao = Literal["ativo", "afastado", "inativo"]
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _so_digitos(v: str) -> str:
    import re

    return re.sub(r"\D", "", v)


class MotoristaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    cpf: str = Field(min_length=11, max_length=14)
    matricula: str | None = Field(default=None, max_length=40)
    cnh_numero: str = Field(min_length=9, max_length=14)
    cnh_categoria: CnhCategoria
    cnh_validade: date
    telefone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    id_unidade: int | None = None
    id_usuario: int | None = None
    situacao: MotoristaSituacao = "ativo"
    observacoes: str | None = None

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v: str) -> str:
        v = _so_digitos(v)
        if len(v) != 11:
            raise ValueError("CPF inválido. Deve conter 11 dígitos.")
        return v

    @field_validator("cnh_numero")
    @classmethod
    def _cnh(cls, v: str) -> str:
        v = _so_digitos(v)
        if len(v) != 11:
            raise ValueError("Número da CNH inválido. Deve conter 11 dígitos.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if v == "":
            return None
        import re

        if not re.match(EMAIL_PATTERN, v):
            raise ValueError("E-mail inválido.")
        return v


class MotoristaUpdate(BaseModel):
    """Whitelist de edição — `tenant_id`/`id`/`excluido` nunca aceitos."""

    nome: str | None = Field(default=None, min_length=1, max_length=150)
    cpf: str | None = Field(default=None, min_length=11, max_length=14)
    matricula: str | None = Field(default=None, max_length=40)
    cnh_numero: str | None = Field(default=None, min_length=9, max_length=14)
    cnh_categoria: CnhCategoria | None = None
    cnh_validade: date | None = None
    telefone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    id_unidade: int | None = None
    id_usuario: int | None = None
    situacao: MotoristaSituacao | None = None
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

    @field_validator("cnh_numero")
    @classmethod
    def _cnh(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = _so_digitos(v)
        if len(v) != 11:
            raise ValueError("Número da CNH inválido. Deve conter 11 dígitos.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if v == "":
            return None
        import re

        if not re.match(EMAIL_PATTERN, v):
            raise ValueError("E-mail inválido.")
        return v


class MotoristaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    cpf: str
    matricula: str | None = None
    cnh_numero: str
    cnh_categoria: str
    cnh_validade: date
    telefone: str | None = None
    email: str | None = None
    id_unidade: int | None = None
    id_usuario: int | None = None
    situacao: str
    observacoes: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None
