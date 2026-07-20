from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, get_current_user_no_password_gate, require_tenant_id
from ..auth.jwt import build_payload, encode_token, get_jwt_secret
from ..auth.password import hash_password, verify_password
from ..config import get_settings
from ..database import get_db
from ..models import Usuario
from ..schemas.auth import (
    AlterarSenhaRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
)
from ..services.conta import ContaError, alterar_senha
from ..services.google_oauth_flow import GoogleOAuthFlow
from ..services.minutas import criar_google_doc_para_minuta

router = APIRouter(prefix="/auth", tags=["auth"])
_settings = get_settings()


async def get_redis() -> Redis:
    """Retorna um cliente Redis para cache de estado OAuth."""
    redis_url = _settings.celery_broker_url  # redis://redis:6379/0
    return await Redis.from_url(redis_url)


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    # Login restringido ao tenant resolvido pelo middleware (Fase 13a).
    tenant_id = getattr(request.state, "tenant_id", None)
    stmt = select(Usuario).where(
        Usuario.email == payload.email,
        Usuario.excluido.is_(False),
        Usuario.ativo.is_(True),
    )
    if tenant_id is not None:
        stmt = stmt.where(Usuario.tenant_id == tenant_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    ok = False
    needs_rehash = False
    if user is not None:
        ok, needs_rehash = verify_password(
            payload.senha,
            bcrypt_hash=user.senha_bcrypt,
            md5_hash=user.senha,
        )

    if not ok or user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )

    if needs_rehash:
        user.senha_bcrypt = hash_password(payload.senha)
        await db.commit()

    secret = await get_jwt_secret(db)
    jwt_payload = build_payload(user.id, user.email, tenant_id=tenant_id)
    token = encode_token(jwt_payload, secret)

    response.set_cookie(
        key="aprimora_token",
        value=token,
        max_age=_settings.jwt_ttl_seconds,
        httponly=True,
        samesite="lax",
        path="/",
    )

    return LoginResponse(
        access_token=token,
        expires_in=_settings.jwt_ttl_seconds,
        usuario_id=user.id,
        usuario_email=user.email,
        nome=user.nome,
        must_change_password=user.must_change_password,
    )


@router.post("/logout")
async def logout() -> Response:
    """Limpa o cookie de sessão. Sem efeito no JWT (que segue válido até expirar)."""
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(key="aprimora_token", path="/")
    return resp


@router.get("/me", response_model=MeResponse)
async def me(
    user: Usuario = Depends(get_current_user_no_password_gate),
) -> MeResponse:
    # SEC-1 whitelist: o frontend lê /auth/me logo após o login para decidir
    # se redireciona para a tela de troca obrigatória — não pode ser bloqueado
    # pelo gate de must_change_password.
    return MeResponse(
        id=user.id,
        nome=user.nome,
        email=user.email,
        cargo=user.cargo,
        id_unidade_trabalho=user.id_unidade_trabalho,
        must_change_password=user.must_change_password,
    )


@router.post("/alterar-senha", status_code=status.HTTP_204_NO_CONTENT)
async def alterar_senha_endpoint(
    payload: AlterarSenhaRequest,
    request: Request,
    user: Usuario = Depends(get_current_user_no_password_gate),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Troca self-service de senha. Grava só bcrypt — desbloqueia a assinatura.

    SEC-1 whitelist: esta é justamente a rota que o usuário precisa chamar
    para sair da condição must_change_password=true. Bloqueá-la pelo gate
    seria um deadlock. A própria troca de senha zera a flag (Commit 3,
    D-ZERAR-MD5-ALTERAR) e a partir daí o usuário volta a passar pelo gate.
    """
    try:
        await alterar_senha(
            db,
            usuario=user,
            senha_atual=payload.senha_atual,
            nova_senha=payload.nova_senha,
            request=request,
        )
    except ContaError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/google")
async def initiate_google_oauth(
    minuta_id: int,
    processo_id: int,
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """Inicia o fluxo OAuth com Google.

    Query params:
    - minuta_id (required): ID da minuta a ser editada
    - processo_id (required): ID do processo associado

    Retorna: 307 Redirect para Google consent screen
    """
    oauth_flow = GoogleOAuthFlow(redis)

    try:
        auth_url = await oauth_flow.generate_oauth_url(
            user_id=user.id,
            tenant_id=tenant_id,
            minuta_id=minuta_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao iniciar OAuth: {str(e)}",
        )

    return RedirectResponse(url=auth_url, status_code=307)


@router.get("/google/callback")
async def handle_google_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """Manipula o callback do Google OAuth.

    Query params:
    - code: código de autorização do Google (sucesso)
    - state: token de state para validação (sucesso)
    - error: erro retornado pelo Google (ex: access_denied)

    Em caso de sucesso:
    1. Valida e troca código por tokens (GoogleOAuthFlow)
    2. Auto-cria Google Doc via criar_google_doc_para_minuta
    3. Redireciona para o Google Docs editor

    Em caso de erro:
    1. Redireciona para /minuta-error com código de erro
    """
    # Rejeição do usuário
    if error == "access_denied":
        return RedirectResponse(
            url="/minuta-error?error=access_denied",
            status_code=307,
        )

    # Validação de params obrigatórios
    if not code or not state:
        return RedirectResponse(
            url="/minuta-error?error=google_api_error",
            status_code=307,
        )

    oauth_flow = GoogleOAuthFlow(redis)

    try:
        # Troca código por tokens, valida state, salva credenciais
        context = await oauth_flow.handle_callback(code, state, db=db)
    except ValueError as e:
        error_msg = str(e)
        if "Sessão expirou" in error_msg:
            return RedirectResponse(
                url="/minuta-error?error=state_expired",
                status_code=307,
            )
        else:
            return RedirectResponse(
                url="/minuta-error?error=google_api_error",
                status_code=307,
            )

    # Auto-cria Google Doc e redireciona para editor
    minuta_id = context.get("minuta_id")
    try:
        minuta = await criar_google_doc_para_minuta(
            db,
            tenant_id=tenant_id,
            minuta_id=minuta_id,
            usuario_id=user.id,
        )
        # Redireciona para o Google Docs editor
        return RedirectResponse(url=minuta.google_doc_url, status_code=307)
    except HTTPException:
        return RedirectResponse(
            url="/minuta-error?error=google_api_error",
            status_code=307,
        )
    except Exception:
        return RedirectResponse(
            url="/minuta-error?error=google_api_error",
            status_code=307,
        )
