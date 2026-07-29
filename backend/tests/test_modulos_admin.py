"""Contratação de módulos pelo admin de plataforma — só platform admin, e não
vaza entre tenants.

`client_plataforma`, `client_admin` e `tenant_id_default` não existem em
`conftest.py` (conferido) — definidas aqui no mesmo padrão de
`test_modulos_me.py`/`test_permissoes_modulo.py`: `AsyncClient` sobre
`ASGITransport` com `app.dependency_overrides[get_current_user]`.
`require_platform_admin` depende de `get_current_user` (não é ele mesmo
sobrescrito), então o override de `get_current_user` decide se o gate deixa
passar — é o que dá o 403 real para `client_admin` (admin comum do tenant,
e-mail fora da allowlist) e o 200 para `client_plataforma` (e-mail inserido
na allowlist via `PLATFORM_ADMIN_EMAILS` monkeypatchada).

`tenant_id_default` ancora no tenant `sobral`: é o único tenant com o
backfill de 5 módulos contratados garantido pela migration 0073 (mesmo
motivo documentado em `test_modulos_me.py`). Só o teste read-only
(`test_platform_admin_lista_catalogo`) usa essa fixture — o teste que
escreve (`test_descontratar_e_recontratar`) roda em tenant isolado da
fixture `two_tenants` de `conftest.py`, para não deixar `sobral` num estado
quebrado para o resto da suíte se uma asserção falhar no meio do teste.
"""
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import Usuario


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def tenant_id_default(admin_engine) -> int:
    async with _sm(admin_engine)() as s:
        return (await s.execute(
            text("SELECT id FROM aprimora_py.tenant WHERE slug = 'sobral'")
        )).scalar_one()


@pytest_asyncio.fixture
async def client_admin(admin_engine, tenant_id_default):
    """Admin comum do tenant `sobral` (admin@local.test) — NÃO é platform admin."""
    async with _sm(admin_engine)() as s:
        usuario_id = (await s.execute(
            text(
                "SELECT id FROM utils.usuario WHERE tenant_id = :t AND email = 'admin@local.test'"
            ),
            {"t": tenant_id_default},
        )).scalar_one()

    async def _get_user():
        async with _sm(admin_engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == usuario_id))
            ).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    from app.database import engine as app_engine
    await app_engine.dispose()


@pytest_asyncio.fixture
async def client_plataforma(monkeypatch):
    """Usuário com e-mail incluído em PLATFORM_ADMIN_EMAILS — passa o gate."""
    get_settings.cache_clear()
    monkeypatch.setenv("PLATFORM_ADMIN_EMAILS", "plataforma@aprimora.test")

    async def _get_user():
        # id=None (não amarrado a nenhum utils.usuario real): id_usuario em
        # audit_log é nullable exatamente para aceitar isso sem violar FK.
        return SimpleNamespace(id=None, email="plataforma@aprimora.test", must_change_password=False)

    app.dependency_overrides[get_current_user] = _get_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    from app.database import engine as app_engine
    await app_engine.dispose()


@pytest.mark.asyncio
async def test_listar_exige_platform_admin(client_admin, tenant_id_default):
    """Admin comum do tenant NÃO é platform admin."""
    r = await client_admin.get(f"/api/v2/admin/tenants/{tenant_id_default}/modulos")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_platform_admin_lista_catalogo(client_plataforma, tenant_id_default):
    r = await client_plataforma.get(f"/api/v2/admin/tenants/{tenant_id_default}/modulos")
    assert r.status_code == 200
    itens = r.json()
    assert len(itens) == 5, "o catálogo contratável tem 5 módulos"
    assert all(i["contratado"] for i in itens), "backfill deveria ter contratado tudo"


@pytest_asyncio.fixture
async def two_tenants_com_audit_limpo(admin_engine, two_tenants):
    """`two_tenants`, mas apagando `aprimora_py.audit_log` e
    `aprimora_py.tenant_modulo` no teardown ANTES do teardown de
    `two_tenants` (fixtures desfazem na ordem inversa da montagem — como
    esta pede `two_tenants`, ela é montada por último e desmontada
    primeiro). `definir_modulos` agora grava auditoria (Important 2 da
    revisão) e o próprio PUT grava `tenant_modulo`; a limpeza de
    `two_tenants` em `conftest.py` não conhece nenhuma das duas tabelas —
    sem isto, o `DELETE FROM aprimora_py.tenant` do teardown de
    `two_tenants` bate nas FKs `audit_log_tenant_id_fkey` /
    `tenant_modulo_tenant_id_fkey` e o teste termina em erro mesmo
    passando."""
    yield two_tenants
    tid_a, tid_b = two_tenants
    async with _sm(admin_engine)() as s:
        await s.execute(
            text("DELETE FROM aprimora_py.audit_log WHERE tenant_id IN (:a, :b)"),
            {"a": tid_a, "b": tid_b},
        )
        await s.execute(
            text("DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id IN (:a, :b)"),
            {"a": tid_a, "b": tid_b},
        )
        await s.commit()


@pytest.mark.asyncio
async def test_descontratar_e_recontratar(client_plataforma, two_tenants_com_audit_limpo):
    """Em tenant isolado (`two_tenants`), não no `sobral` compartilhado — este
    teste ESCREVE (PUT), e se uma asserção falhar entre os dois PUTs a
    restauração nunca roda. Num tenant descartável isso é inofensivo; no
    `sobral` deixaria o backfill de módulos quebrado para toda a suíte
    (inclusive test_modulos_me.py) em execuções seguintes. Não depende do
    backfill da migration 0073: já sobrescreve a lista inteira de slugs no
    primeiro PUT."""
    tenant_id, _ = two_tenants_com_audit_limpo
    r = await client_plataforma.put(
        f"/api/v2/admin/tenants/{tenant_id}/modulos",
        json={"slugs": ["protocolo", "frota", "transporte", "administracao"]},
    )
    assert r.status_code == 200
    por_slug = {i["slug"]: i["contratado"] for i in r.json()}
    assert por_slug["pagamentos"] is False

    r = await client_plataforma.put(
        f"/api/v2/admin/tenants/{tenant_id}/modulos",
        json={"slugs": ["protocolo", "pagamentos", "frota", "transporte", "administracao"]},
    )
    assert all(i["contratado"] for i in r.json())


@pytest.mark.asyncio
async def test_slug_inexistente_e_400(client_plataforma, tenant_id_default):
    r = await client_plataforma.put(
        f"/api/v2/admin/tenants/{tenant_id_default}/modulos",
        json={"slugs": ["nao-existe"]},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_comum_nao_pode_ser_contratado(client_plataforma, tenant_id_default):
    r = await client_plataforma.put(
        f"/api/v2/admin/tenants/{tenant_id_default}/modulos",
        json={"slugs": ["comum"]},
    )
    assert r.status_code == 400


TENANT_INEXISTENTE = 999999999


@pytest.mark.asyncio
async def test_listar_tenant_inexistente_e_404(client_plataforma):
    r = await client_plataforma.get(f"/api/v2/admin/tenants/{TENANT_INEXISTENTE}/modulos")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_definir_tenant_inexistente_e_404(client_plataforma):
    """Sem o 404 antecipado, `contratar()` chegaria a dar `db.add(TenantModulo(
    tenant_id=<inexistente>, ...))` — no commit isso viola a FK para
    `aprimora_py.tenant.id` e levanta `IntegrityError`, não `ValueError`, o
    que escaparia do `except` do endpoint e viraria 500 não tratado."""
    r = await client_plataforma.put(
        f"/api/v2/admin/tenants/{TENANT_INEXISTENTE}/modulos",
        json={"slugs": ["protocolo"]},
    )
    assert r.status_code == 404
