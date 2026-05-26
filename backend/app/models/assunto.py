from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class TipoProcesso(Base):
    __tablename__ = "tipo_processo"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    tipo_processo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    exige_processo_pai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Assunto(Base):
    __tablename__ = "assunto"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    assunto: Mapped[str] = mapped_column(String(1000), nullable=False)
    id_tipo_processo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.tipo_processo.id"), nullable=False
    )
    exige_processo_pai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TipoAnexo(Base):
    __tablename__ = "tipo_anexo"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    tipo_anexo: Mapped[str | None] = mapped_column(String(150), nullable=True)
    excluido: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)


class AssuntoTipoProcessoTipoAnexo(Base):
    __tablename__ = "assunto_tipo_processo_tipo_anexo"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_assunto: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.assunto.id"), nullable=True
    )
    id_tipo_processo: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.tipo_processo.id"), nullable=True
    )
    id_tipo_anexo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.tipo_anexo.id"), nullable=False
    )
    obrigatorio: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    opcional: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    excluido: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
