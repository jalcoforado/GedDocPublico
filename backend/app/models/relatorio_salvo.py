"""Relatório montado e salvo pela própria pessoa (SI-35, migration 0138)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class RelatorioSalvo(Base):
    """Só a DEFINIÇÃO do relatório (colunas, filtros, período, agrupamento,
    ordem) — nunca dados. Cada abertura roda a consulta de novo com o sigilo
    de quem abre (`services/relatorios_montado.py`).

    Pessoal (decisão do PO, 2026-11-12): pertence a `(tenant_id, id_usuario)`
    e mais ninguém o vê — o de outra pessoa responde 404. Excluir apaga a
    linha: não é registro de negócio, como o favorito.
    """

    __tablename__ = "relatorio_salvo"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("utils.usuario.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    definicao: Mapped[dict] = mapped_column(JSONB, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
