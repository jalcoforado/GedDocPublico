"""Espécie documental — catálogo do tipo de documento que originou um protocolo.

Distinto de `TipoAnexo` (que classifica arquivos individuais) e de
`TipoProcesso` (que classifica o processo como um todo). Espécie documental
diz o que é o documento DE ENTRADA: Ofício, Requerimento, Memorando, etc.

Tenant-scoped (cada prefeitura mantém seu catálogo). Seed inicial de
10 espécies em migration 0015.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class EspecieDocumental(Base):
    __tablename__ = "especie_documental"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    flag: Mapped[str] = mapped_column(String(40), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
