from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Usuario, UsuarioExterno
from .jwt import decode_token, get_jwt_secret


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    # Prefer Authorization header (Bearer); fall back to aprimora_token cookie
    # so downloads via plain <a> tags (no JS) still authenticate.
    token: str | None = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get("aprimora_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    secret = await get_jwt_secret(db)
    payload = decode_token(token, secret)

    if not payload or "usuario_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(Usuario).where(
            Usuario.id == payload["usuario_id"],
            Usuario.excluido.is_(False),
            Usuario.ativo.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


async def get_current_cidadao(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UsuarioExterno:
    """Análogo a get_current_user mas valida JWT com claim `tipo=cidadao`.

    Cookie separado `aprimora_cidadao_token` evita conflito com sessão admin
    no mesmo navegador.
    """
    token: str | None = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get("aprimora_cidadao_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = await get_jwt_secret(db)
    payload = decode_token(token, secret)
    if (
        not payload
        or "cidadao_id" not in payload
        or payload.get("tipo") != "cidadao"
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid citizen token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(UsuarioExterno).where(
            UsuarioExterno.id == payload["cidadao_id"],
            UsuarioExterno.excluido.is_(False),
            UsuarioExterno.ativo.is_(True),
        )
    )
    cidadao = result.scalar_one_or_none()
    if cidadao is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cidadão not found or inactive",
        )
    return cidadao
