"""Transporte Regulado — modelo de Permissionário (fundação).

Domínio SEPARADO da Frota Interna (schema `transporte_regulado`, permissão
`transporte_regulado`). Tenant-scoped, RLS em `transporte_regulado.permissionario`
(ver migration 0041), no mesmo padrão de `frota.veiculo`.

`situacao` é o estado regulatório do permissionário (pendente / ativo / suspenso /
cassado / inativo); `excluido` é soft-delete. `cpf` único por tenant entre não
excluídos.
"""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Permissionario(Base):
    __tablename__ = "permissionario"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cpf: Mapped[str] = mapped_column(String(11), nullable=False)
    rg: Mapped[str | None] = mapped_column(String(20), nullable=True)
    data_nascimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cnh_numero: Mapped[str | None] = mapped_column(String(11), nullable=True)
    cnh_categoria: Mapped[str | None] = mapped_column(String(5), nullable=True)
    cnh_validade: Mapped[date | None] = mapped_column(Date, nullable=True)
    tipo_servico: Mapped[str] = mapped_column(String(30), nullable=False)
    numero_permissao: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data_inicio_permissao: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_validade_permissao: Mapped[date | None] = mapped_column(Date, nullable=True)
    situacao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pendente"
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
