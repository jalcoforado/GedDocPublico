"""CCD (Classificação Documental) + TTD (Tabela de Temporalidade) — Fase P4."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class CcdClasse(Base):
    __tablename__ = "ccd_classe"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    id_classe_pai: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.ccd_classe.id"), nullable=True
    )
    palavras_chave: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class TtdRegra(Base):
    __tablename__ = "ttd_regra"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_ccd_classe: Mapped[int] = mapped_column(
        ForeignKey("protocolos.ccd_classe.id"), nullable=False
    )
    id_especie_documental: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.especie_documental.id"), nullable=True
    )
    anos_corrente: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    anos_intermediario: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    destino_final: Mapped[str] = mapped_column(String(30), nullable=False)
    observacao: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
