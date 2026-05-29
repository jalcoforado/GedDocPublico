"""Catálogo de Serviços / Carta de Serviços (PR 4a).

Tenant-scoped (cada prefeitura mantém seus serviços públicos). Os defaults
(unidade/tipo/assunto/espécie) são soft-refs validadas no serviço de domínio —
a FK garante integridade, mas NÃO filtra por tenant (ver services/servico.py).
"""
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Servico(Base):
    __tablename__ = "servico"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    descricao_curta: Mapped[str | None] = mapped_column(String(300), nullable=True)
    descricao_detalhada: Mapped[str | None] = mapped_column(Text, nullable=True)
    publico_alvo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    instrucoes_cidadao: Mapped[str | None] = mapped_column(Text, nullable=True)
    documentos_exigidos: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    prazo_estimado_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Defaults (soft-ref validado same-tenant no serviço de domínio).
    id_unidade_responsavel: Mapped[int | None] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=True
    )
    id_tipo_processo_padrao: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.tipo_processo.id"), nullable=True
    )
    id_assunto_padrao: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.assunto.id"), nullable=True
    )
    id_especie_documental_padrao: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.especie_documental.id"), nullable=True
    )
    nivel_sigilo_padrao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ostensivo"
    )
    canal_entrada_permitido: Mapped[str] = mapped_column(
        String(20), nullable=False, default="portal"
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    destaque: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ordem_exibicao: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    categoria: Mapped[str | None] = mapped_column(String(80), nullable=True)
    texto_confirmacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
