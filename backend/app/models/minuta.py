"""Minuta de documento — editor interno + templates + Google Docs.

Documentos redigidos na plataforma (a partir de templates com placeholders) ou
no Google Docs, como MINUTA EDITÁVEL/VERSIONADA. Ao finalizar, geram um PDF
anexado ao processo (reusa `services/anexos._criar_anexo_from_bytes`) que entra
no fluxo de carimbo + assinatura v2.

Tenant-scoped, RLS nas tabelas do schema `protocolos` (ver migration 0044), no
mesmo padrão de `transporte_regulado.veiculo` (0043). `excluido` é soft-delete;
`status` controla o ciclo de vida (rascunho / finalizada / cancelada).
"""
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class TemplateDocumento(Base):
    """Biblioteca de modelos de documento (por tenant, geridos pelo admin).

    `corpo_html` é HTML autorado no editor rico (TipTap) com tokens
    `{{placeholder}}` resolvidos ao instanciar uma `Minuta`. `nome` único por
    tenant entre não excluídos (índice parcial na migration).
    """

    __tablename__ = "template_documento"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(300), nullable=True)
    categoria: Mapped[str | None] = mapped_column(String(80), nullable=True)
    corpo_html: Mapped[str] = mapped_column(Text, nullable=False)
    placeholders_utilizados: Mapped[list[Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    id_usuario_criacao: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Minuta(Base):
    """Documento editável/versionado vinculado a um processo.

    `origem='interno'` → conteúdo em `corpo_html`; `origem='google'` → editado no
    Google Docs (`google_doc_id`), `corpo_html` fica nulo até import. Ao finalizar,
    `id_anexo_final` aponta para o `Anexo` gerado (invariante:
    finalizada ⟺ id_anexo_final NOT NULL). Mutável apenas enquanto `rascunho`.
    """

    __tablename__ = "minuta"
    __table_args__ = (
        CheckConstraint(
            "origem IN ('interno', 'google')",
            name="ck_minuta_origem_valida",
        ),
        CheckConstraint(
            "status IN ('rascunho', 'finalizada', 'cancelada')",
            name="ck_minuta_status_valido",
        ),
        CheckConstraint(
            "(status = 'finalizada') = (id_anexo_final IS NOT NULL)",
            name="ck_minuta_finalizada_tem_anexo",
        ),
        CheckConstraint(
            "origem = 'google' OR google_doc_id IS NULL",
            name="ck_minuta_google_doc_id_coerente",
        ),
        {"schema": "protocolos"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_processo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=False
    )
    id_template_origem: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.template_documento.id"), nullable=True
    )
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    origem: Mapped[str] = mapped_column(String(20), nullable=False, default="interno")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="rascunho")
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    corpo_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_doc_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    google_doc_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    id_usuario_google: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    id_anexo_final: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.anexo.id"), nullable=True
    )
    id_usuario_criacao: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    id_usuario_finalizacao: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    finalizada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class MinutaHistorico(Base):
    """Snapshot append-only do conteúdo por "Salvar rascunho" (versionamento).

    Uma linha por versão explícita salva; `(id_minuta, versao)` único.
    """

    __tablename__ = "minuta_historico"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_minuta: Mapped[int] = mapped_column(
        ForeignKey("protocolos.minuta.id"), nullable=False
    )
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    corpo_html: Mapped[str] = mapped_column(Text, nullable=False)
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
