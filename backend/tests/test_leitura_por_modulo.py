"""Tenant sem o módulo não LÊ os dados dele — e usuário sem permissão continua lendo.

Os dois lados da decisão desta fatia, no mesmo arquivo de propósito: quem mexer
num vê o outro.

Fixtures espelham tests/test_permissoes_modulo.py::test_http_su_sem_modulo_recebe_403
(``_as_user``/``_cleanup_tenant_http``): dependency_overrides de
``get_current_user``/``require_tenant_id``/``require_tenant_slug`` sobre o app real,
não um token JWT — é o padrão já validado neste repo para bater endpoints de
negócio via HTTP com identidade fixada.
"""
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user, require_tenant_id, require_tenant_slug
from app.config import get_settings
from app.main import app
from app.models import Usuario
from app.services.modulos import contratar
from app.services.provisioning_tenant import provisionar_tenant

APP = get_settings().app_name

# Um representativo por grupo de rota. A cobertura estrutural das 58 é a
# tabela ROTAS_POR_MODULO em test_guarda_modularizacao.py (verificada contra
# `modulo_slug` de cada dependência real) — os testes HTTP abaixo são amostra
# de COMPORTAMENTO (403/200 de verdade, via ASGI), não substituto da tabela.
ROTAS_PROTOCOLO = [
    "/api/v2/processos",
    "/api/v2/assuntos",
    "/api/v2/manifestantes",
    "/api/v2/cidades",
    "/api/v2/workflow-definitions",
    "/api/v2/catalogo/prioridades",
]


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(prefixo: str) -> str:
    return f"{prefixo}{uuid.uuid4().hex[:8]}"


async def _cleanup_tenant(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
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


async def _provisiona(engine, prefixo: str):
    slug = _slug(prefixo)
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome=f"Pref {prefixo}",
            admin_email=f"{slug}@e2e.test",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    return tenant


async def _su_id(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        return int((await s.execute(
            text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
            {"t": tenant_id},
        )).scalar_one())


async def _cria_usuario_nu(engine, tenant_id: int) -> int:
    """Usuário em grupo de nível != 0, SEM nenhuma linha em grupo_transacao.

    Get-or-create de nível espelha
    tests/test_permissoes_modulo.py::_cria_usuario_comum — o bootstrap
    garante só o nível 0 (super-usuário); em banco limpo (CI) não existe
    nível operacional.
    """
    async with _sm(engine)() as s:
        sistema_id = (await s.execute(text(
            "SELECT id FROM utils.sistema WHERE app = :app AND excluido = false LIMIT 1"
        ), {"app": APP})).scalar_one()
        nivel_id = (await s.execute(text(
            "SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1"
        ))).scalar_one_or_none()
        if nivel_id is None:
            nivel_id = (await s.execute(text(
                "INSERT INTO utils.nivel (nivel, valor, excluido) "
                "VALUES ('Operacional', 1, false) RETURNING id"
            ))).scalar_one()
        uid = (await s.execute(text("""
            INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                       excluido, app, nivel_acesso_sigilo)
            VALUES (:t, 'Usuario Nu', :email, '', '33333333333', true, false,
                    :app, 'interno')
            RETURNING id
        """), {"t": tenant_id, "email": f"nu-{tenant_id}@e2e.test", "app": APP})).scalar_one()
        gid = (await s.execute(text("""
            INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
            VALUES (:t, :n, :s, 'Grupo Nu', false) RETURNING id
        """), {"t": tenant_id, "n": nivel_id, "s": sistema_id})).scalar_one()
        await s.execute(text("""
            INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
            VALUES (:t, :u, :g, true, false, :app)
        """), {"t": tenant_id, "u": uid, "g": gid, "app": APP})
        await s.commit()
        return uid


def _as_user(engine, usuario_id: int, tenant_id: int, tenant_slug: str):
    """Builder de dependency_overrides — mesmo padrão de
    test_permissoes_modulo.py::_as_user."""

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


@pytest_asyncio.fixture
async def tenant_sem_protocolo(admin_engine):
    tenant = await _provisiona(admin_engine, "leitura-sem-")
    async with _sm(admin_engine)() as s:
        await contratar(s, tenant.id, ["administracao"])  # sem protocolo
        await s.commit()
    su_id = await _su_id(admin_engine, tenant.id)
    try:
        yield _as_user(admin_engine, su_id, tenant.id, tenant.slug)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
        await _cleanup_tenant(admin_engine, tenant.id)


@pytest_asyncio.fixture
async def tenant_com_protocolo(admin_engine):
    tenant = await _provisiona(admin_engine, "leitura-com-")
    async with _sm(admin_engine)() as s:
        await contratar(s, tenant.id, ["protocolo"])
        await s.commit()
    su_id = await _su_id(admin_engine, tenant.id)
    try:
        yield _as_user(admin_engine, su_id, tenant.id, tenant.slug)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
        await _cleanup_tenant(admin_engine, tenant.id)


@pytest_asyncio.fixture
async def tenant_com_protocolo_usuario_nu(admin_engine):
    tenant = await _provisiona(admin_engine, "leitura-nu-")
    async with _sm(admin_engine)() as s:
        await contratar(s, tenant.id, ["protocolo"])
        await s.commit()
    uid = await _cria_usuario_nu(admin_engine, tenant.id)
    try:
        yield _as_user(admin_engine, uid, tenant.id, tenant.slug)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
        await _cleanup_tenant(admin_engine, tenant.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("rota", ROTAS_PROTOCOLO)
async def test_sem_protocolo_contratado_leitura_da_403(rota, tenant_sem_protocolo):
    tenant_sem_protocolo()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(rota)
    assert r.status_code == 403, f"{rota} deveria estar barrada: {r.status_code} {r.text}"


@pytest.mark.asyncio
@pytest.mark.parametrize("rota", ROTAS_PROTOCOLO)
async def test_com_protocolo_contratado_leitura_passa(rota, tenant_com_protocolo):
    """As 6 rotas são listagens/catálogo — num tenant recém-provisionado, todas
    devolvem 200 com lista vazia. `== 200` (não `!= 403`) porque a asserção
    fraca deixaria passar um 500 — inclusive o que o próprio `require_modulo`
    levanta quando `slugs_contratados` volta vazio (catálogo corrompido)."""
    tenant_com_protocolo()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(rota)
    assert r.status_code == 200, f"{rota} deveria passar com 200: {r.status_code} {r.text}"


@pytest.mark.asyncio
async def test_usuario_sem_permissao_continua_lendo(tenant_com_protocolo_usuario_nu):
    """A PROPRIEDADE DA FATIA. Se este teste falhar, alguém trocou require_modulo
    por require_permission e a fatia virou mudança de política de acesso."""
    tenant_com_protocolo_usuario_nu()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/v2/processos")
    assert r.status_code != 403, (
        "usuário sem permissão perdeu leitura — esta fatia fecha contratação, "
        "não autorização"
    )
