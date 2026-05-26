from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Tenant, Usuario, UsuarioExterno
from .jwt import decode_token, get_jwt_secret


def get_current_tenant_id(request: Request) -> int | None:
    """Lê o tenant resolvido pelo TenantMiddleware. Devolve None se não houver.

    Use isso quando a rota *pode* funcionar sem tenant (raro). Para rotas que
    exigem tenant resolvido, use `require_tenant_id`.
    """
    return getattr(request.state, "tenant_id", None)


def require_tenant_id(request: Request) -> int:
    """Exige tenant resolvido pelo TenantMiddleware. 400 se ausente."""
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant não resolvido para este host",
        )
    return tid


def require_tenant_slug(request: Request) -> str:
    """Exige slug do tenant resolvido pelo middleware. Útil para paths de storage."""
    slug = getattr(request.state, "tenant_slug", None)
    if slug is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant não resolvido para este host",
        )
    return slug


async def get_current_tenant(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Carrega o objeto Tenant completo (1 query extra). Use só quando precisar
    de `nome`/`cor_primaria`/`logo_url` etc. Em rotas hot-path prefira
    `require_tenant_id` (sem query)."""
    tid = require_tenant_id(request)
    result = await db.execute(select(Tenant).where(Tenant.id == tid))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant não encontrado",
        )
    return tenant


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Usuario:
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

    # Defesa em profundidade (Fase 13a): se o token carrega tenant_id e o middleware
    # também resolveu um, eles devem bater. Tokens legacy/PHP sem claim passam.
    request_tenant_id = getattr(request.state, "tenant_id", None)
    token_tenant_id = payload.get("tenant_id")
    if token_tenant_id is not None and request_tenant_id is not None:
        if int(token_tenant_id) != int(request_tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token de outro tenant",
            )

    # Filtra usuário pelo tenant resolvido (defesa adicional contra token de outro tenant).
    stmt = select(Usuario).where(
        Usuario.id == payload["usuario_id"],
        Usuario.excluido.is_(False),
        Usuario.ativo.is_(True),
    )
    if request_tenant_id is not None:
        stmt = stmt.where(Usuario.tenant_id == request_tenant_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    # Para o logging middleware (Fase 33)
    request.state.usuario_id = user.id
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

    request_tenant_id = getattr(request.state, "tenant_id", None)
    token_tenant_id = payload.get("tenant_id")
    if token_tenant_id is not None and request_tenant_id is not None:
        if int(token_tenant_id) != int(request_tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token de outro tenant",
            )

    stmt = select(UsuarioExterno).where(
        UsuarioExterno.id == payload["cidadao_id"],
        UsuarioExterno.excluido.is_(False),
        UsuarioExterno.ativo.is_(True),
    )
    if request_tenant_id is not None:
        stmt = stmt.where(UsuarioExterno.tenant_id == request_tenant_id)
    result = await db.execute(stmt)
    cidadao = result.scalar_one_or_none()
    if cidadao is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cidadão not found or inactive",
        )
    request.state.usuario_id = cidadao.id  # observability (Fase 33)
    return cidadao
