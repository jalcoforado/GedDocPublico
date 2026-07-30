"""load_permissions respeita a contratação de módulos — inclusive para SU.

Inclui também o teste HTTP fim-a-fim (test_http_su_sem_modulo_recebe_403) que
prova o Critical achado em review: `require_permission` retornava antes de
olhar `codigos_bloqueados` quando `is_super_usuario` era True, então o filtro
em `load_permissions` nunca chegava a barrar o SU na borda HTTP — só sumia do
menu. O gate correto fica em `auth/perms.py`, antes do bypass de SU.
"""
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user, require_tenant_id, require_tenant_slug
from app.auth.perms import require_any_permission, require_permission
from app.config import get_settings
from app.main import app
from app.models import Usuario
from app.services.modulos import contratar
from app.services.permissoes import load_permissions
from app.services.provisioning_tenant import provisionar_tenant

# O brief original hardcodeava app='sistemas' — esse valor não corresponde a
# nenhum utils.sistema ligado às 23 transações da Task 3B nesta base (o
# container roda APP_NAME=aprimora; 'sistemas' é uma linha de catálogo
# distinta, sem sistema_transacao vinculada). Com o literal errado, a query
# `Sistema.app == app` em load_permissions nunca casa, `rows` vem vazio e a
# função devolve is_super_usuario=False para QUALQUER teste aqui — inclusive
# depois do fix do Step 3. Troquei pelo padrão já usado em
# app/cli/seed_bootstrap.py e tests/test_transacoes_rbac.py:
# get_settings().app_name. Mesmo bug de fundo do já conhecido
# test_pr5a_dashboard_servicos.py / test_jwt_compat.py, mas ali é tolerado
# como falha pré-existente fora de escopo; aqui é o teste central da fatia
# — se ficar quebrado por esse motivo, "SU não bypassa contratação" nunca é
# realmente exercitado.
APP = get_settings().app_name

# A ORDEM DAS FIXTURES AQUI É LOAD-BEARING: `two_tenants` vem ANTES de
# `admin_session` em toda assinatura de teste deste arquivo. O pytest destrói
# fixtures na ordem inversa da criação, então essa ordem faz a session do teste
# ser fechada (e sua transação desfeita) ANTES de o teardown do `two_tenants`
# rodar `DELETE FROM aprimora_py.tenant`.
#
# Com a ordem invertida, o `await admin_session.rollback()` do fim de cada teste
# é o único que solta os locks — e ele não roda quando a asserção falha. O
# DELETE do teardown então espera para sempre por uma sessão `idle in
# transaction`, e a suíte inteira pendura: em 2026-07-30 isso matou dois jobs de
# CI, em tetos de 15 e de 30 minutos, sem nunca reportar qual teste falhou.
#
# O `lock_timeout` no teardown do conftest é a rede de proteção; esta ordem é o
# conserto. Não reordene por estética.


async def _cria_su(session, tenant_id: int) -> int:
    """Cria usuário + grupo nível 0 no sistema do app. Devolve o id do usuário."""
    sistema_id = (await session.execute(text(
        "SELECT id FROM utils.sistema WHERE app = :app AND excluido = false LIMIT 1"
    ), {"app": APP})).scalar_one()
    nivel_id = (await session.execute(text(
        "SELECT id FROM utils.nivel WHERE valor = 0 LIMIT 1"
    ))).scalar_one()
    uid = (await session.execute(text("""
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo)
        VALUES (:t, 'SU Modulo', :email, '', '00000000000', true, false,
                :app, 'interno')
        RETURNING id
    """), {"t": tenant_id, "email": f"su-mod-{tenant_id}@modulo.test", "app": APP})).scalar_one()
    gid = (await session.execute(text("""
        INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
        VALUES (:t, :n, :s, 'SU Modulo', false) RETURNING id
    """), {"t": tenant_id, "n": nivel_id, "s": sistema_id})).scalar_one()
    await session.execute(text("""
        INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
        VALUES (:t, :u, :g, true, false, :app)
    """), {"t": tenant_id, "u": uid, "g": gid, "app": APP})
    await session.flush()
    return uid


async def _cria_usuario_comum(session, tenant_id: int, *, codigo_transacao: str) -> int:
    """Cria usuário nível != 0 cujo grupo tem `grupo_transacao` concedendo
    `codigo_transacao`. Devolve o id do usuário.

    Existe para o teste do ramo comum: mover o filtro de módulo para dentro
    do `if is_su:` deixaria os testes de SU verdes e reabriria o acesso do
    usuário comum — só um teste que passa por `grupo_transacao` (não por
    `sistema_transacao`) prova que os dois ramos são cobertos.
    """
    sistema_id = (await session.execute(text(
        "SELECT id FROM utils.sistema WHERE app = :app AND excluido = false LIMIT 1"
    ), {"app": APP})).scalar_one()
    nivel_id = (await session.execute(text(
        "SELECT id FROM utils.nivel WHERE valor <> 0 LIMIT 1"
    ))).scalar_one()
    transacao_id = (await session.execute(text(
        "SELECT id FROM utils.transacao WHERE codigo = :c AND excluido = false LIMIT 1"
    ), {"c": codigo_transacao})).scalar_one()
    uid = (await session.execute(text("""
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo)
        VALUES (:t, 'Usuario Comum', :email, '', '22222222222', true, false,
                :app, 'interno')
        RETURNING id
    """), {"t": tenant_id, "email": f"comum-mod-{tenant_id}@modulo.test", "app": APP})).scalar_one()
    gid = (await session.execute(text("""
        INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
        VALUES (:t, :n, :s, 'Grupo Comum', false) RETURNING id
    """), {"t": tenant_id, "n": nivel_id, "s": sistema_id})).scalar_one()
    await session.execute(text("""
        INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
        VALUES (:t, :u, :g, true, false, :app)
    """), {"t": tenant_id, "u": uid, "g": gid, "app": APP})
    await session.execute(text("""
        INSERT INTO utils.grupo_transacao
            (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
        VALUES (:t, :g, :tr, true, true, true, false)
    """), {"t": tenant_id, "g": gid, "tr": transacao_id})
    await session.flush()
    return uid


@pytest.mark.asyncio
async def test_su_nao_bypassa_contratacao(two_tenants, admin_session):
    """Prova a filtragem no nível do dataclass: `load_permissions()` remove de
    `items` — para o SU — as transações de módulo não contratado.

    Isto NÃO prova, sozinho, que o gate HTTP barra o SU: até a correção do
    review, `require_permission` retornava antes de olhar `items`/
    `codigos_bloqueados` quando `is_super_usuario` era True, então este teste
    passava enquanto a rota continuava 200 para qualquer SU. Quem prova a
    propriedade fim-a-fim é `test_http_su_sem_modulo_recebe_403`, ao lado.
    """
    tid, _ = two_tenants
    uid = await _cria_su(admin_session, tid)
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()

    perms = await load_permissions(admin_session, uid, tenant_id=tid)
    codigos = {p.codigo for p in perms.items}

    assert perms.is_super_usuario is True
    assert "frota" in codigos, "módulo contratado sumiu para o SU"
    assert not {c for c in codigos if c.startswith("pagamento_")}, (
        "SU enxergou transações de módulo NÃO contratado"
    )
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_transacao_de_modulo_comum_sobrevive(two_tenants, admin_session):
    """'comum' não é contratável e nunca pode ser filtrado."""
    tid, _ = two_tenants
    uid = await _cria_su(admin_session, tid)
    await contratar(admin_session, tid, [])
    await admin_session.flush()

    perms = await load_permissions(admin_session, uid, tenant_id=tid)
    assert "dashboard" in {p.codigo for p in perms.items}
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_contratar_tudo_nao_muda_nada(two_tenants, admin_session):
    """Regressão: com os 5 contratados, o resultado é o de antes da mudança."""
    tid, _ = two_tenants
    uid = await _cria_su(admin_session, tid)
    await contratar(admin_session, tid,
                    ["protocolo", "pagamentos", "frota", "transporte", "administracao"])
    await admin_session.flush()

    perms = await load_permissions(admin_session, uid, tenant_id=tid)
    codigos = {p.codigo for p in perms.items}
    assert "frota" in codigos
    assert "processo" in codigos
    assert "pagamento_autorizar" in codigos
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_usuario_comum_nao_ve_transacao_de_modulo_nao_contratado(
    two_tenants, admin_session
):
    """Ramo comum (grupo_transacao) também respeita a contratação — não só o
    ramo SU. Se o filtro tivesse ido para dentro do `if is_su:`, este teste
    pegaria a regressão: o código continuaria em `items` e o gate deixaria
    passar."""
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota"])  # sem pagamentos
    await admin_session.flush()
    uid = await _cria_usuario_comum(
        admin_session, tid, codigo_transacao="pagamento_autorizar"
    )

    perms = await load_permissions(admin_session, uid, tenant_id=tid)
    assert perms.is_super_usuario is False
    codigos = {p.codigo for p in perms.items}
    assert "pagamento_autorizar" not in codigos, "item de módulo não contratado vazou"
    assert "pagamento_autorizar" in perms.codigos_bloqueados

    check = require_permission("pagamento_autorizar")
    with pytest.raises(HTTPException) as exc_info:
        await check(user=SimpleNamespace(id=uid), tenant_id=tid, db=admin_session)
    assert exc_info.value.status_code == 403

    await admin_session.rollback()


@pytest.mark.asyncio
async def test_require_any_permission_bloqueia_quando_todos_de_modulo_nao_contratado(
    two_tenants, admin_session
):
    """require_any_permission: se TODOS os códigos exigidos são de módulo não
    contratado, 403 — mesmo para SU."""
    tid, _ = two_tenants
    uid = await _cria_su(admin_session, tid)
    await contratar(admin_session, tid, ["frota"])  # sem pagamentos
    await admin_session.flush()

    check = require_any_permission("pagamento_autorizar", "pagamento_pagar")
    with pytest.raises(HTTPException) as exc_info:
        await check(user=SimpleNamespace(id=uid), tenant_id=tid, db=admin_session)
    assert exc_info.value.status_code == 403
    assert "não contratado" in exc_info.value.detail

    await admin_session.rollback()


@pytest.mark.asyncio
async def test_require_any_permission_passa_com_pelo_menos_um_disponivel(
    two_tenants, admin_session
):
    """require_any_permission: com pelo menos um código de módulo contratado
    (e concedido via grupo_transacao), passa — mesmo o outro código estando
    bloqueado."""
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota"])  # sem pagamentos
    await admin_session.flush()
    uid = await _cria_usuario_comum(admin_session, tid, codigo_transacao="frota")

    check = require_any_permission("pagamento_autorizar", "frota")
    user = await check(user=SimpleNamespace(id=uid), tenant_id=tid, db=admin_session)
    assert user.id == uid

    await admin_session.rollback()


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _as_user(engine, usuario_id: int, tenant_id: int, tenant_slug: str):
    """Builder de dependency_overrides emulando um usuário autenticado —
    mesmo padrão de test_pr4d_http_gates.py/test_pr5a_dashboard_servicos.py."""

    async def _get_user():
        async with _sm(engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == usuario_id))
            ).scalar_one()

    def _setup():
        app.dependency_overrides[get_current_user] = _get_user
        app.dependency_overrides[require_tenant_id] = lambda: tenant_id
        app.dependency_overrides[require_tenant_slug] = lambda: tenant_slug

    return _setup


async def _cleanup_tenant_http(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


@pytest.mark.asyncio
async def test_http_su_sem_modulo_recebe_403(admin_engine):
    """O teste que prova a propriedade fim-a-fim: SU de um tenant que não
    contratou Pagamentos bate num endpoint de Pagamentos via HTTP real e
    recebe 403 — não 200. Este é exatamente o Critical do review: antes da
    correção, `require_permission` retornava no bypass de SU antes de olhar
    `codigos_bloqueados`, e a rota respondia 200 mesmo com o módulo ausente
    do menu."""
    slug = f"modhttp{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref Modulo HTTP",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["frota"])  # sem pagamentos
            await s.commit()
        async with _sm(admin_engine)() as s:
            su_id = int((await s.execute(
                text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
                {"t": tenant.id},
            )).scalar_one())

        _as_user(admin_engine, su_id, tenant.id, tenant.slug)()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v2/pagamentos/autorizacao/fila")
        assert r.status_code == 403, r.text
        assert "não contratado" in r.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
        await _cleanup_tenant_http(admin_engine, tenant.id)
