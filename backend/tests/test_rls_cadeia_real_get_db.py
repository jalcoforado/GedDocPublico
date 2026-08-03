"""SEC-RLS-00B — a cadeia REAL, sem nenhuma sobreposição de `get_db`.

Este arquivo existe por causa de um buraco que o próprio `arreio_tenant_http`
abriu. O arreio é honesto — usa o `SessionLocal` real, o mesmo engine e o mesmo
papel, e só muda **de onde** vem o `tenant_id`. Mas ele sobrepõe `get_db` em 12
arquivos, e com isso o CORPO de `get_db` deixou de ser exercitado por eles:

```python
async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        tid = getattr(request.state, "tenant_id", None)   # <- estas
        if tid is not None:                               # <-  três
            session.info["tenant_id"] = int(tid)          # <- linhas
        yield session
```

Uma regressão que apagasse essas três linhas deixaria os 12 arquivos verdes e
faria **toda** sessão de produção rodar sem `app.tenant_id`. Sob RLS isso não é
um erro: é o sistema inteiro devolvendo vazio, em silêncio — a mesma classe de
falha que este PR corrigiu no `cli/backup.py` e no `limpar_jobs_antigos`.

São dois testes, e os dois são necessários:

1. o de baixo nível prova que `get_db`, alimentado por um `Request` de verdade,
   instala a GUC na conexão — é a asserção que mata a regressão das três
   linhas, e nenhuma rota consegue fazê-la de fora;
2. o HTTP prova a cadeia inteira sem sobreposição alguma de tenant: header
   `Host` → `TenantMiddleware` → `request.state` → `require_tenant_id` +
   `get_db`. É o padrão que `test_sec1_login_me_flag.py::_login_host_header`
   já usava, aplicado a uma rota de negócio tenant-scoped.
"""
from __future__ import annotations

import uuid

import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models import Usuario
from app.services.modulos import contratar
from app.services.provisioning_tenant import provisionar_tenant

ROTA = "/api/v2/tipos-anexo"


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(autouse=True)
async def descarta_engine_da_app():
    """Descarta o pool do engine global entre os testes deste arquivo.

    Estes testes usam o `SessionLocal` REAL — é o ponto do arquivo. O preço é
    que o engine global fica com conexões asyncpg amarradas à event loop do
    teste, e o `pytest-asyncio` cria uma loop nova por função: sem o dispose, o
    teste seguinte recebe conexão de uma loop morta e falha por um motivo que
    não tem nada a ver com o que ele afirma. Foi o que aconteceu na primeira
    execução — os dois passavam isolados e o segundo quebrava no par.
    """
    from app.database import engine as app_engine

    await app_engine.dispose()
    yield
    await app_engine.dispose()


def _host(slug: str) -> str:
    """Host que faz o `TenantMiddleware` resolver `slug` pelo subdomínio."""
    return f"{slug}.{get_settings().base_domain}"


# --------------------------------------------------------------------------
# 1. O corpo de `get_db`, exercitado diretamente
# --------------------------------------------------------------------------


async def test_get_db_real_instala_a_guc_na_conexao(admin_engine) -> None:
    """Alimenta o `get_db` REAL com um `Request` e confere a GUC no banco.

    Não basta checar `session.info["tenant_id"]`: isso provaria que `get_db`
    copiou o valor, não que o Postgres o recebeu. O que decide é o
    `current_setting` lido de dentro da transação — se o listener `after_begin`
    de `app/database.py` for removido, `info` continua populado e a GUC não
    existe.

    Controle negativo no fim: `Request` sem `tenant_id` no `state` produz sessão
    SEM GUC. Sem ele, o teste passaria verde num mundo em que alguém tivesse
    fixado o `SET LOCAL` num tenant constante.
    """
    tid = int(
        (
            await _sm(admin_engine)().execute(
                text("SELECT id FROM aprimora_py.tenant ORDER BY id LIMIT 1")
            )
        ).scalar_one()
    )

    def _request(state: dict) -> Request:
        # `HTTPConnection.state` lê de `scope["state"]` — é assim que o
        # TenantMiddleware deposita o tenant resolvido.
        return Request({"type": "http", "headers": [], "state": dict(state)})

    gen = get_db(_request({"tenant_id": tid}))
    sessao = await gen.__anext__()
    try:
        guc = (
            await sessao.execute(text("SELECT current_setting('app.tenant_id', true)"))
        ).scalar()
        assert str(guc or "") == str(tid), (
            f"`get_db` NÃO instalou a GUC: current_setting devolveu {guc!r}, "
            f"esperado {str(tid)!r}. Sob RLS isso faz toda consulta da "
            "aplicação devolver vazio, sem erro nenhum."
        )
        assert sessao.info.get("tenant_id") == tid
    finally:
        await sessao.rollback()
        await gen.aclose()

    # --- controle negativo ---
    gen_sem = get_db(_request({}))
    sessao_sem = await gen_sem.__anext__()
    try:
        guc_sem = (
            await sessao_sem.execute(
                text("SELECT current_setting('app.tenant_id', true)")
            )
        ).scalar()
        assert not guc_sem, (
            f"sessão SEM tenant no `request.state` veio com app.tenant_id="
            f"{guc_sem!r}. A GUC está vindo de outro lugar, e o teste acima "
            "deixou de provar que foi o `get_db` que a instalou."
        )
    finally:
        await sessao_sem.rollback()
        await gen_sem.aclose()


# --------------------------------------------------------------------------
# 2. A cadeia HTTP inteira, resolvida pelo header `Host`
# --------------------------------------------------------------------------


async def _prepara_tenant(admin_engine, prefixo: str) -> dict:
    slug = f"{prefixo}{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome=f"Pref {slug}", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    marca = f"cadeia-{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        await contratar(s, tenant.id, ["protocolo"])
        await s.execute(
            text(
                "INSERT INTO protocolos.tipo_anexo (tenant_id, tipo_anexo, excluido) "
                "VALUES (:t, :n, false)"
            ),
            {"t": tenant.id, "n": marca},
        )
        su_id = int(
            (
                await s.execute(
                    text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
                    {"t": tenant.id},
                )
            ).scalar_one()
        )
        await s.commit()
    return {"id": tenant.id, "slug": tenant.slug, "marca": marca, "su_id": su_id}


async def _limpa(admin_engine, tenant_id: int) -> None:
    async with _sm(admin_engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.tipo_anexo WHERE tenant_id=:t",
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


@pytest_asyncio.fixture
async def dois_tenants_http(admin_engine):
    a = await _prepara_tenant(admin_engine, "cadeiaa")
    b = await _prepara_tenant(admin_engine, "cadeiab")
    try:
        yield a, b
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
        await _limpa(admin_engine, a["id"])
        await _limpa(admin_engine, b["id"])


async def test_rota_de_negocio_por_host_ve_so_o_tenant_do_host(
    admin_engine, dois_tenants_http
) -> None:
    """Nenhuma sobreposição de tenant: só a identidade é injetada.

    `require_tenant_id`, `require_tenant_slug` e `get_db` ficam **intactos** —
    quem resolve o tenant é o `TenantMiddleware`, a partir do `Host`. É a única
    configuração de teste em que a cadeia de produção inteira corre.

    A asserção é simétrica de propósito. Só "A vê o de A" passaria numa rota que
    devolve tudo; só "A não vê o de B" passaria numa rota que devolve nada. O
    par, nos dois sentidos, é o que prende a propriedade.
    """
    a, b = dois_tenants_http

    async def _get_como(usuario_id: int):
        async def _get_user():
            async with _sm(admin_engine)() as s:
                return (
                    await s.execute(select(Usuario).where(Usuario.id == usuario_id))
                ).scalar_one()

        return _get_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        app.dependency_overrides[get_current_user] = await _get_como(a["su_id"])
        r_a = await c.get(ROTA, headers={"Host": _host(a["slug"])})

        app.dependency_overrides[get_current_user] = await _get_como(b["su_id"])
        r_b = await c.get(ROTA, headers={"Host": _host(b["slug"])})

    assert r_a.status_code == 200, r_a.text
    assert r_b.status_code == 200, r_b.text
    nomes_a = {t["tipo_anexo"] for t in r_a.json()}
    nomes_b = {t["tipo_anexo"] for t in r_b.json()}

    assert a["marca"] in nomes_a, (
        f"Host {_host(a['slug'])} não devolveu o tipo_anexo do próprio tenant. "
        "Se veio lista vazia, o `TenantMiddleware` caiu no tenant default e a "
        "cadeia Host -> request.state -> get_db está quebrada."
    )
    assert b["marca"] not in nomes_a, (
        f"Host {_host(a['slug'])} devolveu dado do tenant B — vazamento "
        "cross-tenant na cadeia real."
    )
    assert b["marca"] in nomes_b, (
        f"Host {_host(b['slug'])} não devolveu o tipo_anexo do próprio tenant."
    )
    assert a["marca"] not in nomes_b, (
        f"Host {_host(b['slug'])} devolveu dado do tenant A — vazamento "
        "cross-tenant na cadeia real."
    )
