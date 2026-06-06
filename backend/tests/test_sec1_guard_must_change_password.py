"""SEC-1 Commit 2 — testes HTTP do guard must_change_password.

Cobre:

A. Whitelist (must_change_password=true acessa sem 403):
   - GET  /auth/me                    → 200
   - POST /auth/alterar-senha         → não bloqueado pelo gate (pode ser
     400 por payload, mas NÃO 403 X-Must-Change-Password)
   - GET  /permissoes/me              → 200
   - GET  /admin/me                   → 200

B. Rotas de negócio bloqueadas com must_change_password=true:
   - POST /usuarios            (via require_permission)                 → 403 + header
   - GET  /usuarios            (via get_current_user direto)            → 403 + header
   - GET  /processos/{id}      (via require_acesso_processo → get_current_user) → 403 + header
   - GET  /notificacoes/me     (via get_current_user direto)            → 403 + header
   - GET  /solicitacoes-assinatura/me/pendentes (via get_current_user)  → 403 + header

C. Regressão:
   - usuário must_change_password=false acessa normalmente
   - 401 sem token continua 401 (não vira 403)
   - header X-Must-Change-Password só aparece quando flag é true

Estratégia: override em `_resolve_current_user` (não em `get_current_user`)
para que o gate em `get_current_user` seja exercitado de verdade. Override em
`get_current_user` inteiro bypassaria o gate — comportamento legítimo dos
testes legacy, mas inútil aqui.
"""
from __future__ import annotations

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import (
    _resolve_current_user,
    require_tenant_id,
    require_tenant_slug,
)
from app.main import app
from app.models import Usuario
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("sec1g")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref SEC1G",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    return tenant


async def _criar_usuario(engine, tenant_id: int, *, flagged: bool) -> int:
    """Insere um usuário direto via SQL para evitar acoplamento ao Usuario(...)
    construtor (alguns campos default Python só preenchem em flush)."""
    suf = uuid.uuid4().hex[:8]
    async with _sm(engine)() as s:
        uid = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO utils.usuario "
                        "  (tenant_id, nome, email, senha, cpf, ativo, excluido, "
                        "   must_change_password) "
                        "VALUES (:t, :n, :e, :senha, :cpf, true, false, :flag) "
                        "RETURNING id"
                    ),
                    {
                        "t": tenant_id,
                        "n": f"SEC1G {suf}",
                        "e": f"{suf}@sec1g.local",
                        "senha": "x" * 32,  # MD5 dummy — login não é exercitado
                        "cpf": uuid.uuid4().hex[:11],
                        "flag": flagged,
                    },
                )
            ).scalar_one()
        )
        await s.commit()
    return uid


async def _cleanup(engine, tenant_id: int) -> None:
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
async def sec1_setup(admin_engine):
    """Tenant + (usuário flagged, usuário normal)."""
    tenant = await _provisionar(admin_engine)
    flagged_id = await _criar_usuario(admin_engine, tenant.id, flagged=True)
    normal_id = await _criar_usuario(admin_engine, tenant.id, flagged=False)
    try:
        yield {
            "tenant_id": tenant.id,
            "tenant_slug": tenant.slug,
            "flagged_id": flagged_id,
            "normal_id": normal_id,
        }
    finally:
        await _cleanup(admin_engine, tenant.id)


def _as_usuario(admin_engine, usuario_id: int, tenant_id: int, tenant_slug: str):
    """Override apenas _resolve_current_user: o gate em get_current_user
    permanece efetivo. require_tenant_id / require_tenant_slug também são
    override para evitar dependência do middleware de tenant."""

    async def _resolver():
        async with _sm(admin_engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == usuario_id))
            ).scalar_one()

    def _setup():
        app.dependency_overrides[_resolve_current_user] = _resolver
        app.dependency_overrides[require_tenant_id] = lambda: tenant_id
        app.dependency_overrides[require_tenant_slug] = lambda: tenant_slug

    return _setup


def _clear_overrides():
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    _clear_overrides()
    # pytest-asyncio cria event loop novo por função; o engine global da app
    # acumula conexões asyncpg ligadas ao loop morto.
    from app.database import engine as app_engine
    await app_engine.dispose()


# ============================================================
# A — Whitelist autenticada permite flagged
# ============================================================


async def test_whitelist_auth_me_permite_flagged(admin_engine, sec1_setup, client):
    s = sec1_setup
    _as_usuario(admin_engine, s["flagged_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.get("/api/v2/auth/me")
    assert r.status_code == 200, r.text
    assert "X-Must-Change-Password" not in r.headers
    body = r.json()
    assert body["id"] == s["flagged_id"]


async def test_whitelist_alterar_senha_nao_bloqueia_pelo_gate(
    admin_engine, sec1_setup, client
):
    """A rota /auth/alterar-senha deve ser alcançável; o payload pode dar
    erro de senha atual incorreta (400) — o importante é não ter 403 com
    X-Must-Change-Password (seria deadlock)."""
    s = sec1_setup
    _as_usuario(admin_engine, s["flagged_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.post(
        "/api/v2/auth/alterar-senha",
        json={"senha_atual": "errada", "nova_senha": "novasenha-1"},
    )
    assert r.status_code != 403, r.text
    assert r.headers.get("X-Must-Change-Password") != "true"


async def test_whitelist_permissoes_me_permite_flagged(
    admin_engine, sec1_setup, client
):
    s = sec1_setup
    _as_usuario(admin_engine, s["flagged_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.get("/api/v2/permissoes/me")
    assert r.status_code == 200, r.text
    assert "X-Must-Change-Password" not in r.headers


async def test_whitelist_admin_me_permite_flagged(admin_engine, sec1_setup, client):
    s = sec1_setup
    _as_usuario(admin_engine, s["flagged_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.get("/api/v2/admin/me")
    assert r.status_code == 200, r.text
    assert "X-Must-Change-Password" not in r.headers
    body = r.json()
    # Não-platform-admin (usuário de teste, não está na allowlist):
    assert body["is_platform_admin"] is False


# ============================================================
# B — Rotas de negócio bloqueadas com flag=true
# ============================================================


def _assert_blocked(r):
    assert r.status_code == 403, r.text
    assert r.headers.get("X-Must-Change-Password") == "true"


async def test_negocio_get_current_user_direto_bloqueia(
    admin_engine, sec1_setup, client
):
    """GET /usuarios usa Depends(get_current_user) direto."""
    s = sec1_setup
    _as_usuario(admin_engine, s["flagged_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.get("/api/v2/usuarios")
    _assert_blocked(r)


async def test_negocio_require_permission_bloqueia(
    admin_engine, sec1_setup, client
):
    """POST /usuarios usa Depends(require_permission(...)) que internamente
    depende de get_current_user. O gate roda primeiro."""
    s = sec1_setup
    _as_usuario(admin_engine, s["flagged_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.post(
        "/api/v2/usuarios",
        json={
            "nome": "X",
            "email": "x@x.local",
            "cpf": "12345678901",
            "senha": "x-pass-1",
            "id_unidade_trabalho": 1,
        },
    )
    _assert_blocked(r)


async def test_negocio_require_acesso_processo_bloqueia(
    admin_engine, sec1_setup, client
):
    """GET /processos/{id} usa require_acesso_processo, que injeta
    Depends(get_current_user). O gate dispara antes de tocar no processo,
    então independe do id existir."""
    s = sec1_setup
    _as_usuario(admin_engine, s["flagged_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.get("/api/v2/processos/999999")
    _assert_blocked(r)


async def test_negocio_notificacoes_me_bloqueia(admin_engine, sec1_setup, client):
    s = sec1_setup
    _as_usuario(admin_engine, s["flagged_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.get("/api/v2/notificacoes/me")
    _assert_blocked(r)


async def test_negocio_assinatura_pendentes_bloqueia(
    admin_engine, sec1_setup, client
):
    s = sec1_setup
    _as_usuario(admin_engine, s["flagged_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.get("/api/v2/solicitacoes-assinatura/me/pendentes")
    _assert_blocked(r)


# ============================================================
# C — Regressão
# ============================================================


async def test_regressao_usuario_normal_acessa_negocio(
    admin_engine, sec1_setup, client
):
    """Usuário com must_change_password=false acessa rotas de negócio
    normalmente (200 ou outro código que não 403 do gate)."""
    s = sec1_setup
    _as_usuario(admin_engine, s["normal_id"], s["tenant_id"], s["tenant_slug"])()
    # GET /notificacoes/me: gateless, retorna lista (pode estar vazia).
    r = await client.get("/api/v2/notificacoes/me")
    assert r.status_code == 200, r.text
    assert "X-Must-Change-Password" not in r.headers


async def test_regressao_401_sem_token(client):
    """Sem token, sem override: _resolve_current_user real dispara 401.
    Não pode virar 403 — o gate só roda após autenticar."""
    # Sem override de _resolve_current_user — o real é executado.
    app.dependency_overrides.clear()
    r = await client.get("/api/v2/notificacoes/me")
    assert r.status_code == 401, r.text
    assert "X-Must-Change-Password" not in r.headers


async def test_regressao_header_ausente_em_outros_403(
    admin_engine, sec1_setup, client
):
    """403 por outro motivo (sem permissão de plataforma) NÃO deve incluir
    X-Must-Change-Password — garante que o header só é set pelo gate."""
    s = sec1_setup
    # Usuário normal (não-flagged) sem allowlist de plataforma:
    _as_usuario(admin_engine, s["normal_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.get("/api/v2/admin/tenants")
    assert r.status_code == 403, r.text
    assert r.headers.get("X-Must-Change-Password") != "true"
