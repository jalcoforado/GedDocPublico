"""Login do cidadão pelo gov.br — as duas pernas HTTP do fluxo OIDC.

`GET /auth/govbr/login?next=/cidadao/...` → grava o cookie de estado e manda o
navegador ao gov.br. `GET /auth/govbr/callback?code&state` → confere o estado,
troca o code servidor-a-servidor, provisiona/vincula o cidadão e emite a MESMA
sessão do login por senha (`auth/cidadao_sessao.py`).

Desligado por padrão: sem `GOVBR_CLIENT_ID`/`GOVBR_CLIENT_SECRET`/
`GOVBR_SSO_URL`, as duas rotas respondem 503. A regra de segurança de cada
passo está em `services/govbr_sso.py`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.cidadao_sessao import emitir_sessao_cidadao
from ..auth.deps import require_tenant_id
from ..auth.jwt import get_jwt_secret
from ..config import get_settings
from ..database import get_db
from ..services import govbr_sso
from ..services.cidadao_auth import (
    CidadaoAuthError,
    CidadaoInativoError,
    login_ou_cadastrar_via_govbr,
)
from ..services.govbr_sso import COOKIE_ESTADO, GovBrErro

router = APIRouter(prefix="/auth/govbr", tags=["auth"])

_CAMINHO_COOKIE = "/api/v2/auth/govbr"


def _redirect_uri(request: Request) -> str:
    fixo = get_settings().govbr_redirect_uri.strip()
    return fixo or str(request.url_for("govbr_callback"))


_MOTIVO_POR_STATUS = {503: "indisponivel", 403: "inativo"}


def _erro(request: Request, status_code: int, detalhe: str, *, motivo: str | None = None) -> Response:
    """Resposta de erro que também descarta o estado: não se reaproveita.

    Quem chega aqui pelo NAVEGADOR (pede HTML) é o cidadão no meio do login:
    ele volta à tela de login com um motivo curto na URL, em vez de ver um JSON
    cru. Cliente de API continua recebendo o status e o JSON de sempre — é o
    que os testes de segurança afirmam, um status por checagem. O motivo não
    carrega o detalhe interno: é um de quatro rótulos fixos.
    """
    if "text/html" in request.headers.get("accept", ""):
        rotulo = motivo or _MOTIVO_POR_STATUS.get(status_code, "falhou")
        resp: Response = RedirectResponse(f"/cidadao/login?govbr={rotulo}", status_code=302)
    else:
        resp = JSONResponse(status_code=status_code, content={"detail": detalhe})
    resp.delete_cookie(COOKIE_ESTADO, path=_CAMINHO_COOKIE)
    return resp


@router.get("/disponivel")
async def govbr_disponivel() -> dict[str, bool]:
    """Se o portal deve mostrar o botão "Entrar com gov.br". Sem credenciais
    configuradas o botão não aparece — em vez de aparecer e falhar."""
    return {"disponivel": get_settings().govbr_configurado}


@router.get("/login")
async def govbr_login(
    request: Request,
    next: str | None = None,  # noqa: A002 — nome do parâmetro é o contrato do portal
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        govbr_sso.exigir_configuracao()
    except GovBrErro as e:
        return _erro(request, e.status_code, e.detalhe)

    estado = govbr_sso.novo_estado(tenant_id=tenant_id, destino=next)
    cookie = govbr_sso.codificar_estado(estado, await get_jwt_secret(db))
    resp = RedirectResponse(
        govbr_sso.url_autorizacao(estado, redirect_uri=_redirect_uri(request)),
        status_code=302,
    )
    resp.set_cookie(
        COOKIE_ESTADO,
        cookie,
        max_age=govbr_sso.TTL_ESTADO_S,
        httponly=True,
        # `lax` é o que deixa o cookie voltar na navegação de topo vinda do
        # gov.br; `strict` o perderia e todo callback daria 400.
        samesite="lax",
        path=_CAMINHO_COOKIE,
    )
    return resp


@router.get("/callback", name="govbr_callback")
async def govbr_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        govbr_sso.exigir_configuracao()
        # Estado ANTES de tudo, inclusive do `error`: sem ele não há como saber
        # se esta requisição é o retorno de um fluxo nosso.
        estado = govbr_sso.conferir_estado(
            request.cookies.get(COOKIE_ESTADO),
            state_recebido=state,
            tenant_id=tenant_id,
            segredo_jwt=await get_jwt_secret(db),
        )
        if error or not code:
            # O próprio gov.br devolveu `error` (ex.: o cidadão recusou) — o
            # estado já foi conferido acima, então isto é um retorno nosso.
            return _erro(request, 401, "Login gov.br não concluído",
                         motivo="cancelado" if error else None)
        identidade = await govbr_sso.identidade_do_callback(
            code, estado, redirect_uri=_redirect_uri(request)
        )
    except GovBrErro as e:
        return _erro(request, e.status_code, e.detalhe)

    try:
        cidadao = await login_ou_cadastrar_via_govbr(
            db,
            tenant_id=tenant_id,
            cpf=identidade.cpf,
            nome=identidade.nome,
            email=identidade.email,
            nivel_govbr=identidade.nivel,
            app=get_settings().app_name,
        )
    except CidadaoInativoError as e:
        return _erro(request, 403, str(e))
    except CidadaoAuthError as e:
        return _erro(request, 401, str(e))

    resp = RedirectResponse(estado.destino, status_code=302)
    await emitir_sessao_cidadao(db, resp, cidadao, tenant_id=tenant_id)
    resp.delete_cookie(COOKIE_ESTADO, path=_CAMINHO_COOKIE)
    return resp
