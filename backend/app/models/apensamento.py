"""Apensamento + Volumes — Fase P6.

`ProcessoApensamento` é log da operação (anexar/desanexar processo a outro).
`ProcessoVolume` é volume físico de processo grande (vol 1/3, 2/3, …).

Desentranhamento é representado por flags em `AnexoProcesso` (ver
[models/processo.py](../models/processo.py)) — não há tabela separada
pra que a lista de anexos de um processo já reflita a remoção via
``WHERE desentranhado_em IS NULL``.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ProcessoApensamento(Base):
    __tablename__ = "processo_apensamento"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_processo_apensado: Mapped[int] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=False
    )
    id_processo_principal: Mapped[int] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=False
    )
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    motivo: Mapped[str] = mapped_column(String(1000), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    desapensado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    id_usuario_desapensamento: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    motivo_desapensamento: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class ProcessoVolume(Base):
    __tablename__ = "processo_volume"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_processo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=False
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    pagina_inicial: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pagina_final: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observacao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
