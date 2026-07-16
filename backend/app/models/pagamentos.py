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
    id_conta: Mapped[int] = mapped_column(ForeignKey("pagamentos.conta_bancaria.id"), nullable=False)
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
    id_usuario_solicitante: Mapped[int] = mapped_column(ForeignKey("utils.usuario.id"), nullable=False)
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
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
