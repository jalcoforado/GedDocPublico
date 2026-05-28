from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class TipoAssinatura(Base):
    __tablename__ = "tipo_assinatura"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo_assinatura: Mapped[str] = mapped_column(String(40), nullable=False)
    flag: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assinar_documentos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    desentranhar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    responder_solicitacao_assinatura: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    externa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SolicitacaoAssinatura(Base):
    __tablename__ = "solicitacao_assinatura"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_processo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=False
    )
    id_solicitante: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    realizada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    id_unidade_solicitante: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dt_inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    dt_fim: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class UsuarioAssinatura(Base):
    __tablename__ = "usuario_assinatura"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_solicitacao_assinatura: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.solicitacao_assinatura.id"), nullable=True
    )
    id_assinante: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    id_tipo_assinatura: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.tipo_assinatura.id"), nullable=True
    )
    id_unidade_trabalho: Mapped[int] = mapped_column(Integer, nullable=False)
    realizada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Assinatura v2 — recusa por signatário
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente")
    motivo_recusa: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    dt_recusa: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AssinaturaAnexo(Base):
    __tablename__ = "assinatura_anexo"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_usuario_assinatura: Mapped[int] = mapped_column(
        ForeignKey("protocolos.usuario_assinatura.id"), nullable=False
    )
    id_anexo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.anexo.id"), nullable=False
    )
    assinado: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    dt_assinatura: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    id_processo: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=True
    )
    # Assinatura v2 — integridade + evidências
    documento_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hash_algoritmo: Mapped[str | None] = mapped_column(String(20), nullable=True, default="sha256")
    documento_versao: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    ip_assinatura: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_assinatura: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metodo_autenticacao: Mapped[str | None] = mapped_column(String(30), nullable=True)
    nivel_assinatura: Mapped[str] = mapped_column(String(20), nullable=False, default="simples")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente")
    motivo: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    evidencias: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    id_audit_log: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("aprimora_py.audit_log.id"), nullable=True
    )
