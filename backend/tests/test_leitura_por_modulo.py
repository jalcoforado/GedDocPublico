"""Tenant sem o módulo não LÊ os dados dele — a fatia de 2026-07-30.

Os dois lados da decisão daquela fatia, no mesmo arquivo de propósito: quem
mexer num vê o outro.

**Atualizado em 2026-08-11 (item 1.0.8).** O título deste arquivo terminava em
"e usuário sem permissão continua lendo", e era verdade: `require_modulo`
respondia só à contratação, então quem não tinha transação nenhuma lia tudo do
módulo contratado. O item 1.0.8 trocou essa política — a leitura agora soma
`require_permission` — e os testes daqui foram ajustados **um a um**, não em
bloco: `test_require_modulo_nao_olha_o_usuario` preserva a propriedade original
no nível da dependency, onde ela continua verdadeira, e
`test_usuario_sem_permissao_agora_leva_403` registra o que mudou. Trocar a
política sem deixar as duas escritas teria apagado a memória do porquê.

Fixtures espelham tests/test_permissoes_modulo.py::test_http_su_sem_modulo_recebe_403
(``_as_user``/``_cleanup_tenant_http``): dependency_overrides de
``get_current_user``/``require_tenant_id``/``require_tenant_slug`` sobre o app real,
não um token JWT — é o padrão já validado neste repo para bater endpoints de
negócio via HTTP com identidade fixada.
"""
import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import Usuario
from app.services.modulos import contratar
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

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
    # `/jobs` mudou de `administracao` para `protocolo` em 2026-08-11 (item
    # 1.0.8): todo job deste router é de protocolo — PDF de processo, carimbo,
    # relatório de tramitação — e as escritas sempre exigiram a transação
    # `processo`. Enquanto só o módulo era cobrado, a incoerência era
    # invisível; ao cobrar também a transação, um tenant com `administracao` e
    # sem `protocolo` deixaria de ler jobs que já não podia disparar.
    "/api/v2/jobs",
]

# Task 3: representativos das 11 rotas de administracao (o mapa completo é
# ROTAS_POR_MODULO em test_guarda_modularizacao.py). `/organograma` saiu deste
# grupo no review final (2026-07-30) — voltou a transversal, ver
# test_guarda_modularizacao.py::ENDPOINTS_LEITURA_SEM_GATE.
ROTAS_ADMINISTRACAO = [
    "/api/v2/grupos",
    "/api/v2/catalogo/niveis",
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
        arreio_tenant_http(tenant_id, tenant_slug)

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
async def tenant_sem_administracao(admin_engine):
    # Contrata `protocolo`, não nenhum — prova que o gate é específico do
    # slug "administracao", não um "tenant sem módulo nenhum" genérico.
    tenant = await _provisiona(admin_engine, "leitura-sem-adm-")
    async with _sm(admin_engine)() as s:
        await contratar(s, tenant.id, ["protocolo"])  # sem administracao
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
async def tenant_com_administracao(admin_engine):
    tenant = await _provisiona(admin_engine, "leitura-com-adm-")
    async with _sm(admin_engine)() as s:
        await contratar(s, tenant.id, ["administracao"])
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
@pytest.mark.parametrize("rota", ROTAS_ADMINISTRACAO)
async def test_sem_administracao_contratada_leitura_da_403(rota, tenant_sem_administracao):
    tenant_sem_administracao()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(rota)
    assert r.status_code == 403, f"{rota} deveria estar barrada: {r.status_code} {r.text}"


@pytest.mark.asyncio
@pytest.mark.parametrize("rota", ROTAS_ADMINISTRACAO)
async def test_com_administracao_contratada_leitura_passa(rota, tenant_com_administracao):
    """Mesma asserção forte da Task 2: `== 200`, não `!= 403` — as 3 rotas são
    listagens/catálogo, num tenant recém-provisionado devolvem 200 com lista
    vazia (ou o catálogo global de níveis, sempre não-vazio)."""
    tenant_com_administracao()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(rota)
    assert r.status_code == 200, f"{rota} deveria passar com 200: {r.status_code} {r.text}"


@pytest.mark.asyncio
async def test_require_modulo_nao_olha_o_usuario(tenant_com_protocolo_usuario_nu):
    """A PROPRIEDADE DA FATIA de 2026-07-30 — hoje verificada na DEPENDENCY.

    Até 2026-08-11 este teste batia em `GET /api/v2/processos` com um usuário
    sem permissão nenhuma e exigia **200**: era assim que se provava que
    `require_modulo` decide por contratação e não por usuário.

    O item 1.0.8 mudou a política deliberadamente (decisão do Jorge,
    2026-08-11): aquela rota agora soma `require_permission("processo")`, e o
    mesmo usuário nu leva 403 — por AUTORIZAÇÃO, não por contratação. Manter a
    asserção antiga seria travar uma política que o dono do produto trocou.

    Mas a propriedade original continua verdadeira e continua valendo a pena
    travar: `require_modulo` **não olha o usuário**. O que muda é o nível em
    que se mede. Aqui a dependency é chamada direto — sem a outra no caminho —,
    e passar com um usuário que não tem grupo, transação nem nível é
    exatamente a afirmação. Se alguém acrescentar uma consulta de permissão
    dentro de `auth/modulos.py`, este teste reprova.
    """
    from app.auth.modulos import require_modulo
    from app.database import SessionLocal

    tenant_com_protocolo_usuario_nu()
    # O `_as_user` já instalou o override; o que importa aqui é o tenant e o
    # usuário nu que ele representa.
    from app.auth.deps import get_current_user as _dep
    usuario = await app.dependency_overrides[_dep]()

    async with SessionLocal() as db:
        db.info["tenant_id"] = int(usuario.tenant_id)
        # Não levanta: contratado é contratado, independentemente de quem pede.
        await require_modulo("protocolo")(tenant_id=int(usuario.tenant_id), db=db)

        # E o controle que tira a vacuidade: a MESMA chamada, com um módulo que
        # este tenant não contratou, tem de barrar. Sem esta linha, um `_check`
        # que virasse `return None` deixaria a asserção de cima passar para
        # sempre — dizendo exatamente nada sobre a propriedade.
        with pytest.raises(HTTPException) as exc:
            await require_modulo("frota")(tenant_id=int(usuario.tenant_id), db=db)
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_usuario_sem_permissao_agora_leva_403(tenant_com_protocolo_usuario_nu):
    """O par do teste acima, e o registro do que o item 1.0.8 trocou.

    Sem este, a mudança de política ficaria só na ausência do teste antigo —
    e ausência não se lê num diff futuro. Aqui ela fica escrita: mesmo tenant,
    mesmo módulo contratado, mesma rota; o que barra agora é o usuário.
    """
    tenant_com_protocolo_usuario_nu()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/v2/processos")
    assert r.status_code == 403, r.text
    assert "Sem permissão" in r.json()["detail"], (
        "tem de ser 403 de AUTORIZAÇÃO. 'Módulo não contratado' aqui "
        f"significaria que a contratação quebrou: {r.text}"
    )
