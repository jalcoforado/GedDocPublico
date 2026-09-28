from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from ..auth.deps import require_tenant_id
from ..auth.jwt import build_payload, encode_token, get_jwt_secret
from ..config import get_settings
from ..database import get_db
from ..services.cidadao_auth import login_ou_cadastrar_via_govbr
from ..services.govbr_sso import GovBrOAuthFlow

router = APIRouter(prefix="/auth/govbr", tags=["auth"])
_settings = get_settings()

@router.get("/login")
async def govbr_login(request: Request):
    """Redireciona o cidadão para o SSO do Gov.br"""
    # Em um app real, state deve ser um JWT curto ou um UUID no Redis
    # para validar contra ataques CSRF e guardar o tenant_id inicial.
    state = str(uuid.uuid4())
    
    # Redirecionamento configurado para a própria API processar
    redirect_uri = str(request.url_for("govbr_callback"))
    flow = GovBrOAuthFlow(redirect_uri=redirect_uri)
    
    auth_url = flow.get_authorization_url(state=state)
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def govbr_callback(
    request: Request,
    response: Response,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db)
):
    """Recebe o code do Gov.br, troca pelo token e faz login do cidadão"""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID não identificado na sessão")

    redirect_uri = str(request.url_for("govbr_callback"))
    flow = GovBrOAuthFlow(redirect_uri=redirect_uri)
    
    try:
        user_info = await flow.fetch_token_and_userinfo(code)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Falha ao autenticar com Gov.br: {str(e)}"
        )
    
    # 1. Provisiona ou faz login do usuário externo (Cidadão)
    cidadao = await login_ou_cadastrar_via_govbr(
        db,
        tenant_id=tenant_id,
        cpf=user_info["cpf"],
        nome=user_info["nome"],
        email=user_info["email"],
        nivel_govbr=user_info["nivel_confiabilidade"],
    )

    # 2. Gera o JWT Padrão do Aprimora para cidadão
    secret = await get_jwt_secret(db)
    jwt_payload = build_payload(
        cidadao.id,
        cidadao.email or f"{cidadao.cpf_cnpj}@cidadao.local",
        tenant_id=tenant_id
    )
    token = encode_token(jwt_payload, secret)

    # 3. Define o Cookie de Sessão
    res = RedirectResponse(url="/portal/painel")
    res.set_cookie(
        key="aprimora_token",
        value=token,
        max_age=_settings.jwt_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=True,
    )
    
    # Em produção, redireciona para o painel do Cidadão no Frontend
    return res


@router.get("/mock-login")
async def govbr_mock_login(state: str, request: Request):
    """Página fake para ambiente de dev pular a tela do governo"""
    flow = GovBrOAuthFlow(redirect_uri="")
    if not flow.is_mock():
        raise HTTPException(status_code=404, detail="Mock desabilitado")
    
    # Força um CPF de teste
    fake_code = "mock-code-12345678909"
    callback_url = request.url_for("govbr_callback").include_query_params(code=fake_code, state=state)
    return RedirectResponse(url=str(callback_url))
