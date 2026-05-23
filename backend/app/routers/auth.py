from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..auth.jwt import build_payload, encode_token, get_jwt_secret
from ..auth.password import hash_password, verify_password
from ..config import get_settings
from ..database import get_db
from ..models import Usuario
from ..schemas.auth import LoginRequest, LoginResponse, MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])
_settings = get_settings()


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    result = await db.execute(
        select(Usuario).where(
            Usuario.email == payload.email,
            Usuario.excluido.is_(False),
            Usuario.ativo.is_(True),
        )
    )
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

    # Rehash transparente: popula senha_bcrypt sem tocar `senha` (PHP continua funcionando com MD5).
    if needs_rehash:
        user.senha_bcrypt = hash_password(payload.senha)
        await db.commit()

    secret = await get_jwt_secret(db)
    jwt_payload = build_payload(user.id, user.email)
    token = encode_token(jwt_payload, secret)

    # Cookie HttpOnly (Fase 9.4.3 #8) — JS não lê, mas é enviado automaticamente
    # em requests same-origin. Token continua no JSON para clientes API (curl/scripts).
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
    )


@router.post("/logout")
async def logout() -> Response:
    """Limpa o cookie de sessão. Sem efeito no JWT (que segue válido até expirar)."""
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(key="aprimora_token", path="/")
    return resp


@router.get("/me", response_model=MeResponse)
async def me(user: Usuario = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        id=user.id,
        nome=user.nome,
        email=user.email,
        cargo=user.cargo,
        id_unidade_trabalho=user.id_unidade_trabalho,
    )
