"""Transporte Regulado — modelos de Permissionário e Empresa.

Domínio SEPARADO da Frota Interna (schema `transporte_regulado`, permissão
`transporte_regulado`). Tenant-scoped, RLS nas tabelas do schema (ver migrations
0041/0042), no mesmo padrão de `frota.veiculo`.

`situacao` é o estado regulatório (pendente / ativo(a) / suspenso(a) /
cassado(a) / inativo(a)); `excluido` é soft-delete. `cpf`/`cnpj` únicos por tenant
entre não excluídos.
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


class Empresa(Base):
    """Empresa/operadora regulada. `cnpj` único por tenant entre não excluídas;
    `id_representante_permissionario` opcional (FK para `permissionario`, mesmo
    tenant — coerência garantida no serviço)."""

    __tablename__ = "empresa"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    razao_social: Mapped[str] = mapped_column(String(200), nullable=False)
    nome_fantasia: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False)
    inscricao_municipal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    inscricao_estadual: Mapped[str | None] = mapped_column(String(30), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cep: Mapped[str | None] = mapped_column(String(9), nullable=True)
    logradouro: Mapped[str | None] = mapped_column(String(200), nullable=True)
    numero: Mapped[str | None] = mapped_column(String(20), nullable=True)
    complemento: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bairro: Mapped[str | None] = mapped_column(String(100), nullable=True)
    municipio: Mapped[str | None] = mapped_column(String(100), nullable=True)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True)
    tipo_servico: Mapped[str] = mapped_column(String(30), nullable=False)
    numero_autorizacao: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data_inicio_autorizacao: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_validade_autorizacao: Mapped[date | None] = mapped_column(Date, nullable=True)
    id_representante_permissionario: Mapped[int | None] = mapped_column(
        ForeignKey("transporte_regulado.permissionario.id"), nullable=True
    )
    situacao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pendente"
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
