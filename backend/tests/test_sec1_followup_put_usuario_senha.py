"""SEC-1 follow-up — PUT /usuarios/{id} com senha força troca obrigatória.

Cobre 7 cenários:

1. PUT com `senha` preenchida → must_change_password=true, MD5 zerado,
   bcrypt atualizado.
2. Senha nova autentica via bcrypt; senha antiga não vale mais.
3. Login com a nova senha retorna `must_change_password=true` no body.
4. audit_log registra `usuario.senha_alterada_por_admin` SEM
   senha/hash/CPF/e-mail/nome.
5. PUT sem `senha` não mexe na flag e não registra audit de senha.
6. Cross-tenant continua 404; flag do alvo não muda.
7. Sem permissão `usuario.atualizar` continua 403; flag não muda.

Reaproveita conftest (`admin_engine`) e os helpers do
`test_sec1_marcar_flag_must_change_password` (replicados localmente para
manter cada arquivo de teste autônomo — segue padrão dos outros SEC-1).
"""
from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import _resolve_current_user
from app.auth.password import hash_md5, hash_password, verify_password
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


def _payload_contem_pii(payload: dict | None, *segredos: str) -> bool:
    """Procura segredos/PII no payload do audit_log. Bloqueia também hashes
    bcrypt (heurística por prefixo $2a/$2b/$2y) — qualquer um seria leak."""
    if not payload:
        return False
    blob = json.dumps(payload)
    for seg in segredos:
        if seg and seg in blob:
            return True
    if "$2a$" in blob or "$2b$" in blob or "$2y$" in blob:
        return True
    return False


# ----------------------------------------------------------------------
# Fixture base: tenant + SU já com flag liberada + alvo "normal"
# ----------------------------------------------------------------------


@pytest_asyncio.fixture
async def tenant_su_alvo(admin_engine):
    """Cria tenant + admin (SU). Limpa a flag do SU para que ele consiga chamar
    rotas de negócio (Commit 2 bloquearia caso contrário). Insere um servidor
    "alvo" com MD5 + bcrypt + flag=false para que possamos validar
    explicitamente que o PUT marca a flag e zera MD5."""
    slug = _slug("sec1fup")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref Follow-up",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
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
        alvo_email = f"alvo-{uuid.uuid4().hex[:8]}@t.local"
        alvo_id = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO utils.usuario "
                        "  (tenant_id, nome, email, senha, senha_bcrypt, cpf, "
                        "   ativo, excluido, must_change_password) "
                        "VALUES (:t, 'Alvo Follow-up', :e, :md5, :bc, :cpf, "
                        "        true, false, false) "
                        "RETURNING id"
                    ),
                    {
                        "t": tenant.id,
                        "e": alvo_email,
                        "md5": hash_md5("senha-antiga"),
                        "bc": hash_password("senha-antiga"),
                        "cpf": uuid.uuid4().hex[:11],
                    },
                )
            ).scalar_one()
        )
        await s.commit()
    try:
        yield {
            "tenant_id": tenant.id,
            "tenant_slug": tenant.slug,
            "su_id": su.id,
            "alvo_id": alvo_id,
            "alvo_email": alvo_email,
            "alvo_cpf": None,  # carregado abaixo só se algum teste precisar
        }
    finally:
        await _cleanup_tenant(admin_engine, tenant.id)


def _override_as(_admin_engine, *, usuario_id: int, tenant_id: int, tenant_slug: str):
    """Faz a chamada HTTP rodar como `usuario_id` no `tenant_id`/`tenant_slug`.

    A sessão é a REAL (`SessionLocal`), instalada por `arreio_tenant_http` com
    o `tenant_id` da fixture. Antes era uma sessão de `admin_engine`
    (`ged_user`, BYPASSRLS): a RLS ficava desligada aqui seja qual for o
    `DATABASE_URL`, e o cenário 6 ("cross-tenant continua 404") passava sem
    exercitar barreira nenhuma no banco (inventário §8.8).
    """

    async def _resolver(db: AsyncSession = Depends(get_db)):
        return (
            await db.execute(select(Usuario).where(Usuario.id == usuario_id))
        ).scalar_one()

    arreio_tenant_http(tenant_id, tenant_slug)
    app.dependency_overrides[_resolve_current_user] = _resolver


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()


# ----------------------------------------------------------------------
# 1. PUT com senha marca a flag, zera MD5, atualiza bcrypt
# ----------------------------------------------------------------------


async def test_put_com_senha_marca_flag_zera_md5_atualiza_bcrypt(
    admin_engine, tenant_su_alvo, client
):
    ctx = tenant_su_alvo
    _override_as(
        admin_engine,
        usuario_id=ctx["su_id"],
        tenant_id=ctx["tenant_id"],
        tenant_slug=ctx["tenant_slug"],
    )
    r = await client.put(
        f"/api/v2/usuarios/{ctx['alvo_id']}", json={"senha": "nova-pwd-admin"}
    )
    assert r.status_code == 200, r.text
    async with _sm(admin_engine)() as s:
        u = (
            await s.execute(select(Usuario).where(Usuario.id == ctx["alvo_id"]))
        ).scalar_one()
    assert u.must_change_password is True
    assert u.senha == "", "MD5 legado deveria ter sido zerado"
    assert u.senha_bcrypt and u.senha_bcrypt.startswith("$2")
    # Senha não pode aparecer na resposta.
    body = r.json()
    assert "senha" not in body
    assert "senha_bcrypt" not in body


# ----------------------------------------------------------------------
# 2. Senha nova autentica via bcrypt; antiga não vale mais
# ----------------------------------------------------------------------


async def test_put_senha_nova_autentica_via_bcrypt(
    admin_engine, tenant_su_alvo, client
):
    ctx = tenant_su_alvo
    _override_as(
        admin_engine,
        usuario_id=ctx["su_id"],
        tenant_id=ctx["tenant_id"],
        tenant_slug=ctx["tenant_slug"],
    )
    r = await client.put(
        f"/api/v2/usuarios/{ctx['alvo_id']}", json={"senha": "nova-pwd-bc"}
    )
    assert r.status_code == 200, r.text
    async with _sm(admin_engine)() as s:
        u = (
            await s.execute(select(Usuario).where(Usuario.id == ctx["alvo_id"]))
        ).scalar_one()
    ok_nova, needs = verify_password(
        "nova-pwd-bc", bcrypt_hash=u.senha_bcrypt, md5_hash=None
    )
    assert ok_nova is True
    assert needs is False
    ok_velha, _ = verify_password(
        "senha-antiga", bcrypt_hash=u.senha_bcrypt, md5_hash=None
    )
    assert ok_velha is False


# ----------------------------------------------------------------------
# 3. Login com nova senha retorna must_change_password=true no body
# ----------------------------------------------------------------------


async def test_login_apos_put_admin_devolve_flag_true(
    admin_engine, tenant_su_alvo, client
):
    """Após PUT administrativo com `senha`, o login do alvo retorna
    must_change_password=true no body (contrato do SEC-1 Commit 4 vale aqui)."""
    ctx = tenant_su_alvo
    _override_as(
        admin_engine,
        usuario_id=ctx["su_id"],
        tenant_id=ctx["tenant_id"],
        tenant_slug=ctx["tenant_slug"],
    )
    r_put = await client.put(
        f"/api/v2/usuarios/{ctx['alvo_id']}", json={"senha": "nova-pwd-login"}
    )
    assert r_put.status_code == 200, r_put.text
    # `/auth/login` lê `request.state.tenant_id` (setado pelo TenantMiddleware
    # via subdomínio do Host) — não dá pra override por Depends. Solução:
    # mandar o Host correto. Mesmo padrão do test_sec1_login_me_flag.
    r_login = await client.post(
        "/api/v2/auth/login",
        json={"email": ctx["alvo_email"], "senha": "nova-pwd-login"},
        headers={"Host": f"{ctx['tenant_slug']}.aprimora.local"},
    )
    assert r_login.status_code == 200, r_login.text
    assert r_login.json().get("must_change_password") is True


# ----------------------------------------------------------------------
# 4. audit_log registra usuario.senha_alterada_por_admin SEM segredos/PII
# ----------------------------------------------------------------------


async def test_put_com_senha_registra_audit_minimizado(
    admin_engine, tenant_su_alvo, client
):
    ctx = tenant_su_alvo
    _override_as(
        admin_engine,
        usuario_id=ctx["su_id"],
        tenant_id=ctx["tenant_id"],
        tenant_slug=ctx["tenant_slug"],
    )
    # Captura nome/cpf/email do alvo p/ assert contra leak.
    async with _sm(admin_engine)() as s:
        alvo = (
            await s.execute(select(Usuario).where(Usuario.id == ctx["alvo_id"]))
        ).scalar_one()
        alvo_nome = alvo.nome
        alvo_cpf = alvo.cpf
        alvo_email = alvo.email
    r = await client.put(
        f"/api/v2/usuarios/{ctx['alvo_id']}", json={"senha": "nova-pwd-audit"}
    )
    assert r.status_code == 200, r.text
    async with _sm(admin_engine)() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT payload FROM aprimora_py.audit_log "
                    "WHERE tenant_id=:t "
                    "  AND acao='usuario.senha_alterada_por_admin' "
                    "ORDER BY id DESC LIMIT 1"
                ),
                {"t": ctx["tenant_id"]},
            )
        ).all()
    assert len(rows) == 1, "Audit log de senha alterada por admin não foi gravado"
    payload = rows[0][0]
    # Audit minimizado: chaves esperadas e nada além delas.
    assert set(payload.keys()) == {
        "id_usuario_afetado",
        "afetado_super_usuario",
        "via",
    }, f"chaves inesperadas: {set(payload.keys())}"
    assert payload["id_usuario_afetado"] == ctx["alvo_id"]
    assert payload["afetado_super_usuario"] is False
    assert payload["via"] == "put_usuario"
    # Não pode vazar senha/hash/PII.
    assert not _payload_contem_pii(
        payload,
        "nova-pwd-audit",
        "senha-antiga",
        alvo_nome,
        alvo_cpf,
        alvo_email,
    ), f"audit_log contém segredo/PII: {payload}"


# ----------------------------------------------------------------------
# 5. PUT sem senha não toca na flag e não registra audit de senha
# ----------------------------------------------------------------------


async def test_put_sem_senha_nao_altera_flag_nem_audita_senha(
    admin_engine, tenant_su_alvo, client
):
    ctx = tenant_su_alvo
    _override_as(
        admin_engine,
        usuario_id=ctx["su_id"],
        tenant_id=ctx["tenant_id"],
        tenant_slug=ctx["tenant_slug"],
    )
    # Confere flag inicial.
    async with _sm(admin_engine)() as s:
        u0 = (
            await s.execute(select(Usuario).where(Usuario.id == ctx["alvo_id"]))
        ).scalar_one()
        md5_antes = u0.senha
        bc_antes = u0.senha_bcrypt
    assert u0.must_change_password is False
    r = await client.put(
        f"/api/v2/usuarios/{ctx['alvo_id']}", json={"cargo": "Analista Pleno"}
    )
    assert r.status_code == 200, r.text
    async with _sm(admin_engine)() as s:
        u = (
            await s.execute(select(Usuario).where(Usuario.id == ctx["alvo_id"]))
        ).scalar_one()
    assert u.must_change_password is False
    assert u.senha == md5_antes  # MD5 intacto
    assert u.senha_bcrypt == bc_antes  # bcrypt intacto
    assert u.cargo == "Analista Pleno"
    # Nenhum registro da nova ação no audit_log.
    async with _sm(admin_engine)() as s:
        count = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM aprimora_py.audit_log "
                    "WHERE tenant_id=:t "
                    "  AND acao='usuario.senha_alterada_por_admin'"
                ),
                {"t": ctx["tenant_id"]},
            )
        ).scalar_one()
    assert count == 0


# ----------------------------------------------------------------------
# 6. Cross-tenant continua 404; flag do alvo não muda
# ----------------------------------------------------------------------


async def test_put_cross_tenant_continua_404_e_nao_marca_flag(
    admin_engine, tenant_su_alvo, client
):
    """Outro tenant tenta alterar a senha do alvo via PUT — o gate de tenant
    devolve 404 (não vaza existência) e a flag do alvo não muda."""
    ctx = tenant_su_alvo
    outro_slug = _slug("sec1fup-x")
    async with _sm(admin_engine)() as s:
        outro_tenant, _ = await provisionar_tenant(
            s,
            slug=outro_slug,
            nome="Outro Tenant",
            admin_email=f"{outro_slug}@t.local",
            admin_nome="Adm X",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    async with _sm(admin_engine)() as s:
        await s.execute(
            text(
                "UPDATE utils.usuario SET must_change_password=false "
                "WHERE tenant_id=:t"
            ),
            {"t": outro_tenant.id},
        )
        await s.commit()
        su_outro = (
            await s.execute(
                select(Usuario).where(Usuario.tenant_id == outro_tenant.id)
            )
        ).scalar_one()
    try:
        _override_as(
            admin_engine,
            usuario_id=su_outro.id,
            tenant_id=outro_tenant.id,
            tenant_slug=outro_tenant.slug,
        )
        r = await client.put(
            f"/api/v2/usuarios/{ctx['alvo_id']}", json={"senha": "tentativa"}
        )
        assert r.status_code == 404
        async with _sm(admin_engine)() as s:
            u = (
                await s.execute(
                    select(Usuario).where(Usuario.id == ctx["alvo_id"])
                )
            ).scalar_one()
        assert u.must_change_password is False
        assert u.senha != ""  # MD5 antigo segue intacto
    finally:
        await _cleanup_tenant(admin_engine, outro_tenant.id)


# ----------------------------------------------------------------------
# 7. Usuário sem permissão usuario.atualizar continua 403; flag não muda
# ----------------------------------------------------------------------


async def test_put_sem_permissao_continua_403_e_nao_marca_flag(
    admin_engine, tenant_su_alvo, client
):
    """Servidor "comum" do mesmo tenant tenta alterar a senha do alvo. O gate
    `require_permission("usuario", "atualizar")` deve devolver 403 antes de
    qualquer mutação."""
    ctx = tenant_su_alvo
    # Cria um servidor comum sem grupos administrativos.
    async with _sm(admin_engine)() as s:
        comum_id = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO utils.usuario "
                        "  (tenant_id, nome, email, senha, senha_bcrypt, cpf, "
                        "   ativo, excluido, must_change_password) "
                        "VALUES (:t, 'Comum', :e, '', :bc, :cpf, true, false, false) "
                        "RETURNING id"
                    ),
                    {
                        "t": ctx["tenant_id"],
                        "e": f"comum-{uuid.uuid4().hex[:8]}@t.local",
                        "bc": hash_password("qualquer"),
                        "cpf": uuid.uuid4().hex[:11],
                    },
                )
            ).scalar_one()
        )
        await s.commit()
    _override_as(
        admin_engine,
        usuario_id=comum_id,
        tenant_id=ctx["tenant_id"],
        tenant_slug=ctx["tenant_slug"],
    )
    r = await client.put(
        f"/api/v2/usuarios/{ctx['alvo_id']}", json={"senha": "tentativa-comum"}
    )
    assert r.status_code == 403, r.text
    async with _sm(admin_engine)() as s:
        u = (
            await s.execute(select(Usuario).where(Usuario.id == ctx["alvo_id"]))
        ).scalar_one()
    assert u.must_change_password is False
    assert u.senha != ""
