"""Login do servidor municipal com a conta Google (SI-32) — as pernas HTTP.

`GET /auth/google-login/inicio?next=/m/...` → grava o cookie de estado e manda
o navegador ao Google. `GET /auth/google-login/callback?code&state` → confere o
estado, troca o code servidor-a-servidor, acha o usuário ATIVO deste tenant com
o e-mail verificado e emite a MESMA sessão do login por senha
(`routers/auth._emitir_sessao`).

Não confundir com `/auth/google` e `/auth/google/callback` (em `auth.py`): lá é
a conexão da conta Google às minutas (Google Docs), feita por quem JÁ está
logado; aqui é a entrada no sistema. Mesmo client ID/secret, endereços de
retorno diferentes — os dois cadastrados no Google Cloud.

Desligado por padrão: sem `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET`
o botão não aparece e as rotas voltam a `/login?google=indisponivel`. A regra de
segurança de cada passo está em `services/google_login.py`.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.jwt import get_jwt_secret
from ..config import get_settings
from ..database import get_db
from ..models import Usuario
from ..services import google_login
from ..services.google_login import CAMINHO_COOKIE, COOKIE_ESTADO, GoogleLoginErro
from .auth import _emitir_sessao

router = APIRouter(prefix="/auth/google-login", tags=["auth"])
logger = logging.getLogger(__name__)


def _redirect_uri(request: Request) -> str:
    return get_settings().google_login_redirect or str(request.url_for("google_login_callback"))


def _voltar_ao_login(motivo: str) -> Response:
    """Volta à tela de login com um rótulo curto (a tela o traduz; o valor
    da URL nunca é exibido) e descarta o estado: ele não se reaproveita."""
    resp = RedirectResponse(f"/login?google={motivo}", status_code=302)
    resp.delete_cookie(COOKIE_ESTADO, path=CAMINHO_COOKIE)
    return resp


@router.get("/disponivel")
async def google_login_disponivel() -> dict[str, bool]:
    """Se a tela de login mostra "Entrar com o Google" (só lê a configuração)."""
    return {"disponivel": get_settings().google_login_configurado}


@router.get("/inicio")
async def google_login_inicio(
    request: Request,
    next: str | None = None,  # noqa: A002 — mesmo nome do `?next=` da tela de login
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        google_login.exigir_configuracao()
    except GoogleLoginErro as e:
        return _voltar_ao_login(e.motivo)

    estado = google_login.novo_estado(tenant_id=tenant_id, destino=next)
    cookie = google_login.codificar_estado(estado, await get_jwt_secret(db))
    resp = RedirectResponse(
        google_login.url_autorizacao(estado, redirect_uri=_redirect_uri(request)),
        status_code=302,
    )
    resp.set_cookie(
        COOKIE_ESTADO,
        cookie,
        max_age=google_login.TTL_ESTADO_S,
        httponly=True,
        # `lax` deixa o cookie voltar na navegação de topo vinda do Google;
        # `strict` o perderia e todo callback falharia.
        samesite="lax",
        path=CAMINHO_COOKIE,
    )
    return resp


@router.get("/callback", name="google_login_callback")
async def google_login_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    secret = await get_jwt_secret(db)
    try:
        google_login.exigir_configuracao()
        # Estado ANTES de tudo, inclusive do `error`: sem ele não há como saber
        # se esta requisição é o retorno de um fluxo nosso.
        estado = google_login.conferir_estado(
            request.cookies.get(COOKIE_ESTADO),
            state_recebido=state,
            tenant_id=tenant_id,
            segredo_jwt=secret,
        )
        if error or not code:
            return _voltar_ao_login("cancelado" if error == "access_denied" else "falhou")
        identidade = await google_login.identidade_do_callback(
            code, estado, redirect_uri=_redirect_uri(request)
        )
    except GoogleLoginErro as e:
        logger.info("google_login_recusado", extra={"motivo": e.motivo, "detalhe": e.detalhe})
        return _voltar_ao_login(e.motivo)

    # O Google diz QUEM é; o cadastro do município diz se PODE entrar. E-mail
    # comparado sem caixa (o Google devolve minúsculo; o cadastro nem sempre).
    candidatos = (
        await db.execute(
            select(Usuario).where(
                Usuario.tenant_id == tenant_id,
                func.lower(Usuario.email) == identidade.email.lower(),
                Usuario.excluido.is_(False),
                Usuario.ativo.is_(True),
            )
        )
    ).scalars().all()
    if len(candidatos) != 1:
        # Nenhum: a conta Google não é de um servidor daqui. Mais de um: o
        # cadastro está ambíguo, e escolher um deles seria adivinhar.
        logger.info(
            "google_login_sem_usuario",
            extra={"tenant_id": tenant_id, "encontrados": len(candidatos)},
        )
        return _voltar_ao_login("sem_conta")
    user = candidatos[0]

    if user.email_verificado_em is None:
        # Convite ainda não aceito — mesma regra do login por senha.
        return _voltar_ao_login("nao_ativada")

    # A troca obrigatória de senha (SEC-1) tem precedência sobre o `next`,
    # como no login por senha: o backend a exige em toda rota de qualquer jeito.
    destino = "/alterar-senha-obrigatoria" if user.must_change_password else estado.destino
    resp = RedirectResponse(destino, status_code=302)
    _emitir_sessao(resp, user, secret, tenant_id=tenant_id)
    resp.delete_cookie(COOKIE_ESTADO, path=CAMINHO_COOKIE)
    logger.info("google_login_ok", extra={"usuario_id": user.id, "tenant_id": tenant_id})
    return resp
