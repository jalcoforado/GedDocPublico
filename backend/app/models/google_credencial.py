"""Credencial OAuth do Google (por usuário) para a integração com Google Docs.

Tokens (access/refresh) são armazenados CIFRADOS em repouso (Fernet, chave em
`settings` — ver PR-D). Escopo mínimo `drive.file` (só arquivos criados pelo app).
Tenant-scoped no schema de plataforma `aprimora_py`, RLS por `tenant_id`
(migration 0044). `(tenant_id, id_usuario)` único entre credenciais não revogadas.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class GoogleCredencial(Base):
    __tablename__ = "google_credencial"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    access_token_cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    escopo: Mapped[str] = mapped_column(String(255), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revogado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
