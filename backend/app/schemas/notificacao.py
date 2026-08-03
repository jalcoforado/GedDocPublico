"""Schemas Pydantic — Notificacao (Fase 17)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class NotificacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    canal: str
    tipo: str
    titulo: str
    mensagem: str
    link_url: str | None
    payload: dict[str, Any] | None
    prioridade: str
    criado_em: datetime
    lido_em: datetime | None
    enviado_em: datetime | None
    erro: str | None


class NotificacaoListResponse(BaseModel):
    items: list[NotificacaoOut]
    nao_lidas: int


class MarcarLidasResponse(BaseModel):
    atualizadas: int


# Fase 17b — preferências
class PreferenciaResponse(BaseModel):
    in_app: bool
    email: bool
    whatsapp: bool


class PreferenciaUpdate(BaseModel):
    in_app: bool | None = None
    email: bool | None = None
    whatsapp: bool | None = None


# Fase 16 — telefone do usuário corrente + teste manual de WhatsApp
class TelefoneUpdate(BaseModel):
    telefone: str | None  # E.164 sugerido; aceita None pra limpar


class TelefoneResponse(BaseModel):
    telefone: str | None


class WhatsAppTestRequest(BaseModel):
    """Corpo do teste de WhatsApp. **Não tem destino.**

    O campo `telefone` foi REMOVIDO (backlog 1.0.6): ele era destino livre, e
    qualquer autenticado do tenant mandava mensagem para número arbitrário
    usando a credencial paga do tenant. O destino agora é sempre o telefone do
    perfil de quem chama, resolvido no servidor.

    Não reintroduza um campo de destino aqui sem antes decidir quem tem
    autorização para mandar mensagem a terceiro — hoje ninguém tem.
    """

    mensagem: str = "Teste de WhatsApp via Aprimora"


class WhatsAppTestResponse(BaseModel):
    id_notificacao: int
    enviado_em: str | None
    erro: str | None
    provider: str
