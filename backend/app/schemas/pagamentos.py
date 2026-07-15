"""Schemas dos cadastros de Pagamentos. `*Update` são whitelist (nunca aceitam
tenant_id/id/excluido/timestamps). FornecedorOut mascara dados bancários; a revelação
decifrada é um schema/endpoint separado e auditado."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TipoPessoa = Literal["FISICA", "JURIDICA"]
SituacaoCadastral = Literal["REGULAR", "PENDENTE", "IRREGULAR"]
CriticidadeLit = Literal["URGENTE", "ALTA", "MEDIA", "BAIXA"]
GrupoDespesaLit = Literal["PESSOAL", "CUSTEIO", "INVESTIMENTO", "DIVIDA", "OUTRAS"]


# ---------- fornecedor ----------
class DadosBancarios(BaseModel):
    banco: str | None = Field(default=None, max_length=200)
    agencia: str | None = Field(default=None, max_length=200)
    conta: str | None = Field(default=None, max_length=200)
    chave_pix: str | None = Field(default=None, max_length=200)


class FornecedorCreate(BaseModel):
    tipo_pessoa: TipoPessoa
    cnpj_cpf: str = Field(min_length=1, max_length=18)
    nome: str = Field(min_length=1, max_length=200)
    situacao_cadastral: SituacaoCadastral = "REGULAR"
    motivo_pendencia: str | None = Field(default=None, max_length=255)
    dados_bancarios: DadosBancarios | None = None


class FornecedorUpdate(BaseModel):
    tipo_pessoa: TipoPessoa | None = None
    cnpj_cpf: str | None = Field(default=None, max_length=18)
    nome: str | None = Field(default=None, max_length=200)
    situacao_cadastral: SituacaoCadastral | None = None
    motivo_pendencia: str | None = Field(default=None, max_length=255)
    dados_bancarios: DadosBancarios | None = None


class FornecedorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo_pessoa: TipoPessoa
    cnpj_cpf: str
    nome: str
    situacao_cadastral: SituacaoCadastral
    motivo_pendencia: str | None
    tem_dados_bancarios: bool  # true se qualquer *_cif != null (preenchido no serviço)
    criado_em: datetime
    atualizado_em: datetime | None


class FornecedorDadosBancariosOut(DadosBancarios):
    pass


class FornecedorSituacaoHistoricoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    situacao: SituacaoCadastral
    motivo: str | None
    id_usuario: int | None
    criado_em: datetime


# ---------- natureza_despesa ----------
class NaturezaCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    descricao: str = Field(min_length=1, max_length=150)
    criticidade_padrao: CriticidadeLit = "MEDIA"
    ativa: bool = True


class NaturezaUpdate(BaseModel):
    codigo: str | None = Field(default=None, max_length=20)
    descricao: str | None = Field(default=None, max_length=150)
    criticidade_padrao: CriticidadeLit | None = None
    ativa: bool | None = None


class NaturezaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; codigo: str; descricao: str; criticidade_padrao: CriticidadeLit; ativa: bool
    criado_em: datetime; atualizado_em: datetime | None


# ---------- fonte_recursos ----------
class FonteCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    descricao: str = Field(min_length=1, max_length=200)
    grupos_despesa_permitidos: list[GrupoDespesaLit] = Field(default_factory=list)


class FonteUpdate(BaseModel):
    codigo: str | None = Field(default=None, max_length=20)
    descricao: str | None = Field(default=None, max_length=200)
    grupos_despesa_permitidos: list[GrupoDespesaLit] | None = None


class FonteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; codigo: str; descricao: str; grupos_despesa_permitidos: list[str]
    criado_em: datetime; atualizado_em: datetime | None


# ---------- conta_bancaria ----------
class ContaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    banco: str = Field(min_length=1, max_length=100)
    agencia: str = Field(min_length=1, max_length=20)
    conta: str = Field(min_length=1, max_length=30)
    id_fonte_recursos: int
    grupo_despesa: GrupoDespesaLit
    saldo_minimo_alerta: Decimal = Decimal("0")
    saldo_inicial: Decimal = Decimal("0")
    ativa: bool = True


class ContaUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=150)
    banco: str | None = Field(default=None, max_length=100)
    agencia: str | None = Field(default=None, max_length=20)
    conta: str | None = Field(default=None, max_length=30)
    id_fonte_recursos: int | None = None
    grupo_despesa: GrupoDespesaLit | None = None
    saldo_minimo_alerta: Decimal | None = None
    saldo_inicial: Decimal | None = None
    ativa: bool | None = None


class ContaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; nome: str; banco: str; agencia: str; conta: str
    id_fonte_recursos: int; grupo_despesa: GrupoDespesaLit
    saldo_minimo_alerta: Decimal; saldo_inicial: Decimal; ativa: bool
    criado_em: datetime; atualizado_em: datetime | None


# ---------- contrato ----------
class ContratoCreate(BaseModel):
    numero: str = Field(min_length=1, max_length=50)
    id_fornecedor: int
    id_unidade: int
    objeto: str = Field(min_length=1, max_length=255)
    vigencia_inicio: date
    vigencia_fim: date
    valor_total: Decimal


class ContratoUpdate(BaseModel):
    numero: str | None = Field(default=None, max_length=50)
    id_fornecedor: int | None = None
    id_unidade: int | None = None
    objeto: str | None = Field(default=None, max_length=255)
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    valor_total: Decimal | None = None


class ContratoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; numero: str; id_fornecedor: int; id_unidade: int; objeto: str
    vigencia_inicio: date; vigencia_fim: date; valor_total: Decimal
    criado_em: datetime; atualizado_em: datetime | None


# ---------- alcada ----------
class AlcadaCreate(BaseModel):
    id_usuario: int
    id_natureza: int | None = None
    valor_maximo: Decimal


class AlcadaUpdate(BaseModel):
    id_usuario: int | None = None
    id_natureza: int | None = None
    valor_maximo: Decimal | None = None


class AlcadaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; id_usuario: int; id_natureza: int | None; valor_maximo: Decimal
    criado_em: datetime; atualizado_em: datetime | None


# ---------- movimentacao_conta (caixa) ----------
TipoMov = Literal["ENTRADA", "SAIDA"]
OrigemMov = Literal["APORTE", "RECEITA", "AJUSTE", "PAGAMENTO", "ESTORNO"]


class MovimentacaoCreate(BaseModel):
    id_conta: int
    tipo: TipoMov
    valor: Decimal = Field(gt=0)
    origem: OrigemMov
    data: date
    descricao: str | None = Field(default=None, max_length=255)


class MovimentacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; id_conta: int; tipo: TipoMov; valor: Decimal; origem: OrigemMov
    data: date; descricao: str | None; id_usuario: int | None; criado_em: datetime


class SaldoConta(BaseModel):
    id_conta: int; saldo_inicial: Decimal; total_entradas: Decimal
    total_saidas: Decimal; saldo_atual: Decimal


class ContaSaldoPainel(BaseModel):
    id_conta: int; nome: str; banco: str; grupo_despesa: str
    saldo_inicial: Decimal; total_entradas: Decimal; total_saidas: Decimal
    saldo_atual: Decimal; saldo_minimo_alerta: Decimal; abaixo_minimo: bool
