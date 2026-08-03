"""SEC-1 Commit 4 — expõe must_change_password em LoginResponse e MeResponse.

Cobre 8 cenários do escopo:

Login:
  1. Login normal (flag=false) retorna must_change_password=false.
  2. Login de usuário flagged (flag=true) retorna must_change_password=true.
  3. Login de usuário flagged continua HTTP 200 + autentica normalmente
     (não é bloqueado pelo gate — o /login não passa por get_current_user).

/auth/me:
  4. /auth/me com flag=false retorna must_change_password=false.
  5. /auth/me com flag=true retorna must_change_password=true.
  6. /auth/me com flag=true NÃO é bloqueado (whitelist do Commit 2).

Segurança:
  7. Respostas de /login e /auth/me não vazam senha/senha_bcrypt/hash bcrypt.
  8. Regressão: campos antigos seguem presentes + must_change_password adicional.

Reaproveita a infra de override do Commit 3, com o arreio corrigido em
`SEC-RLS-00B`: a sessão é a REAL (`SessionLocal`), com o `tenant_id` da
fixture instalado por `arreio_tenant_http`; o resolver carrega da MESMA db.
"""
from __future__ import annotations

import uuid

import pytest_asyncio
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import _resolve_current_user
from app.auth.password import hash_password
from app.database import get_db
from app.main import app
from app.models import Usuario
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _cleanup_tenant(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
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
async def cenario(admin_engine):
    """Provisiona tenant + 2 usuários do mesmo tenant:
    - normal_id: must_change_password=false
    - flagged_id: must_change_password=true
    Ambos com senha conhecida (bcrypt apenas).
    """
    slug = _slug("sec1c4")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref C4",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    senha_plain = "senha-c4-teste"
    bcrypt_hash = hash_password(senha_plain)
    async with _sm(admin_engine)() as s:
        normal_email = f"normal-{uuid.uuid4().hex[:8]}@t.local"
        flagged_email = f"flag-{uuid.uuid4().hex[:8]}@t.local"
        normal_id = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO utils.usuario "
                        "  (tenant_id, nome, email, senha, senha_bcrypt, cpf, "
                        "   cargo, ativo, excluido, must_change_password) "
                        "VALUES (:t, 'Normal', :e, '', :bc, :c, 'Analista', "
                        "         true, false, false) "
                        "RETURNING id"
                    ),
                    {
                        "t": tenant.id, "e": normal_email,
                        "bc": bcrypt_hash, "c": uuid.uuid4().hex[:11],
                    },
                )
            ).scalar_one()
        )
        flagged_id = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO utils.usuario "
                        "  (tenant_id, nome, email, senha, senha_bcrypt, cpf, "
                        "   cargo, ativo, excluido, must_change_password) "
                        "VALUES (:t, 'Flagged', :e, '', :bc, :c, 'Analista', "
                        "         true, false, true) "
                        "RETURNING id"
                    ),
                    {
                        "t": tenant.id, "e": flagged_email,
                        "bc": bcrypt_hash, "c": uuid.uuid4().hex[:11],
                    },
                )
            ).scalar_one()
        )
        await s.commit()
    try:
        yield {
            "tenant_id": tenant.id,
            "tenant_slug": tenant.slug,
            "normal_id": normal_id,
            "normal_email": normal_email,
            "flagged_id": flagged_id,
            "flagged_email": flagged_email,
            "senha": senha_plain,
        }
    finally:
        await _cleanup_tenant(admin_engine, tenant.id)


def _login_host_header(tenant_slug: str) -> dict[str, str]:
    """Para /login: o endpoint lê `request.state.tenant_id` direto (setado
    pelo TenantMiddleware via subdomínio do Host). Não dá para override via
    Depends. Solução: enviar o Host correto e deixar o middleware resolver,
    o que também ativa RLS corretamente na session do `get_db` real."""
    return {"Host": f"{tenant_slug}.aprimora.local"}


def _setup_as_usuario(_admin_engine, usuario_id: int, tenant_id: int, tenant_slug: str):
    """Para /auth/me: override _resolve_current_user (idem testes Commit 3).

    A sessão vem de `arreio_tenant_http`, isto é, do `SessionLocal` REAL da
    aplicação com o `tenant_id` da fixture. Antes vinha de `admin_engine`
    (`ged_user`, BYPASSRLS): a RLS ficava desligada nestes testes
    independentemente do `DATABASE_URL`, e um vazamento cross-tenant não teria
    como aparecer aqui (inventário §8.8).
    """

    async def _resolver(db: AsyncSession = Depends(get_db)):
        return (
            await db.execute(select(Usuario).where(Usuario.id == usuario_id))
        ).scalar_one()

    def _setup():
        arreio_tenant_http(tenant_id, tenant_slug)
        app.dependency_overrides[_resolve_current_user] = _resolver

    return _setup


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    from app.database import engine as app_engine
    await app_engine.dispose()


# ============================================================
# 1-3. Login
# ============================================================


async def test_login_normal_retorna_flag_false(admin_engine, cenario, client):
    c = cenario
    r = await client.post(
        "/api/v2/auth/login",
        json={"email": c["normal_email"], "senha": c["senha"]},
        headers=_login_host_header(c["tenant_slug"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["must_change_password"] is False
    assert body["usuario_id"] == c["normal_id"]


async def test_login_flagged_retorna_flag_true(admin_engine, cenario, client):
    c = cenario
    r = await client.post(
        "/api/v2/auth/login",
        json={"email": c["flagged_email"], "senha": c["senha"]},
        headers=_login_host_header(c["tenant_slug"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["must_change_password"] is True
    assert body["usuario_id"] == c["flagged_id"]


async def test_login_flagged_autentica_normalmente(admin_engine, cenario, client):
    """HTTP 200 + access_token válido — login não é bloqueado pelo gate
    (o gate só age em rotas que dependem de get_current_user)."""
    c = cenario
    r = await client.post(
        "/api/v2/auth/login",
        json={"email": c["flagged_email"], "senha": c["senha"]},
        headers=_login_host_header(c["tenant_slug"]),
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("X-Must-Change-Password") != "true"
    body = r.json()
    assert body.get("access_token")
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    # Cookie HttpOnly é setado normalmente.
    assert "aprimora_token" in r.headers.get("set-cookie", "")


# ============================================================
# 4-6. /auth/me
# ============================================================


async def test_me_normal_retorna_flag_false(admin_engine, cenario, client):
    c = cenario
    _setup_as_usuario(admin_engine, c["normal_id"], c["tenant_id"], c["tenant_slug"])()
    r = await client.get("/api/v2/auth/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == c["normal_id"]
    assert body["must_change_password"] is False


async def test_me_flagged_retorna_flag_true(admin_engine, cenario, client):
    c = cenario
    _setup_as_usuario(admin_engine, c["flagged_id"], c["tenant_id"], c["tenant_slug"])()
    r = await client.get("/api/v2/auth/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == c["flagged_id"]
    assert body["must_change_password"] is True


async def test_me_flagged_nao_e_bloqueado_pelo_gate(admin_engine, cenario, client):
    c = cenario
    _setup_as_usuario(admin_engine, c["flagged_id"], c["tenant_id"], c["tenant_slug"])()
    r = await client.get("/api/v2/auth/me")
    assert r.status_code == 200, r.text  # NÃO 403
    assert "X-Must-Change-Password" not in r.headers


# ============================================================
# 7. Não vazar senha/hash
# ============================================================


_PROIBIDOS = {"senha", "senha_bcrypt", "password", "hash"}


def _assert_sem_segredos(body: dict, *, bcrypt_hash: str | None = None) -> None:
    """Falha se a response carregar qualquer campo proibido ou hash bcrypt
    no valor de algum campo string."""
    for k in body.keys():
        assert k.lower() not in _PROIBIDOS, f"campo proibido {k!r} na response"
    # Heurística: hashes bcrypt sempre começam com $2 (versão a/b/y).
    for v in body.values():
        if isinstance(v, str):
            assert not v.startswith("$2a$"), f"hash bcrypt vazou: {v!r}"
            assert not v.startswith("$2b$"), f"hash bcrypt vazou: {v!r}"
            assert not v.startswith("$2y$"), f"hash bcrypt vazou: {v!r}"
    # Verificação extra: o hash bcrypt do cenário não pode aparecer em
    # qualquer string da response.
    if bcrypt_hash:
        for v in body.values():
            if isinstance(v, str):
                assert bcrypt_hash not in v, "hash bcrypt do banco aparece na response"


async def test_responses_nao_vazam_senha_nem_hash(admin_engine, cenario, client):
    c = cenario
    # Carrega o hash bcrypt para comparação (do banco).
    async with _sm(admin_engine)() as s:
        u = (
            await s.execute(select(Usuario).where(Usuario.id == c["flagged_id"]))
        ).scalar_one()
        bcrypt_hash = u.senha_bcrypt

    # /login — via Host header, sem override de get_db.
    r_login = await client.post(
        "/api/v2/auth/login",
        json={"email": c["flagged_email"], "senha": c["senha"]},
        headers=_login_host_header(c["tenant_slug"]),
    )
    assert r_login.status_code == 200
    _assert_sem_segredos(r_login.json(), bcrypt_hash=bcrypt_hash)
    # access_token é esperado (não está na lista de proibidos).
    assert "access_token" in r_login.json()

    # /auth/me — via overrides (gate vivo, mas /me está na whitelist).
    _setup_as_usuario(admin_engine, c["flagged_id"], c["tenant_id"], c["tenant_slug"])()
    r_me = await client.get("/api/v2/auth/me")
    assert r_me.status_code == 200
    _assert_sem_segredos(r_me.json(), bcrypt_hash=bcrypt_hash)


# ============================================================
# 8. Regressão: campos antigos seguem presentes
# ============================================================


async def test_regressao_campos_antigos_continuam_em_login_e_me(
    admin_engine, cenario, client
):
    c = cenario

    # Login — via Host header (sem override de get_db).
    r_login = await client.post(
        "/api/v2/auth/login",
        json={"email": c["normal_email"], "senha": c["senha"]},
        headers=_login_host_header(c["tenant_slug"]),
    )
    login_body = r_login.json()
    for campo in (
        "access_token",
        "token_type",
        "expires_in",
        "usuario_id",
        "usuario_email",
        "nome",
        "must_change_password",
    ):
        assert campo in login_body, f"campo ausente em /login: {campo}"

    # /me
    _setup_as_usuario(admin_engine, c["normal_id"], c["tenant_id"], c["tenant_slug"])()
    r_me = await client.get("/api/v2/auth/me")
    me_body = r_me.json()
    for campo in (
        "id",
        "nome",
        "email",
        "cargo",
        "id_unidade_trabalho",
        "must_change_password",
    ):
        assert campo in me_body, f"campo ausente em /auth/me: {campo}"
