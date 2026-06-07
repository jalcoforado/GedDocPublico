"""Gestão de Frota Pública — modelo de Veículo (fundação).

Tenant-scoped (cada prefeitura mantém sua própria frota). RLS em `frota.veiculo`
(ver migration 0031), no mesmo padrão de `protocolos.servico`.

Design: `situacao` é o estado de domínio do veículo (disponível / em uso /
manutenção / inativo / baixado); `excluido` é soft-delete. Não há flag `ativo`
separada — `situacao` já cobre disponibilidade (evita redundância).
"""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Veiculo(Base):
    __tablename__ = "veiculo"
    __table_args__ = {"schema": "frota"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    placa: Mapped[str] = mapped_column(String(8), nullable=False)
    renavam: Mapped[str | None] = mapped_column(String(20), nullable=True)
    chassi: Mapped[str | None] = mapped_column(String(30), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(60), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ano_fabricacao: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ano_modelo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cor: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tipo_veiculo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tipo_combustivel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    situacao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="disponivel"
    )
    # Soft-ref validada same-tenant no serviço (a FK garante integridade mas
    # NÃO filtra por tenant — mesmo critério de `servico.id_unidade_responsavel`).
    id_unidade_responsavel: Mapped[int | None] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=True
    )
    quilometragem_atual: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    data_aquisicao: Mapped[date | None] = mapped_column(Date, nullable=True)
    forma_posse: Mapped[str] = mapped_column(
        String(20), nullable=False, default="proprio"
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Motorista(Base):
    """Motorista / condutor da frota (PR Frota-2).

    `cpf` único por tenant entre não excluídos. `situacao` é o estado do
    condutor (ativo / afastado / inativo); `excluido` é soft-delete. `id_usuario`
    é opcional — vincula o motorista a um usuário do sistema, quando for o caso.
    """

    __tablename__ = "motorista"
    __table_args__ = {"schema": "frota"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cpf: Mapped[str] = mapped_column(String(11), nullable=False)
    matricula: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cnh_numero: Mapped[str] = mapped_column(String(11), nullable=False)
    cnh_categoria: Mapped[str] = mapped_column(String(5), nullable=False)
    cnh_validade: Mapped[date] = mapped_column(Date, nullable=False)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Soft-refs validadas same-tenant no serviço (a FK garante integridade mas
    # NÃO filtra por tenant — mesmo critério de `id_unidade_responsavel`).
    id_unidade: Mapped[int | None] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=True
    )
    id_usuario: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    situacao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ativo"
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
