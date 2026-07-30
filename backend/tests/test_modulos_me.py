"""GET /modulos/me devolve contratado ∩ permitido.

Ancorado no tenant default (`sobral`) e no `admin@local.test` semeados por
`app.cli.seed_bootstrap` — não cria tenant novo. Quem garante os 5 módulos
contratados para esse tenant é o PRÓPRIO seed_bootstrap
(`garantir_contratacao_inicial`), não o backfill da migration 0073: o
backfill só alcança tenants que já existiam quando ela rodou (ver
`test_modulos_migration.py::test_backfill_contratou_cinco_no_tenant_default`),
e em banco limpo (CI, scripts/bootstrap-db.sh) as migrations rodam antes de
qualquer tenant existir — o backfill sozinho não contrataria nada. `sobral`
é a âncora certa aqui porque é o único tenant que passa pelo seed; um
`two_tenants` recém-criado nasceria sem contratação nenhuma (não passa pelo
seed_bootstrap).

Padrão de override de dependência + fixture `http_client` que descarta o
engine global da app no teardown espelha `tests/test_pr4d_http_gates.py` e
`tests/test_pr5a_dashboard_servicos.py` — não existe fixture `client_admin`
em `conftest.py`.
"""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user, require_tenant_id
from app.main import app
from app.models import Usuario


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _as_user(engine, usuario_id: int, tenant_id: int):
    """Builder de dependency_overrides emulando um usuário autenticado — mesmo
    padrão de test_pr4d_http_gates.py/test_pr5a_dashboard_servicos.py."""

    async def _get_user():
        async with _sm(engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == usuario_id))
            ).scalar_one()

    def _setup():
        app.dependency_overrides[get_current_user] = _get_user
        app.dependency_overrides[require_tenant_id] = lambda: tenant_id

    return _setup


@pytest_asyncio.fixture
async def http_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    # pytest-asyncio cria event loop novo por função; o engine global da app
    # acumula conexões asyncpg ligadas ao loop morto. dispose() entre testes
    # evita "Event loop is closed" no próximo teste (mesmo padrão de
    # test_pr4d_http_gates.py).
    from app.database import engine as app_engine
    await app_engine.dispose()


async def test_me_exige_autenticacao(http_client):
    r = await http_client.get("/api/v2/modulos/me")
    assert r.status_code == 401


async def test_me_devolve_apenas_contratados(admin_engine, http_client):
    """admin@local.test é o SU do tenant default `sobral` (5 módulos
    contratados por `seed_bootstrap.garantir_contratacao_inicial` — não pelo
    backfill da migration 0073, que não alcança tenant criado depois dela;
    ver docstring do módulo)."""
    async with _sm(admin_engine)() as s:
        tenant_id = (await s.execute(
            text("SELECT id FROM aprimora_py.tenant WHERE slug = 'sobral'")
        )).scalar_one()
        usuario_id = (await s.execute(
            text(
                "SELECT id FROM utils.usuario "
                "WHERE tenant_id = :t AND email = 'admin@local.test'"
            ),
            {"t": tenant_id},
        )).scalar_one()

    _as_user(admin_engine, usuario_id, tenant_id)()
    r = await http_client.get("/api/v2/modulos/me")
    assert r.status_code == 200, r.text
    slugs = [i["slug"] for i in r.json()["itens"]]
    assert slugs, (
        "lista vazia é falso positivo aqui: 'comum' not in [], [] == sorted([]) "
        "e set() <= set(catalogo) são TODAS verdadeiras para slugs == [] — foi "
        "exatamente essa guarda frouxa que deixou passar o Critical do review "
        "de branch (tenant sem nenhuma linha em tenant_modulo cai em "
        "disponiveis={'comum'} e o endpoint devolve itens=[], teste verde, "
        "produto inutilizável). Um 'launcher em branco' já custou um PR "
        "neste projeto — não deixe a asserção aceitar de novo."
    )
    assert "comum" not in slugs, "'comum' não é módulo de launcher"
    catalogo = ["protocolo", "pagamentos", "frota", "transporte", "administracao"]
    assert slugs == sorted(slugs, key=catalogo.index), "itens fora da ordem do catálogo"
    assert set(slugs) <= set(catalogo)
