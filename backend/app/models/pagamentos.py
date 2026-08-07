"""Models do módulo de Pagamentos — cadastros (PAG-1). Schema `pagamentos`,
tenant-scoped com RLS (migration 0045). Dados bancários do fornecedor guardados
cifrados (colunas *_cif); a cifra/decifra é responsabilidade do serviço."""
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Criticidade(str, enum.Enum):
    URGENTE = "URGENTE"; ALTA = "ALTA"; MEDIA = "MEDIA"; BAIXA = "BAIXA"


class GrupoDespesa(str, enum.Enum):
    PESSOAL = "PESSOAL"; CUSTEIO = "CUSTEIO"; INVESTIMENTO = "INVESTIMENTO"
    DIVIDA = "DIVIDA"; OUTRAS = "OUTRAS"


class Fornecedor(Base):
    __tablename__ = "fornecedor"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    tipo_pessoa: Mapped[str] = mapped_column(String(10), nullable=False)
    cnpj_cpf: Mapped[str] = mapped_column(String(18), nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    situacao_cadastral: Mapped[str] = mapped_column(String(10), nullable=False, default="REGULAR")
    motivo_pendencia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    banco_cif: Mapped[str | None] = mapped_column(Text, nullable=True)
    agencia_cif: Mapped[str | None] = mapped_column(Text, nullable=True)
    conta_cif: Mapped[str | None] = mapped_column(Text, nullable=True)
    chave_pix_cif: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class FornecedorSituacaoHistorico(Base):
    """Log append-only de mudanças de situação cadastral do fornecedor."""
    __tablename__ = "fornecedor_situacao_historico"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_fornecedor: Mapped[int] = mapped_column(ForeignKey("pagamentos.fornecedor.id"), nullable=False)
    situacao: Mapped[str] = mapped_column(String(10), nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("utils.usuario.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class NaturezaDespesa(Base):
    __tablename__ = "natureza_despesa"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    descricao: Mapped[str] = mapped_column(String(150), nullable=False)
    criticidade_padrao: Mapped[str] = mapped_column(String(10), nullable=False, default="MEDIA")
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class FonteRecursos(Base):
    __tablename__ = "fonte_recursos"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    grupos_despesa_permitidos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Campos ricos v2.0 (RF-FON-01/07)
    exercicio: Mapped[int | None] = mapped_column(Integer, nullable=True)
    esfera_origem: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tipo_vinculacao: Mapped[str | None] = mapped_column(String(30), nullable=True)
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, default="ATIVA")
    vigencia_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    vigencia_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ContaBancaria(Base):
    __tablename__ = "conta_bancaria"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    banco: Mapped[str] = mapped_column(String(100), nullable=False)
    agencia: Mapped[str] = mapped_column(String(20), nullable=False)
    conta: Mapped[str] = mapped_column(String(30), nullable=False)
    id_fonte_recursos: Mapped[int] = mapped_column(ForeignKey("pagamentos.fonte_recursos.id"), nullable=False)
    grupo_despesa: Mapped[str] = mapped_column(String(20), nullable=False)
    saldo_minimo_alerta: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    saldo_inicial: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Campos ricos v2.0 (RF-CTA-01/08). modo_movimentacao='PAGA' → elegível como conta pagadora.
    digito: Mapped[str | None] = mapped_column(String(5), nullable=True)
    tipo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    titularidade: Mapped[str | None] = mapped_column(String(150), nullable=True)
    orgao_gestor: Mapped[str | None] = mapped_column(String(150), nullable=True)
    finalidade: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data_abertura: Mapped[date | None] = mapped_column(Date, nullable=True)
    modo_movimentacao: Mapped[str] = mapped_column(String(15), nullable=False, default="PAGA")
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Contrato(Base):
    __tablename__ = "contrato"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    numero: Mapped[str] = mapped_column(String(50), nullable=False)
    id_fornecedor: Mapped[int] = mapped_column(ForeignKey("pagamentos.fornecedor.id"), nullable=False)
    id_unidade: Mapped[int] = mapped_column(ForeignKey("utils.unidade_trabalho.id"), nullable=False)
    objeto: Mapped[str] = mapped_column(String(255), nullable=False)
    vigencia_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    vigencia_fim: Mapped[date] = mapped_column(Date, nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # Categoria para a fila cronológica (F3). Nullable de propósito: obrigar o
    # ente a classificar todo o histórico no dia do deploy travaria o módulo.
    categoria: Mapped[str | None] = mapped_column(String(20), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class MovimentacaoConta(Base):
    __tablename__ = "movimentacao_conta"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_conta: Mapped[int] = mapped_column(ForeignKey("pagamentos.conta_bancaria.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    origem: Mapped[str] = mapped_column(String(20), nullable=False)
    id_debito: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_parcela: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("utils.usuario.id"), nullable=True)
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Debito(Base):
    __tablename__ = "debito"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_fornecedor: Mapped[int] = mapped_column(ForeignKey("pagamentos.fornecedor.id"), nullable=False)
    id_natureza: Mapped[int] = mapped_column(ForeignKey("pagamentos.natureza_despesa.id"), nullable=False)
    # Fonte do empenho — vinculante (v2.0 RN-02/05). A conta pagadora é escolhida
    # na autorização apenas entre contas desta fonte.
    id_fonte_recursos: Mapped[int] = mapped_column(ForeignKey("pagamentos.fonte_recursos.id"), nullable=False)
    # Conta sugerida na criação (não-vinculante, seção 6.1) — pode ser nula.
    id_conta: Mapped[int | None] = mapped_column(ForeignKey("pagamentos.conta_bancaria.id"), nullable=True)
    # Conta pagadora escolhida/reservada na autorização — imutável após gravada.
    id_conta_pagadora: Mapped[int | None] = mapped_column(
        ForeignKey("pagamentos.conta_bancaria.id"), nullable=True)
    id_contrato: Mapped[int | None] = mapped_column(ForeignKey("pagamentos.contrato.id"), nullable=True)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    competencia: Mapped[str] = mapped_column(String(7), nullable=False)
    numero_ne: Mapped[str | None] = mapped_column(String(30), nullable=True)
    numero_nf: Mapped[str | None] = mapped_column(String(40), nullable=True)
    criticidade: Mapped[str] = mapped_column(String(10), nullable=False, default="MEDIA")
    urgente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    justificativa_urgencia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(25), nullable=False, default="RASCUNHO")
    # --- as três dimensões (F1, spec §4.1) ---------------------------------
    # `status` acima passa a ser DERIVADO destas três
    # (services/pagamentos_estados.status_legado) e sobrevive só até a F5,
    # porque conciliação, exceções, caixa, export, filas e o frontend inteiro
    # ainda o leem.
    situacao_tramitacao: Mapped[str] = mapped_column(
        String(30), nullable=False, default="RASCUNHO")
    situacao_fila: Mapped[str] = mapped_column(
        String(30), nullable=False, default="NAO_REGISTRADA")
    situacao_pagamento: Mapped[str] = mapped_column(
        String(20), nullable=False, default="NAO_INICIADA")
    # Unidade administrativa de origem. Antes da F1 só existia via contrato —
    # débito sem contrato não tinha unidade nenhuma, o que inviabilizava tanto o
    # papel "Unidade Setorial" quanto a chave da fila cronológica da F3.
    id_unidade: Mapped[int] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    id_gestor_decisor: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True)
    id_validador: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True)
    id_usuario_solicitante: Mapped[int] = mapped_column(ForeignKey("utils.usuario.id"), nullable=False)
    # Liquidação (v2.0 RF-VAL-02/RN-01) — guarda antes de autorizar.
    liquidacao_confirmada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    data_liquidacao: Mapped[date | None] = mapped_column(Date, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Parcela(Base):
    __tablename__ = "parcela"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_debito: Mapped[int] = mapped_column(ForeignKey("pagamentos.debito.id"), nullable=False)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="A_PAGAR")
    data_pagamento: Mapped[date | None] = mapped_column(Date, nullable=True)
    forma_pagamento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    id_movimentacao: Mapped[int | None] = mapped_column(ForeignKey("pagamentos.movimentacao_conta.id"), nullable=True)
    data_liberacao: Mapped[date | None] = mapped_column(Date, nullable=True)
    id_usuario_liberacao: Mapped[int | None] = mapped_column(ForeignKey("utils.usuario.id"), nullable=True)
    data_prevista_pagamento: Mapped[date | None] = mapped_column(Date, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DebitoHistorico(Base):
    """Trilha imutável das transições do débito (append-only)."""
    __tablename__ = "debito_historico"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_debito: Mapped[int] = mapped_column(ForeignKey("pagamentos.debito.id"), nullable=False)
    status_anterior: Mapped[str | None] = mapped_column(String(25), nullable=True)
    status_novo: Mapped[str] = mapped_column(String(25), nullable=False)
    acao: Mapped[str] = mapped_column(String(20), nullable=False)
    justificativa: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("utils.usuario.id"), nullable=True)
    ip_origem: Mapped[str | None] = mapped_column(String(45), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OrdemPagamento(Base):
    __tablename__ = "ordem_pagamento"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    id_usuario_autorizador: Mapped[int] = mapped_column(ForeignKey("utils.usuario.id"), nullable=False)
    # Conta pagadora + valor reservado da autorização (registro histórico v2.0 seção 19).
    id_conta_pagadora: Mapped[int | None] = mapped_column(
        ForeignKey("pagamentos.conta_bancaria.id"), nullable=True)
    valor_reservado: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    # RF-AUT-16: saldo disponível antes e projetado após a reserva (auditoria).
    saldo_antes: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    saldo_projetado_apos: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    ip_origem: Mapped[str | None] = mapped_column(String(45), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OrdemPagamentoDebito(Base):
    __tablename__ = "ordem_pagamento_debito"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_ordem: Mapped[int] = mapped_column(ForeignKey("pagamentos.ordem_pagamento.id"), nullable=False)
    id_debito: Mapped[int] = mapped_column(ForeignKey("pagamentos.debito.id"), nullable=False)


class Alcada(Base):
    __tablename__ = "alcada"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("utils.usuario.id"), nullable=False)
    id_natureza: Mapped[int | None] = mapped_column(ForeignKey("pagamentos.natureza_despesa.id"), nullable=True)
    valor_maximo: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # Dimensões opcionais v2.0 (RF-CAD-06) — nulas = alçada genérica.
    id_unidade: Mapped[int | None] = mapped_column(ForeignKey("utils.unidade_trabalho.id"), nullable=True)
    id_fonte: Mapped[int | None] = mapped_column(ForeignKey("pagamentos.fonte_recursos.id"), nullable=True)
    tipo_despesa: Mapped[str | None] = mapped_column(String(20), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class BloqueioSaldo(Base):
    """Valor administrativamente bloqueado numa conta por período (RF-SLD-07)."""
    __tablename__ = "bloqueio_saldo"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_conta: Mapped[int] = mapped_column(ForeignKey("pagamentos.conta_bancaria.id"), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    motivo: Mapped[str] = mapped_column(String(255), nullable=False)
    periodo_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    periodo_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    id_usuario_responsavel: Mapped[int | None] = mapped_column(ForeignKey("utils.usuario.id"), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SaldoHistorico(Base):
    """Snapshot diário dos saldos por conta (RF-SLD-03), preenchido por job."""
    __tablename__ = "saldo_historico"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_conta: Mapped[int] = mapped_column(ForeignKey("pagamentos.conta_bancaria.id"), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    saldo_bancario: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    saldo_conciliado: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    saldo_reservado: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    saldo_bloqueado: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ContaFonteHistorico(Base):
    """Trilha append-only das trocas de fonte de uma conta (RF-CTA-06)."""
    __tablename__ = "conta_fonte_historico"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_conta: Mapped[int] = mapped_column(ForeignKey("pagamentos.conta_bancaria.id"), nullable=False)
    id_fonte_anterior: Mapped[int | None] = mapped_column(
        ForeignKey("pagamentos.fonte_recursos.id"), nullable=True)
    id_fonte_nova: Mapped[int] = mapped_column(ForeignKey("pagamentos.fonte_recursos.id"), nullable=False)
    justificativa: Mapped[str] = mapped_column(String(255), nullable=False)
    vigencia: Mapped[date] = mapped_column(Date, nullable=False)
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("utils.usuario.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ChecklistItem(Base):
    """Item parametrizável de checklist documental (RF-VAL-01/06). id_natureza
    nulo = aplica a todos os débitos; senão, só à natureza indicada."""
    __tablename__ = "checklist_item"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    obrigatorio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    id_natureza: Mapped[int | None] = mapped_column(
        ForeignKey("pagamentos.natureza_despesa.id"), nullable=True)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DebitoChecklistMarca(Base):
    """Log append-only das marcações de checklist por débito (RF-VAL-06)."""
    __tablename__ = "debito_checklist_marca"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_debito: Mapped[int] = mapped_column(ForeignKey("pagamentos.debito.id"), nullable=False)
    id_checklist_item: Mapped[int] = mapped_column(
        ForeignKey("pagamentos.checklist_item.id"), nullable=False)
    marcado: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("utils.usuario.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class TagPrioridade(Base):
    """Rótulos de priorização por tenant (RF-CAD-05)."""
    __tablename__ = "tag_prioridade"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(50), nullable=False)
    cor: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Extrato(Base):
    """Arquivo de extrato bancário importado (RF-EXT-01/10)."""
    __tablename__ = "extrato"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_conta: Mapped[int] = mapped_column(ForeignKey("pagamentos.conta_bancaria.id"), nullable=False)
    periodo_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    periodo_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    nome_arquivo: Mapped[str] = mapped_column(String(255), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    formato: Mapped[str] = mapped_column(String(10), nullable=False)
    status_processamento: Mapped[str] = mapped_column(String(20), nullable=False, default="IMPORTADO")
    qtd_lancamentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("utils.usuario.id"), nullable=True)
    importado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class LancamentoExtrato(Base):
    """Linha de um extrato (RF-EXT-02)."""
    __tablename__ = "lancamento_extrato"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_extrato: Mapped[int] = mapped_column(ForeignKey("pagamentos.extrato.id"), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    historico: Mapped[str] = mapped_column(String(255), nullable=False)
    documento: Mapped[str | None] = mapped_column(String(50), nullable=True)
    favorecido: Mapped[str | None] = mapped_column(String(150), nullable=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)  # CREDITO | DEBITO
    conciliado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Conciliacao(Base):
    """Correspondência entre um lançamento do extrato e a movimentação da conta
    (RF-EXT-04/05). Uma por lançamento e uma por movimentação (RN-14)."""
    __tablename__ = "conciliacao"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_lancamento: Mapped[int] = mapped_column(
        ForeignKey("pagamentos.lancamento_extrato.id"), nullable=False)
    id_movimentacao: Mapped[int | None] = mapped_column(
        ForeignKey("pagamentos.movimentacao_conta.id"), nullable=True)
    id_parcela: Mapped[int | None] = mapped_column(ForeignKey("pagamentos.parcela.id"), nullable=True)
    tipo_correspondencia: Mapped[str] = mapped_column(String(15), nullable=False)
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("utils.usuario.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
