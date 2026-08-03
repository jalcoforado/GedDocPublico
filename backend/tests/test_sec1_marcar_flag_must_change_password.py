"""SEC-1 Commit 3 — marca/libera must_change_password nos fluxos de senha.

Cobre 12 cenários do escopo:

Marcação (true):
  1. Provisionamento cria admin inicial com flag=true.
  2. Reset administrativo marca flag=true.
  3. Reset administrativo limpa MD5 legado.
  4. Reset administrativo não grava senha/hash/token no audit_log.
  5. POST /usuarios cria usuário com flag=true.

Liberação (false):
  6. Alteração própria de senha marca flag=false.
  7. Alteração própria de senha limpa MD5 legado.
  8. Alteração própria mantém usuário autenticável com bcrypt.
  9. Alteração própria não registra senha/hash/token no audit.

Integração com o guard (Commit 2):
 10. Usuário com flag=true consegue chamar /auth/alterar-senha (whitelist).
 11. Após trocar senha, mesmo usuário acessa rota de negócio.
 12. Usuário sem flag continua sem mudança de comportamento.

Reaproveita conftest (admin_engine, two_tenants).
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import _resolve_current_user
from app.auth.password import hash_md5, hash_password, verify_password
from app.database import get_db
from app.main import app
from app.models import Usuario
from app.services.conta import ContaError, alterar_senha
from app.services.provisioning_tenant import provisionar_tenant
from app.services.usuario_senha import resetar_senha_usuario
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


def _payload_contem_segredo(payload: dict | None, *segredos: str) -> bool:
    """Procura strings sensíveis em qualquer valor textual do payload do audit."""
    if not payload:
        return False
    import json

    blob = json.dumps(payload)
    for seg in segredos:
        if seg and seg in blob:
            return True
    # Heurística: hashes bcrypt sempre começam com $2 (versão a/b/y) — bloqueia
    # qualquer registro acidental de senha_bcrypt.
    if "$2a$" in blob or "$2b$" in blob or "$2y$" in blob:
        return True
    return False


# ============================================================
# 1. Provisionamento — admin inicial com flag=true
# ============================================================


async def test_provisionamento_cria_admin_com_flag_true(admin_engine):
    slug = _slug("sec1c3p")
    cpf = uuid.uuid4().hex[:11]
    async with _sm(admin_engine)() as s:
        tenant, senha_temp = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref Prov",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=cpf,
            plano="basico",
        )
    try:
        async with _sm(admin_engine)() as s:
            admin = (
                await s.execute(
                    select(Usuario).where(Usuario.tenant_id == tenant.id)
                )
            ).scalar_one()
        assert admin.must_change_password is True
        assert admin.senha == ""  # MD5 vazio
        assert admin.senha_bcrypt is not None and admin.senha_bcrypt.startswith("$2")
        # Senha temporária deve continuar válida via bcrypt
        ok, _ = verify_password(
            senha_temp, bcrypt_hash=admin.senha_bcrypt, md5_hash=None
        )
        assert ok is True
    finally:
        await _cleanup_tenant(admin_engine, tenant.id)


# ============================================================
# 2-4. Reset administrativo
# ============================================================


@pytest_asyncio.fixture
async def tenant_com_su(admin_engine):
    slug = _slug("sec1c3r")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref Reset",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    async with _sm(admin_engine)() as s:
        su = (
            await s.execute(
                select(Usuario).where(Usuario.tenant_id == tenant.id)
            )
        ).scalar_one()
        # Para os testes 2/3/4 queremos um "alvo do reset" diferente do SU,
        # e sem flag=true previamente (simula servidor já em uso).
        alvo_id = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO utils.usuario "
                        "  (tenant_id, nome, email, senha, senha_bcrypt, cpf, "
                        "   ativo, excluido, must_change_password) "
                        "VALUES (:t, 'Alvo', :e, :md5, :bc, :cpf, true, false, false) "
                        "RETURNING id"
                    ),
                    {
                        "t": tenant.id,
                        "e": f"alvo-{uuid.uuid4().hex[:8]}@t.local",
                        "md5": hash_md5("senha-antiga"),
                        "bc": hash_password("senha-antiga"),
                        "cpf": uuid.uuid4().hex[:11],
                    },
                )
            ).scalar_one()
        )
        await s.commit()
    try:
        yield {"tenant_id": tenant.id, "su_id": su.id, "alvo_id": alvo_id}
    finally:
        await _cleanup_tenant(admin_engine, tenant.id)


async def test_reset_administrativo_marca_flag_true(admin_engine, tenant_com_su):
    s_ctx = tenant_com_su
    async with _sm(admin_engine)() as s:
        user, senha_temp = await resetar_senha_usuario(
            s,
            usuario_id=s_ctx["alvo_id"],
            tenant_id=s_ctx["tenant_id"],
            ator_usuario_id=s_ctx["su_id"],
        )
    assert user.must_change_password is True
    assert isinstance(senha_temp, str) and len(senha_temp) >= 12


async def test_reset_administrativo_limpa_md5(admin_engine, tenant_com_su):
    s_ctx = tenant_com_su
    async with _sm(admin_engine)() as s:
        user, _ = await resetar_senha_usuario(
            s,
            usuario_id=s_ctx["alvo_id"],
            tenant_id=s_ctx["tenant_id"],
            ator_usuario_id=s_ctx["su_id"],
        )
    assert user.senha == ""
    assert user.senha_bcrypt is not None and user.senha_bcrypt.startswith("$2")


async def test_reset_administrativo_nao_grava_senha_no_audit(
    admin_engine, tenant_com_su
):
    s_ctx = tenant_com_su
    async with _sm(admin_engine)() as s:
        _, senha_temp = await resetar_senha_usuario(
            s,
            usuario_id=s_ctx["alvo_id"],
            tenant_id=s_ctx["tenant_id"],
            ator_usuario_id=s_ctx["su_id"],
        )
    async with _sm(admin_engine)() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT payload FROM aprimora_py.audit_log "
                    "WHERE tenant_id=:t AND acao='usuario.senha_resetada' "
                    "ORDER BY id DESC LIMIT 1"
                ),
                {"t": s_ctx["tenant_id"]},
            )
        ).all()
    assert len(rows) == 1
    payload = rows[0][0]
    assert not _payload_contem_segredo(
        payload, senha_temp, "senha-antiga"
    ), f"audit_log de reset contém segredo: {payload}"
    # Sanity: marca de auditoria do Commit 3 está presente.
    assert payload.get("must_change_password_set") is True


# ============================================================
# 5. POST /usuarios — flag=true
# ============================================================


@pytest_asyncio.fixture
async def tenant_su_unidade(admin_engine):
    slug = _slug("sec1c3post")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref Post",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    # SU nasce com must_change_password=true (Commit 3). Para testar POST
    # /usuarios precisamos simular que ele já trocou a senha — caso contrário
    # o gate (Commit 2) bloqueia qualquer rota de negócio.
    async with _sm(admin_engine)() as s:
        await s.execute(
            text(
                "UPDATE utils.usuario SET must_change_password=false "
                "WHERE tenant_id=:t"
            ),
            {"t": tenant.id},
        )
        await s.commit()
    async with _sm(admin_engine)() as s:
        su = (
            await s.execute(
                select(Usuario).where(Usuario.tenant_id == tenant.id)
            )
        ).scalar_one()
        uid = int(
            (
                await s.execute(
                    text(
                        "SELECT id FROM utils.unidade_trabalho "
                        "WHERE tenant_id=:t LIMIT 1"
                    ),
                    {"t": tenant.id},
                )
            ).scalar_one()
        )
    try:
        yield {
            "tenant_id": tenant.id,
            "tenant_slug": tenant.slug,
            "su_id": su.id,
            "unidade_id": uid,
        }
    finally:
        await _cleanup_tenant(admin_engine, tenant.id)


def _as_usuario(_admin_engine, usuario_id: int, tenant_id: int, tenant_slug: str):
    """Overrides para os testes HTTP:

    - `arreio_tenant_http`: instala `get_db`/`require_tenant_id`/
      `require_tenant_slug` falando o MESMO tenant. A sessão é a REAL
      (`SessionLocal`), com `session.info["tenant_id"]` da fixture — antes
      vinha de `admin_engine` (`ged_user`, BYPASSRLS), o que desligava a RLS
      nestes testes independentemente do `DATABASE_URL` e os tornava incapazes
      de falhar por isolamento (inventário §8.8). O motivo original da gambiarra
      era real: sem o `tenant_id` correto na sessão, o `TenantMiddleware` cai no
      default `sobral` e a RLS filtra tudo. A correção é dar o tenant certo, não
      desligar a RLS.
    - `_resolve_current_user`: lê o usuário da MESMA `db` que o serviço
      vai usar, garantindo que o objeto esteja attached e que UPDATEs
      (ex: `alterar_senha` zerando a flag) persistam.
    """
    from fastapi import Depends

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


async def test_post_usuarios_cria_com_flag_true(
    admin_engine, tenant_su_unidade, client
):
    s_ctx = tenant_su_unidade
    _as_usuario(admin_engine, s_ctx["su_id"], s_ctx["tenant_id"], s_ctx["tenant_slug"])()
    r = await client.post(
        "/api/v2/usuarios",
        json={
            "nome": "Novo Servidor",
            "email": f"novo-{uuid.uuid4().hex[:8]}@t.local",
            "cpf": uuid.uuid4().hex[:11],
            "senha": "senha-temp-1",
            "id_unidade_trabalho": s_ctx["unidade_id"],
            "ativo": True,
            "cargo": "Analista",
            "grupos": [],
        },
    )
    assert r.status_code == 201, r.text
    novo_id = r.json()["id"]
    async with _sm(admin_engine)() as s:
        novo = (
            await s.execute(select(Usuario).where(Usuario.id == novo_id))
        ).scalar_one()
    assert novo.must_change_password is True
    assert novo.senha == ""  # MD5 limpo
    assert novo.senha_bcrypt and novo.senha_bcrypt.startswith("$2")
    # A senha do payload tem que continuar autenticando via bcrypt.
    ok, _ = verify_password(
        "senha-temp-1", bcrypt_hash=novo.senha_bcrypt, md5_hash=None
    )
    assert ok is True


# ============================================================
# 6-9. Alteração própria de senha
# ============================================================


@pytest_asyncio.fixture
async def usuario_flagged(admin_engine, tenant_com_su):
    """Reseta a senha do `alvo` para obter um usuário concreto em estado
    must_change_password=true com MD5 zerado e bcrypt definido."""
    s_ctx = tenant_com_su
    async with _sm(admin_engine)() as s:
        user, senha_temp = await resetar_senha_usuario(
            s,
            usuario_id=s_ctx["alvo_id"],
            tenant_id=s_ctx["tenant_id"],
            ator_usuario_id=s_ctx["su_id"],
        )
    return {
        "tenant_id": s_ctx["tenant_id"],
        "su_id": s_ctx["su_id"],
        "user_id": user.id,
        "senha_temp": senha_temp,
    }


async def test_alterar_senha_marca_flag_false(admin_engine, usuario_flagged):
    ctx = usuario_flagged
    async with _sm(admin_engine)() as s:
        u = (
            await s.execute(select(Usuario).where(Usuario.id == ctx["user_id"]))
        ).scalar_one()
        await alterar_senha(
            s, usuario=u, senha_atual=ctx["senha_temp"], nova_senha="nova-senha-1"
        )
    async with _sm(admin_engine)() as s:
        u = (
            await s.execute(select(Usuario).where(Usuario.id == ctx["user_id"]))
        ).scalar_one()
    assert u.must_change_password is False


async def test_alterar_senha_limpa_md5(admin_engine, tenant_com_su):
    """Usuário com MD5 legado (vindo de PHP/legado, sem ter passado por reset)
    troca a senha self-service. A partir daí MD5 deve estar vazio."""
    s_ctx = tenant_com_su
    async with _sm(admin_engine)() as s:
        u = (
            await s.execute(select(Usuario).where(Usuario.id == s_ctx["alvo_id"]))
        ).scalar_one()
        assert u.senha != ""  # pré-condição: tinha MD5 do hash_md5("senha-antiga")
        await alterar_senha(
            s, usuario=u, senha_atual="senha-antiga", nova_senha="nova-senha-1"
        )
    async with _sm(admin_engine)() as s:
        u = (
            await s.execute(select(Usuario).where(Usuario.id == s_ctx["alvo_id"]))
        ).scalar_one()
    assert u.senha == ""


async def test_alterar_senha_mantem_autenticavel_via_bcrypt(
    admin_engine, usuario_flagged
):
    ctx = usuario_flagged
    async with _sm(admin_engine)() as s:
        u = (
            await s.execute(select(Usuario).where(Usuario.id == ctx["user_id"]))
        ).scalar_one()
        await alterar_senha(
            s, usuario=u, senha_atual=ctx["senha_temp"], nova_senha="nova-senha-1"
        )
    async with _sm(admin_engine)() as s:
        u = (
            await s.execute(select(Usuario).where(Usuario.id == ctx["user_id"]))
        ).scalar_one()
    ok, needs = verify_password(
        "nova-senha-1", bcrypt_hash=u.senha_bcrypt, md5_hash=u.senha or None
    )
    assert ok is True
    assert needs is False
    # Senha antiga não vale mais.
    ok_velha, _ = verify_password(
        ctx["senha_temp"], bcrypt_hash=u.senha_bcrypt, md5_hash=None
    )
    assert ok_velha is False


async def test_alterar_senha_nao_grava_senha_no_audit(admin_engine, usuario_flagged):
    ctx = usuario_flagged
    async with _sm(admin_engine)() as s:
        u = (
            await s.execute(select(Usuario).where(Usuario.id == ctx["user_id"]))
        ).scalar_one()
        await alterar_senha(
            s, usuario=u, senha_atual=ctx["senha_temp"], nova_senha="nova-senha-1"
        )
    async with _sm(admin_engine)() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT payload FROM aprimora_py.audit_log "
                    "WHERE tenant_id=:t AND acao='usuario.senha_alterada' "
                    "ORDER BY id DESC LIMIT 1"
                ),
                {"t": ctx["tenant_id"]},
            )
        ).all()
    assert len(rows) == 1
    payload = rows[0][0]
    assert not _payload_contem_segredo(
        payload, ctx["senha_temp"], "nova-senha-1"
    ), f"audit_log de troca contém segredo: {payload}"
    # Marca clara de que a flag foi limpa nesta operação.
    assert payload.get("must_change_password_cleared") is True


# ============================================================
# 10-11. Integração com guard via HTTP
# ============================================================


async def test_http_flagged_consegue_chamar_alterar_senha(
    admin_engine, usuario_flagged, client
):
    """Whitelist do Commit 2: usuário com flag=true não toma 403 no
    /auth/alterar-senha — segue o fluxo até a troca real."""
    ctx = usuario_flagged
    # tenant slug do tenant_com_su
    async with _sm(admin_engine)() as s:
        slug = (
            await s.execute(
                text("SELECT slug FROM aprimora_py.tenant WHERE id=:t"),
                {"t": ctx["tenant_id"]},
            )
        ).scalar_one()
    _as_usuario(admin_engine, ctx["user_id"], ctx["tenant_id"], slug)()
    r = await client.post(
        "/api/v2/auth/alterar-senha",
        json={"senha_atual": ctx["senha_temp"], "nova_senha": "nova-senha-1"},
    )
    assert r.status_code == 204, r.text
    assert r.headers.get("X-Must-Change-Password") != "true"
    # Flag tem que estar limpa no banco agora.
    async with _sm(admin_engine)() as s:
        u = (
            await s.execute(select(Usuario).where(Usuario.id == ctx["user_id"]))
        ).scalar_one()
    assert u.must_change_password is False


async def test_http_apos_trocar_senha_acessa_rota_negocio(
    admin_engine, usuario_flagged, client
):
    """Após /auth/alterar-senha, o mesmo usuário consegue chamar uma rota
    de negócio que estava bloqueada (notificações/me)."""
    ctx = usuario_flagged
    async with _sm(admin_engine)() as s:
        slug = (
            await s.execute(
                text("SELECT slug FROM aprimora_py.tenant WHERE id=:t"),
                {"t": ctx["tenant_id"]},
            )
        ).scalar_one()
    _as_usuario(admin_engine, ctx["user_id"], ctx["tenant_id"], slug)()
    # Antes da troca: rota de negócio bloqueada com X-Must-Change-Password.
    r1 = await client.get("/api/v2/notificacoes/me")
    assert r1.status_code == 403
    assert r1.headers.get("X-Must-Change-Password") == "true"
    # Trocar a senha.
    r2 = await client.post(
        "/api/v2/auth/alterar-senha",
        json={"senha_atual": ctx["senha_temp"], "nova_senha": "nova-senha-1"},
    )
    assert r2.status_code == 204, r2.text
    # Depois: mesmo usuário acessa a rota normalmente (200).
    r3 = await client.get("/api/v2/notificacoes/me")
    assert r3.status_code == 200, r3.text
    assert "X-Must-Change-Password" not in r3.headers


# ============================================================
# 12. Usuário sem flag continua igual
# ============================================================


async def test_usuario_sem_flag_alterar_senha_sem_efeito_na_flag(admin_engine):
    """Usuário que nunca esteve em must_change_password troca a senha; a flag
    continua false. Backward compat: comportamento não muda para quem nunca
    foi marcado true."""
    slug = _slug("sec1c3clean")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref Clean",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    # Cria um usuário "normal" — flag=false direto no INSERT.
    async with _sm(admin_engine)() as s:
        uid = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO utils.usuario "
                        "  (tenant_id, nome, email, senha, senha_bcrypt, cpf, "
                        "   ativo, excluido, must_change_password) "
                        "VALUES (:t, 'Normal', :e, '', :bc, :cpf, true, false, false) "
                        "RETURNING id"
                    ),
                    {
                        "t": tenant.id,
                        "e": f"normal-{uuid.uuid4().hex[:8]}@t.local",
                        "bc": hash_password("velha"),
                        "cpf": uuid.uuid4().hex[:11],
                    },
                )
            ).scalar_one()
        )
        await s.commit()
    try:
        async with _sm(admin_engine)() as s:
            u = (
                await s.execute(select(Usuario).where(Usuario.id == uid))
            ).scalar_one()
            await alterar_senha(s, usuario=u, senha_atual="velha", nova_senha="nova-1")
        async with _sm(admin_engine)() as s:
            u = (
                await s.execute(select(Usuario).where(Usuario.id == uid))
            ).scalar_one()
        assert u.must_change_password is False
        # Senha nova autentica via bcrypt; MD5 permanece vazio.
        assert u.senha == ""
        ok, _ = verify_password(
            "nova-1", bcrypt_hash=u.senha_bcrypt, md5_hash=None
        )
        assert ok is True
    finally:
        await _cleanup_tenant(admin_engine, tenant.id)
