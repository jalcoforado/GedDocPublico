from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
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


class AssinaturaAnexo(Base):
    __tablename__ = "assinatura_anexo"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
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
