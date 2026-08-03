"""Contratação de módulos pelo admin de plataforma — só platform admin, e não
vaza entre tenants.

**Reescrito em SEC-01A.** Antes, `client_plataforma` combinava
`monkeypatch.setenv("PLATFORM_ADMIN_EMAILS", ...)` com
`dependency_overrides[get_current_user]`, porque o gate era uma comparação de
e-mail sobre a identidade municipal. Nenhuma dessas duas peças sobreviveu: o
gate agora exige token administrativo RS256 do IdP dedicado e um principal em
`aprimora_py.platform_principal`, sobre uma conexão própria. O cliente de
plataforma passou a mandar um token **de verdade**, emitido pelos fixtures de
SEC-00 e validado pela cadeia real — sem `dependency_overrides` sobre o gate,
que faria o teste concordar consigo mesmo.

`client_admin` continua sendo um servidor municipal comum, e continua tomando
403 — só que agora por não ter token administrativo nenhum, e não por o e-mail
dele estar fora de uma lista.

`tenant_id_default` ancora no tenant `sobral`: é o único tenant com os 5
módulos contratáveis contratados garantidos — pelo backfill da migration
0073 se o banco já tinha esse tenant no momento em que ela rodou, ou por
`seed_bootstrap.garantir_contratacao_inicial` se não tinha (banco limpo,
caso do CI: migrations rodam antes de qualquer tenant existir). Quem
garante a contratação de ponta a ponta é o seed, não o backfill sozinho —
o backfill não alcança tenant criado depois dele (mesmo motivo documentado
em `test_modulos_me.py`). Só o teste read-only
(`test_platform_admin_lista_catalogo`) usa essa fixture — o teste que
escreve (`test_descontratar_e_recontratar`) roda em tenant isolado da
fixture `two_tenants` de `conftest.py`, para não deixar `sobral` num estado
quebrado para o resto da suíte se uma asserção falhar no meio do teste.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
async def token_admin_municipal(admin_engine, tenant_id_default) -> str:
    """Token MUNICIPAL legítimo do super-usuário de `sobral` (admin@local.test).

    Não é um token inventado: sai de `build_payload`/`encode_token`, a mesma
    cadeia que emite a sessão de qualquer servidor de prefeitura, e é assinado
    com o segredo real do ambiente. É a credencial mais forte que existe do lado
    municipal — e é exatamente por isso que serve de teste: se ela abrisse a
    fronteira de plataforma, a separação de realms não existiria.
    """
    from app.auth.jwt import build_payload, encode_token, get_jwt_secret

    async with _sm(admin_engine)() as s:
        usuario = (
            await s.execute(
                select(Usuario).where(
                    Usuario.tenant_id == tenant_id_default,
                    Usuario.email == "admin@local.test",
                )
            )
        ).scalar_one()
        segredo = await get_jwt_secret(s)
    return encode_token(
        build_payload(usuario.id, usuario.email, tenant_id_default), segredo
    )


@pytest_asyncio.fixture
async def client_plataforma(principal_ativo, plataforma_configurada):
    """Operador de plataforma **real**: token RS256 do IdP de teste + principal
    ativo, validados pela cadeia de produção.

    O gate não é sobrescrito. Todo request deste cliente atravessa
    `validar_token_plataforma` e a consulta ao principal, e roda na conexão do
    papel `aprimora_platform` — que é onde um grant faltando apareceria.
    """
    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        yield c
    from app.database import engine as app_engine
    await app_engine.dispose()


@pytest.mark.asyncio
async def test_su_de_prefeitura_nao_e_admin_de_plataforma(
    token_admin_municipal, tenant_id_default, plataforma_configurada
):
    """Super-usuário de prefeitura NÃO opera a plataforma, e agora nem chega
    perto: com a fronteira **inteiramente configurada e viva**, o token
    municipal mais poderoso que existe é recusado como **401** — não
    autenticado neste realm.

    O código mudou de 403 para 401 de propósito, e a diferença importa: antes,
    o usuário era autenticado pela cadeia municipal e depois reprovado numa
    lista de e-mails (403 = "conheço você, não deixo"). Hoje a credencial
    municipal não é sequer uma credencial aqui (401 = "isto não é um token meu").
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(
            f"/api/v2/admin/tenants/{tenant_id_default}/modulos",
            headers={"Authorization": f"Bearer {token_admin_municipal}"},
        )
    assert r.status_code == 401, r.text
    from app.database import engine as app_engine

    await app_engine.dispose()


@pytest.mark.asyncio
async def test_sem_token_administrativo_e_401(tenant_id_default, plataforma_configurada):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(f"/api/v2/admin/tenants/{tenant_id_default}/modulos")
    assert r.status_code == 401
    from app.database import engine as app_engine

    await app_engine.dispose()


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
