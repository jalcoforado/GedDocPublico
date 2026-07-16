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
    comprometido: Decimal = Decimal("0"); disponivel: Decimal = Decimal("0")


class ContaSaldoPainel(BaseModel):
    id_conta: int; nome: str; banco: str; grupo_despesa: str
    saldo_inicial: Decimal; total_entradas: Decimal; total_saidas: Decimal
    saldo_atual: Decimal; saldo_minimo_alerta: Decimal; abaixo_minimo: bool
    comprometido: Decimal = Decimal("0"); disponivel: Decimal = Decimal("0")


# ---------- débito / parcelas / ordem de pagamento (R2) ----------
StatusDebito = Literal["RASCUNHO", "AGUARDANDO_APROVACAO", "APROVADO", "AUTORIZADO",
                       "PAGO_PARCIAL", "PAGO", "REJEITADO", "CANCELADO"]
StatusParcela = Literal["A_PAGAR", "PAGA", "CANCELADA"]
FormaPagamento = Literal["PIX", "TED", "BOLETO", "DINHEIRO", "OUTRO"]


class ParcelaCreate(BaseModel):
    numero: int = Field(ge=1)
    valor: Decimal = Field(gt=0)
    vencimento: date


class DebitoCreate(BaseModel):
    id_fornecedor: int
    id_natureza: int
    id_conta: int
    id_contrato: int | None = None
    valor_total: Decimal = Field(gt=0)
    competencia: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    numero_ne: str | None = Field(default=None, max_length=30)
    numero_nf: str | None = Field(default=None, max_length=40)
    criticidade: CriticidadeLit = "MEDIA"
    urgente: bool = False
    justificativa_urgencia: str | None = Field(default=None, max_length=255)
    descricao: str = Field(min_length=1, max_length=255)
    parcelas: list[ParcelaCreate] = Field(min_length=1)


class DebitoUpdate(BaseModel):
    id_fornecedor: int | None = None
    id_natureza: int | None = None
    id_conta: int | None = None
    id_contrato: int | None = None
    valor_total: Decimal | None = Field(default=None, gt=0)
    competencia: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    numero_ne: str | None = Field(default=None, max_length=30)
    numero_nf: str | None = Field(default=None, max_length=40)
    criticidade: CriticidadeLit | None = None
    urgente: bool | None = None
    justificativa_urgencia: str | None = Field(default=None, max_length=255)
    descricao: str | None = Field(default=None, min_length=1, max_length=255)
    parcelas: list[ParcelaCreate] | None = Field(default=None, min_length=1)


class ParcelaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; id_debito: int; numero: int; valor: Decimal; vencimento: date
    status: StatusParcela; data_pagamento: date | None; forma_pagamento: FormaPagamento | None
    id_movimentacao: int | None


class DebitoOut(BaseModel):
    id: int; id_fornecedor: int; nome_fornecedor: str; id_natureza: int; id_conta: int
    id_contrato: int | None; valor_total: Decimal; competencia: str
    numero_ne: str | None; numero_nf: str | None; criticidade: CriticidadeLit
    urgente: bool; justificativa_urgencia: str | None; descricao: str
    status: StatusDebito; id_usuario_solicitante: int
    criado_em: datetime; atualizado_em: datetime | None


class DebitoHistoricoOut(BaseModel):
    id: int; acao: str; status_anterior: str | None; status_novo: str
    justificativa: str | None; id_usuario: int | None; nome_usuario: str | None
    criado_em: datetime


class DebitoDetalheOut(DebitoOut):
    parcelas: list[ParcelaOut]
    historico: list[DebitoHistoricoOut]


class JustificativaIn(BaseModel):
    justificativa: str = Field(min_length=1, max_length=255)


class AutorizarLoteIn(BaseModel):
    debito_ids: list[int] = Field(min_length=1)


class PagarParcelaIn(BaseModel):
    forma_pagamento: FormaPagamento
    data_pagamento: date | None = None


class OrdemPagamentoOut(BaseModel):
    id: int; numero: str; valor_total: Decimal; id_usuario_autorizador: int
    nome_autorizador: str | None; qtd_debitos: int; criado_em: datetime


class ParcelaFilaOut(BaseModel):
    id: int; id_debito: int; numero: int; valor: Decimal; vencimento: date
    nome_fornecedor: str; descricao_debito: str; vencida: bool


class MinhaFilaOut(BaseModel):
    solicitar: list[DebitoOut] | None = None    # meus RASCUNHO (inclui devolvidos)
    aprovar: list[DebitoOut] | None = None      # AGUARDANDO_APROVACAO
    autorizar: list[DebitoOut] | None = None    # APROVADO
    pagar: list[ParcelaFilaOut] | None = None   # A_PAGAR de AUTORIZADO/PAGO_PARCIAL


# ---------- dashboard financeiro ----------
class DashboardKpis(BaseModel):
    saldo_total: Decimal; disponivel_total: Decimal; comprometido_total: Decimal
    a_pagar_30d: Decimal; vencidas_qtd: int; vencidas_valor: Decimal
    pago_no_mes: Decimal; aguardando_aprovacao_qtd: int; aguardando_autorizacao_qtd: int


class FluxoMensalItem(BaseModel):
    mes: str  # 'YYYY-MM'
    entradas: Decimal; saidas: Decimal


class ComposicaoItem(BaseModel):
    codigo: str; descricao: str; valor: Decimal


class DebitoResumoItem(BaseModel):
    id: int; nome_fornecedor: str; descricao: str; valor_total: Decimal
    status: StatusDebito; competencia: str


class ParcelaAlertaItem(BaseModel):
    id: int; id_debito: int; nome_fornecedor: str; valor: Decimal
    vencimento: date; dias_atraso: int


class ContaAlertaItem(BaseModel):
    id_conta: int; nome: str; saldo_atual: Decimal; saldo_minimo_alerta: Decimal


class DashboardAlertas(BaseModel):
    parcelas_vencidas: list[ParcelaAlertaItem]
    parcelas_7dias: list[ParcelaAlertaItem]
    contas_abaixo_minimo: list[ContaAlertaItem]


class DashboardOut(BaseModel):
    kpis: DashboardKpis
    fluxo_mensal: list[FluxoMensalItem]
    por_natureza: list[ComposicaoItem]
    por_fonte: list[ComposicaoItem]
    maiores_debitos: list[DebitoResumoItem]
    alertas: DashboardAlertas
