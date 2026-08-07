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
SituacaoFonte = Literal["ATIVA", "SUSPENSA", "ENCERRADA"]
ModoMovimentacao = Literal["PAGA", "RECEBE", "TRANSFERE", "RESTRITA"]


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
    exercicio: int | None = None
    esfera_origem: str | None = Field(default=None, max_length=20)
    tipo_vinculacao: str | None = Field(default=None, max_length=30)
    situacao: SituacaoFonte = "ATIVA"
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None


class FonteUpdate(BaseModel):
    codigo: str | None = Field(default=None, max_length=20)
    descricao: str | None = Field(default=None, max_length=200)
    grupos_despesa_permitidos: list[GrupoDespesaLit] | None = None
    exercicio: int | None = None
    esfera_origem: str | None = Field(default=None, max_length=20)
    tipo_vinculacao: str | None = Field(default=None, max_length=30)
    situacao: SituacaoFonte | None = None
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None


class FonteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; codigo: str; descricao: str; grupos_despesa_permitidos: list[str]
    exercicio: int | None = None; esfera_origem: str | None = None
    tipo_vinculacao: str | None = None; situacao: SituacaoFonte = "ATIVA"
    vigencia_inicio: date | None = None; vigencia_fim: date | None = None
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
    digito: str | None = Field(default=None, max_length=5)
    tipo: str | None = Field(default=None, max_length=20)
    titularidade: str | None = Field(default=None, max_length=150)
    orgao_gestor: str | None = Field(default=None, max_length=150)
    finalidade: str | None = Field(default=None, max_length=255)
    data_abertura: date | None = None
    modo_movimentacao: ModoMovimentacao = "PAGA"


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
    digito: str | None = Field(default=None, max_length=5)
    tipo: str | None = Field(default=None, max_length=20)
    titularidade: str | None = Field(default=None, max_length=150)
    orgao_gestor: str | None = Field(default=None, max_length=150)
    finalidade: str | None = Field(default=None, max_length=255)
    data_abertura: date | None = None
    modo_movimentacao: ModoMovimentacao | None = None
    # RF-CTA-06: obrigatória ao trocar a fonte vinculada (gera trilha).
    justificativa_troca_fonte: str | None = Field(default=None, max_length=255)


class ContaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; nome: str; banco: str; agencia: str; conta: str
    id_fonte_recursos: int; grupo_despesa: GrupoDespesaLit
    saldo_minimo_alerta: Decimal; saldo_inicial: Decimal; ativa: bool
    digito: str | None = None; tipo: str | None = None; titularidade: str | None = None
    orgao_gestor: str | None = None; finalidade: str | None = None
    data_abertura: date | None = None; modo_movimentacao: ModoMovimentacao = "PAGA"
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
    id_unidade: int | None = None
    id_fonte: int | None = None
    tipo_despesa: GrupoDespesaLit | None = None


class AlcadaUpdate(BaseModel):
    id_usuario: int | None = None
    id_natureza: int | None = None
    valor_maximo: Decimal | None = None
    id_unidade: int | None = None
    id_fonte: int | None = None
    tipo_despesa: GrupoDespesaLit | None = None


class AlcadaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; id_usuario: int; id_natureza: int | None; valor_maximo: Decimal
    id_unidade: int | None = None; id_fonte: int | None = None
    tipo_despesa: GrupoDespesaLit | None = None
    criado_em: datetime; atualizado_em: datetime | None


# ---------- bloqueio_saldo (v2.0) ----------
class BloqueioSaldoCreate(BaseModel):
    id_conta: int
    valor: Decimal = Field(gt=0)
    motivo: str = Field(min_length=1, max_length=255)
    periodo_inicio: date
    periodo_fim: date | None = None


class BloqueioSaldoUpdate(BaseModel):
    valor: Decimal | None = Field(default=None, gt=0)
    motivo: str | None = Field(default=None, max_length=255)
    periodo_inicio: date | None = None
    periodo_fim: date | None = None
    ativo: bool | None = None


class BloqueioSaldoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; id_conta: int; valor: Decimal; motivo: str
    periodo_inicio: date; periodo_fim: date | None
    id_usuario_responsavel: int | None; ativo: bool
    criado_em: datetime; atualizado_em: datetime | None


# ---------- tag_prioridade (v2.0) ----------
class TagPrioridadeCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=50)
    cor: str | None = Field(default=None, max_length=20)
    ordem: int = 0
    ativa: bool = True


class TagPrioridadeUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=50)
    cor: str | None = Field(default=None, max_length=20)
    ordem: int | None = None
    ativa: bool | None = None


class TagPrioridadeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; nome: str; cor: str | None; ordem: int; ativa: bool
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
    # v2.0 — 5 saldos (spec seção 10). Até a Fase 3, conciliado := bancário.
    bloqueado: Decimal = Decimal("0")
    saldo_bancario: Decimal = Decimal("0")
    saldo_conciliado: Decimal = Decimal("0")
    disponivel_projetado: Decimal = Decimal("0")


class ContaSaldoPainel(BaseModel):
    id_conta: int; nome: str; banco: str; grupo_despesa: str
    saldo_inicial: Decimal; total_entradas: Decimal; total_saidas: Decimal
    saldo_atual: Decimal; saldo_minimo_alerta: Decimal; abaixo_minimo: bool
    comprometido: Decimal = Decimal("0"); disponivel: Decimal = Decimal("0")
    bloqueado: Decimal = Decimal("0")
    saldo_conciliado: Decimal = Decimal("0")
    disponivel_projetado: Decimal = Decimal("0")


# ---------- débito / parcelas / ordem de pagamento (R2) ----------
StatusDebito = Literal["RASCUNHO", "EM_VALIDACAO", "DEVOLVIDO", "VALIDADO",
                       "ENVIADO_SECRETARIO", "AGUARDANDO_AUTORIZACAO", "AUTORIZADO",
                       "ENVIADO_TESOURARIA", "EM_PROCESSAMENTO", "PAGO_PARCIAL", "PAGO",
                       "CONCILIADO", "REJEITADO", "SUSPENSO", "CANCELADO", "ESTORNADO"]
StatusParcela = Literal["A_PAGAR", "LIBERADA", "PAGA", "CANCELADA"]
FormaPagamento = Literal["PIX", "TED", "BOLETO", "DINHEIRO", "OUTRO"]

# --- as três dimensões (F1, spec §4.1) -------------------------------------
SituacaoTramitacao = Literal[
    "RASCUNHO", "AGUARDANDO_GESTOR", "AJUSTE_GESTOR", "AGUARDANDO_VALIDACAO",
    "AJUSTE_VALIDACAO", "AGUARDANDO_AUTORIDADE", "AJUSTE_AUTORIDADE",
    "AUTORIZADA", "REJEITADA_GESTOR", "INDEFERIDA_AUTORIDADE", "CANCELADA"]
SituacaoFila = Literal[
    "NAO_REGISTRADA", "REGISTRADA", "BLOQUEADA", "ELEGIVEL",
    "AGUARDANDO_DISPONIBILIDADE", "EXCECAO_AUTORIZADA", "CONCLUIDA", "RETIRADA"]
SituacaoPagamento = Literal[
    "NAO_INICIADA", "PROGRAMADA", "ENVIADA_BANCO", "EM_PROCESSAMENTO",
    "PAGA_PARCIAL", "PAGA", "FALHOU", "CANCELADA", "ESTORNADA"]
CategoriaContrato = Literal["BENS", "LOCACOES", "SERVICOS", "OBRAS"]
# ----------------------------------------------------------------------------


class ParcelaCreate(BaseModel):
    numero: int = Field(ge=1)
    valor: Decimal = Field(gt=0)
    vencimento: date


class DebitoCreate(BaseModel):
    id_fornecedor: int
    id_natureza: int
    id_fonte_recursos: int           # fonte do empenho (vinculante, v2.0)
    id_conta: int | None = None      # conta sugerida (não-vinculante)
    id_contrato: int | None = None
    id_unidade: int                  # unidade setorial de origem (F1)
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
    id_fonte_recursos: int | None = None
    id_conta: int | None = None
    id_contrato: int | None = None
    id_unidade: int | None = None
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
    data_liberacao: date | None = None
    id_usuario_liberacao: int | None = None
    data_prevista_pagamento: date | None = None


class DebitoOut(BaseModel):
    id: int; id_fornecedor: int; nome_fornecedor: str; id_natureza: int
    id_fonte_recursos: int; id_conta: int | None; id_conta_pagadora: int | None
    id_contrato: int | None; valor_total: Decimal; competencia: str
    numero_ne: str | None; numero_nf: str | None; criticidade: CriticidadeLit
    urgente: bool; justificativa_urgencia: str | None; descricao: str
    status: StatusDebito
    # `status` acima é legado e derivado; estes três são a verdade (F1).
    situacao_tramitacao: SituacaoTramitacao
    situacao_fila: SituacaoFila
    situacao_pagamento: SituacaoPagamento
    id_unidade: int
    versao: int = 1
    lock_version: int = 0
    id_gestor_decisor: int | None = None
    id_validador: int | None = None
    id_usuario_solicitante: int
    liquidacao_confirmada: bool = False; data_liquidacao: date | None = None
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


class LiquidacaoIn(BaseModel):
    data_liquidacao: date | None = None  # default = hoje no serviço


class GrupoAutorizacaoIn(BaseModel):
    """Autorização de um lote de débitos de uma fonte, pagos por uma conta escolhida."""
    id_fonte: int
    id_conta_pagadora: int
    debito_ids: list[int] = Field(min_length=1)
    # RN-15: exceção de saldo insuficiente — só quando expressamente autorizada e
    # justificada; a justificativa é gravada no histórico (auditável).
    permitir_saldo_insuficiente: bool = False
    justificativa_excecao: str | None = Field(default=None, max_length=255)


class DecisaoIn(BaseModel):
    """Payload das decisões do rito. `lock_version` é obrigatório: sem ele não
    há como distinguir 'decidiu sobre o estado que viu' de 'decidiu sobre um
    estado que outro usuário já mudou' (spec §6.3)."""
    lock_version: int


class DecisaoJustificadaIn(DecisaoIn):
    justificativa: str = Field(min_length=1, max_length=255)


class SolicitarAjusteIn(DecisaoJustificadaIn):
    """Solicitação de ajuste na despesa, a partir de qualquer etapa decisória."""
    etapa: str = Field(min_length=1, max_length=50)


class AutorizarLoteIn(BaseModel):
    grupos: list[GrupoAutorizacaoIn] = Field(min_length=1)


class PagarParcelaIn(BaseModel):
    forma_pagamento: FormaPagamento
    data_pagamento: date | None = None


class OrdemPagamentoOut(BaseModel):
    id: int; numero: str; valor_total: Decimal; id_usuario_autorizador: int
    nome_autorizador: str | None; qtd_debitos: int; criado_em: datetime
    id_conta_pagadora: int | None = None; valor_reservado: Decimal | None = None


class ParcelaFilaOut(BaseModel):
    id: int; id_debito: int; numero: int; valor: Decimal; vencimento: date
    nome_fornecedor: str; descricao_debito: str; vencida: bool


class MinhaFilaOut(BaseModel):
    solicitar: list[DebitoOut] | None = None    # meus RASCUNHO/DEVOLVIDO
    validar: list[DebitoOut] | None = None      # EM_VALIDACAO
    encaminhar: list[DebitoOut] | None = None   # VALIDADO
    autorizar: list[DebitoOut] | None = None    # ENVIADO_SECRETARIO/AGUARDANDO_AUTORIZACAO
    liberar: list[ParcelaFilaOut] | None = None  # A_PAGAR de autorizados/tesouraria
    pagar: list[ParcelaFilaOut] | None = None   # LIBERADA


# ---------- filas agregadas por conta (autorização / liberação / tesouraria) ----------
class DebitoFilaItem(BaseModel):
    id: int; nome_fornecedor: str; descricao: str; natureza_codigo: str
    natureza_descricao: str; competencia: str; urgente: bool
    aprovado_por: str | None; aprovado_em: datetime | None; valor_total: Decimal


class ParcelaFilaLibItem(BaseModel):
    id: int; id_debito: int; nome_fornecedor: str; descricao_debito: str
    numero: int; qtd_parcelas: int; valor: Decimal; vencimento: date
    vencida: bool; dias_atraso: int; op_numero: str | None; op_id: int | None


class ParcelaTesourariaItem(ParcelaFilaLibItem):
    data_liberacao: date | None; liberado_por: str | None
    data_prevista_pagamento: date | None
    data_pagamento: date | None = None


class GrupoConta(BaseModel):
    id_conta: int; nome_conta: str; disponivel: Decimal; abaixo_minimo: bool


class ContaElegivelOut(BaseModel):
    """Conta ativa de uma fonte, elegível como conta pagadora (v2.0 RF-AUT-02/05)."""
    id_conta: int; nome: str; banco: str; agencia: str; conta_mascarada: str
    saldo_atual: Decimal; disponivel: Decimal; abaixo_minimo: bool
    # RF-AUT-05: reservado, conciliado, disponível projetado e última atualização.
    reservado: Decimal = Decimal("0"); bloqueado: Decimal = Decimal("0")
    saldo_conciliado: Decimal = Decimal("0"); disponivel_projetado: Decimal = Decimal("0")
    atualizado_em: datetime | None = None


# ---------- conciliação bancária (Onda B / Fase 3) ----------
class ImportarExtratoIn(BaseModel):
    """Importa um extrato em CSV (data;historico;documento;favorecido;valor;tipo).
    tipo = CREDITO|DEBITO; data em DD/MM/AAAA ou AAAA-MM-DD; valor decimal."""
    id_conta: int
    nome_arquivo: str = Field(min_length=1, max_length=255)
    formato: Literal["CSV", "OFX", "XLSX", "CNAB"] = "CSV"
    conteudo: str = Field(min_length=1)


class ExtratoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; id_conta: int; nome_arquivo: str; formato: str
    periodo_inicio: date | None; periodo_fim: date | None
    status_processamento: str; qtd_lancamentos: int; importado_em: datetime


class LancamentoExtratoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; id_extrato: int; data: date; historico: str
    documento: str | None; favorecido: str | None; valor: Decimal
    tipo: str; conciliado: bool


class SugestaoBaixaOut(BaseModel):
    """Sugestão de baixa de um lançamento contra uma movimentação (RF-EXT-04/05)."""
    id_lancamento: int; lancamento_data: date; lancamento_historico: str; lancamento_valor: Decimal
    id_movimentacao: int; id_parcela: int | None; id_debito: int | None
    nome_fornecedor: str | None; movimentacao_data: date; movimentacao_valor: Decimal
    tipo_correspondencia: str  # EXATA | PROVAVEL


class ConciliarIn(BaseModel):
    id_lancamento: int
    id_movimentacao: int


class ConciliacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; id_lancamento: int; id_movimentacao: int | None
    id_parcela: int | None; tipo_correspondencia: str; criado_em: datetime


class ChecklistItemCreate(BaseModel):
    descricao: str = Field(min_length=1, max_length=200)
    obrigatorio: bool = True
    id_natureza: int | None = None
    ordem: int = 0


class ChecklistItemUpdate(BaseModel):
    descricao: str | None = Field(default=None, max_length=200)
    obrigatorio: bool | None = None
    id_natureza: int | None = None
    ordem: int | None = None
    ativo: bool | None = None


class ChecklistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; descricao: str; obrigatorio: bool; id_natureza: int | None; ordem: int; ativo: bool


class ChecklistDebitoItemOut(BaseModel):
    """Item do checklist aplicável a um débito, com seu estado atual (RF-VAL-01/06)."""
    id_checklist_item: int; descricao: str; obrigatorio: bool
    marcado: bool; observacao: str | None; atualizado_em: datetime | None


class MarcarChecklistIn(BaseModel):
    id_checklist_item: int
    marcado: bool
    observacao: str | None = Field(default=None, max_length=255)


class SimulacaoAutorizacaoIn(BaseModel):
    """Simulação do impacto de um pagamento numa conta (RF-PNL-05). Informe
    `debito_ids` (soma os valores) ou um `valor` direto."""
    id_conta: int
    debito_ids: list[int] | None = None
    valor: Decimal | None = None


class SimulacaoAutorizacaoOut(BaseModel):
    id_conta: int; valor_simulado: Decimal
    disponivel_antes: Decimal; disponivel_projetado_apos: Decimal; suficiente: bool


class FichaFonteContaItem(BaseModel):
    """Conta vinculada a uma fonte, com saldos e situação (RF-FON-06)."""
    id_conta: int; nome: str; banco: str; conta_mascarada: str
    ativa: bool; modo_movimentacao: str
    saldo_bancario: Decimal; saldo_conciliado: Decimal; reservado: Decimal
    bloqueado: Decimal; disponivel_projetado: Decimal; atualizado_em: datetime | None


class FichaFonteOut(BaseModel):
    """Ficha da fonte: dados + todas as contas vinculadas com saldos (RF-FON-06)."""
    id_fonte: int; codigo: str; descricao: str; situacao: str
    exercicio: int | None; tipo_vinculacao: str | None
    disponivel_total: Decimal
    contas: list[FichaFonteContaItem]


class FilaAutorizacaoFonteGrupo(BaseModel):
    """Débitos APROVADO de uma fonte + contas elegíveis para pagá-los (v2.0)."""
    id_fonte: int; codigo_fonte: str; descricao_fonte: str
    debitos: list[DebitoFilaItem]
    contas_elegiveis: list[ContaElegivelOut]


class FilaLiberacaoGrupo(GrupoConta):
    parcelas: list[ParcelaFilaLibItem]


class FilaTesourariaOut(BaseModel):
    liberadas: list[ParcelaTesourariaItem]      # ordenadas por data_prevista/vencimento
    pagas_recentes: list[ParcelaTesourariaItem]  # últimas 15, com data_pagamento no lugar


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


class ContaDesatualizadaItem(BaseModel):
    """Conta sem atualização de saldo no dia útil corrente (RF-SLD-06)."""
    id_conta: int; nome: str; atualizado_em: datetime | None


class DashboardAlertas(BaseModel):
    parcelas_vencidas: list[ParcelaAlertaItem]
    parcelas_7dias: list[ParcelaAlertaItem]
    contas_abaixo_minimo: list[ContaAlertaItem]
    contas_desatualizadas: list[ContaDesatualizadaItem] = []


class DashboardOut(BaseModel):
    kpis: DashboardKpis
    fluxo_mensal: list[FluxoMensalItem]
    por_natureza: list[ComposicaoItem]
    por_fonte: list[ComposicaoItem]
    maiores_debitos: list[DebitoResumoItem]
    alertas: DashboardAlertas
