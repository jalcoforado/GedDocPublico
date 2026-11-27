"""Avaliação de documento do processo (SI-73, RF-04 V2). Migration 0148.

Regras em `docs/avaliacao-de-documentos.md`. Avaliar não é assinar: nada aqui
toca `assinatura_anexo`.
"""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class AvaliacaoPedido(Base):
    __tablename__ = "avaliacao_pedido"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_processo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=False
    )
    id_usuario_solicitante: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    id_usuario_avaliador: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    orientacao: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    prazo: Mapped[date | None] = mapped_column(Date, nullable=True)
    # `pendente` enquanto houver documento sem decisão; `concluida` quando
    # todos foram decididos. Volta a `pendente` no reenvio de um devolvido.
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente")
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AvaliacaoDocumento(Base):
    """Um documento do pedido e a decisão sobre ele.

    `id_anexo` é a VERSÃO EXATA avaliada: a aprovação da versão 1 não vale
    para a versão 2. O reenvio do devolvido é outra linha, com a versão
    corrigida, apontando para a devolvida (`id_avaliacao_anterior`).
    """

    __tablename__ = "avaliacao_documento"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_pedido: Mapped[int] = mapped_column(
        ForeignKey("protocolos.avaliacao_pedido.id"), nullable=False
    )
    id_anexo: Mapped[int] = mapped_column(ForeignKey("protocolos.anexo.id"), nullable=False)
    id_avaliacao_anterior: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.avaliacao_documento.id"), nullable=True
    )
    # NULL = aguardando; `aprovado` | `devolvido`.
    resultado: Mapped[str | None] = mapped_column(String(20), nullable=True)
    justificativa: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    id_usuario_decisao: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    decidido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
