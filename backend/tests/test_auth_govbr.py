"""Testes para o fluxo de autenticação via Gov.br."""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.models import UsuarioExterno
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"

async def _provisionar(engine, *, prefix="govbr-test"):
    slug = _slug(prefix)
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref GovBr Test",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    return tenant

async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        await s.execute(text("DELETE FROM utils.usuario_externo WHERE tenant_id=:t"), {"t": tenant_id})
        for stmt in (
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


@pytest_asyncio.fixture
async def govbr_setup(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        yield {
            "tenant_id": tenant.id,
            "tenant_slug": tenant.slug,
        }
    finally:
        await _cleanup(admin_engine, tenant.id)


from tests.conftest import arreio_tenant_http

@pytest.mark.asyncio
async def test_govbr_mock_login_redirect(govbr_setup):
    """Verifica se o endpoint mock de login redireciona corretamente."""
    state = uuid.uuid4().hex
    arreio_tenant_http(govbr_setup["tenant_id"], govbr_setup["tenant_slug"])
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Tenant-Slug": govbr_setup["tenant_slug"]}
        ) as client:
            resp = await client.get(
                "/api/v2/auth/govbr/mock-login",
                params={"state": state},
                follow_redirects=False
            )
            assert resp.status_code == 307
            location = resp.headers["location"]
            assert "callback" in location
            assert "code=mock-code-12345678909" in location
            assert f"state={state}" in location
    finally:
        from app.database import engine as app_engine
        await app_engine.dispose()


@pytest.mark.asyncio
async def test_govbr_callback_provisiona_usuario_externo(govbr_setup, admin_engine):
    """Verifica se o callback intercepta o code e cria o cidadão."""
    cpf_teste = "12345678909"
    code = f"mock-code-{cpf_teste}"
    state = "some-state"
    
    arreio_tenant_http(govbr_setup["tenant_id"], govbr_setup["tenant_slug"])
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Tenant-Slug": govbr_setup["tenant_slug"]}
        ) as client:
            resp = await client.get(
                "/api/v2/auth/govbr/callback",
                params={"code": code, "state": state},
                follow_redirects=False
            )
            assert resp.status_code == 307  # Redireciona para o portal após logar
            assert resp.headers["location"] == "/portal/painel"
            assert "aprimora_token" in resp.cookies
    finally:
        from app.database import engine as app_engine
        await app_engine.dispose()

    # Confirma que o cidadão foi provisionado
    async with _sm(admin_engine)() as s:
        cidadao = (
            await s.execute(
                select(UsuarioExterno).where(
                    UsuarioExterno.cpf_cnpj == cpf_teste,
                    UsuarioExterno.tenant_id == govbr_setup["tenant_id"]
                )
            )
        ).scalar_one()

        assert cidadao is not None
        assert cidadao.login_govbr is True
        assert cidadao.nivel_govbr == "prata"  # Retornado pelo Mock
        assert cidadao.senha == ""
        assert cidadao.senha_bcrypt == ""

