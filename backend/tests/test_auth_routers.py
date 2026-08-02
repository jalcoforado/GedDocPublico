"""Testes para OAuth routers (PR-F Phases 4-5).

Testa os endpoints:
- GET /auth/google → redireciona para Google consent screen
- GET /auth/google/callback → troca código por tokens, cria Google Doc, redireciona

Usa app.dependency_overrides para mockar identidade do usuário e Redis.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi import Depends, HTTPException, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.auth.jwt import build_payload, encode_token, get_jwt_secret
from app.main import app
from app.models import Usuario
from app.routers.auth import get_redis
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine, *, prefix="auth-test"):
    slug = _slug(prefix)
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref Auth Test",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    return tenant


async def _su_id(engine, tenant_id: int) -> int:
    """Id do super-usuário do tenant."""
    async with _sm(engine)() as s:
        return int((await s.execute(
            text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
            {"t": tenant_id},
        )).scalar_one())


async def _get_usuario(engine, usuario_id: int) -> Usuario:
    """Carrega usuário completo."""
    async with _sm(engine)() as s:
        return (await s.execute(
            select(Usuario).where(Usuario.id == usuario_id)
        )).scalar_one()


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.minuta WHERE tenant_id=:t",
            "DELETE FROM protocolos.minuta_historico WHERE tenant_id=:t",
            "DELETE FROM protocolos.processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.assunto WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


@pytest_asyncio.fixture
async def auth_setup(admin_engine):
    """Provisiona tenant com super-usuário."""
    tenant = await _provisionar(admin_engine)
    su_id = await _su_id(admin_engine, tenant.id)
    try:
        yield {
            "tenant_id": tenant.id,
            "tenant_slug": tenant.slug,
            "su_id": su_id,
        }
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest_asyncio.fixture
async def admin_token(admin_engine, auth_setup):
    """Gera JWT token para super-usuário do tenant."""
    s = auth_setup
    user = await _get_usuario(admin_engine, s["su_id"])

    # Gera token JWT igual ao login
    async with _sm(admin_engine)() as db:
        secret = await get_jwt_secret(db)
        jwt_payload = build_payload(user.id, user.email, tenant_id=s["tenant_id"])
        token = encode_token(jwt_payload, secret)

    return token


def _clear_overrides():
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    _clear_overrides()
    from app.database import engine as app_engine
    await app_engine.dispose()


@pytest.mark.asyncio
async def test_initiate_google_oauth_redirect(
    admin_engine, auth_setup, client, admin_token, redis_client
):
    """GET /auth/google redirects to Google consent screen."""
    from app.auth.deps import _resolve_current_user

    s = auth_setup

    # Override dependencies
    arreio_tenant_http(s["tenant_id"], s["tenant_slug"])
    app.dependency_overrides[get_redis] = lambda: redis_client

    # Override get_current_user to bypass must_change_password gate in tests
    async def mock_get_current_user_no_gate(user: Usuario = Depends(_resolve_current_user)) -> Usuario:
        """Skip must_change_password gate for testing."""
        return user

    app.dependency_overrides[get_current_user] = mock_get_current_user_no_gate

    # Create a proper host header matching the test tenant's slug
    # This ensures TenantMiddleware resolves to the correct tenant
    host_header = f"{s['tenant_slug']}.aprimora.local"

    response = await client.get(
        "/api/v2/auth/google?minuta_id=123&processo_id=456",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "Host": host_header,  # Set Host for TenantMiddleware
        },
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert "accounts.google.com" in response.headers["location"]
    assert "state=" in response.headers["location"]


@pytest.mark.asyncio
async def test_initiate_google_oauth_missing_auth(client):
    """GET /auth/google without auth → 401."""
    _clear_overrides()

    response = await client.get("/api/v2/auth/google?minuta_id=123&processo_id=456")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_google_credential_status_no_credentials(client, auth_setup, admin_token):
    """GET /users/me/google-credential with no credentials → 404."""
    s = auth_setup

    # Override tenant_id dependency (arreio SEC-RLS-00B: tenant tambem na session)
    arreio_tenant_http(s["tenant_id"], s["tenant_slug"])

    response = await client.get(
        "/api/v2/users/me/google-credential",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
