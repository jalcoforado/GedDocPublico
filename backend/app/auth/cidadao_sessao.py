"""Emissão da sessão do cidadão — um formato só, qualquer que seja a porta.

O cidadão entra por senha (`POST /cidadao/login`) ou pelo gov.br
(`GET /auth/govbr/callback`). As duas portas têm de produzir **a mesma**
sessão: token `tipo=cidadao` (`build_cidadao_payload`) no cookie
`aprimora_cidadao_token`, que é o que `get_current_cidadao` lê. Um segundo
formato divergiria em silêncio — e o rascunho do gov.br chegou a emitir o token
de SERVIDOR (`build_payload`, cookie `aprimora_token`) com o id do cidadão no
lugar do `usuario_id`, o que abria a sessão administrativa do servidor de mesmo
id numérico. Por isso a emissão mora aqui e as duas rotas a chamam.
"""
from __future__ import annotations

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import UsuarioExterno
from .jwt import build_cidadao_payload, encode_token, get_jwt_secret

COOKIE_CIDADAO = "aprimora_cidadao_token"


async def emitir_sessao_cidadao(
    db: AsyncSession,
    response: Response,
    cidadao: UsuarioExterno,
    *,
    tenant_id: int,
) -> str:
    """Assina o token do cidadão, grava o cookie em `response` e devolve o token."""
    settings = get_settings()
    secret = await get_jwt_secret(db)
    token = encode_token(
        build_cidadao_payload(cidadao.id, cidadao.cpf_cnpj or "", tenant_id=tenant_id),
        secret,
    )
    response.set_cookie(
        key=COOKIE_CIDADAO,
        value=token,
        max_age=settings.jwt_ttl_seconds,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return token
