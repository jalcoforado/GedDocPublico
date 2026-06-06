from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user_no_password_gate
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

router = APIRouter(prefix="/auth", tags=["auth"])
_settings = get_settings()


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
