"""Item 1.0.8 — leitura exige transação, e isso só é verificável com NÃO-SU.

Por que este arquivo existe separado das guardas estruturais
(`test_guarda_modularizacao.py`): aquelas provam que a **dependency está na
rota**; estas provam que **ela decide**. São coisas diferentes, e a segunda é
a que quebraria em produção — a primeira passaria verde com um gate que
recebesse o código errado.

E por que todo teste aqui monta usuário comum: em `auth/perms.py` o bypass de
super-usuário **retorna antes** de olhar as transações do grupo. Um teste
escrito com SU passa com o gate certo, com o gate errado e sem gate nenhum —
os três. Foi assim que 10 rotas do transporte devolveram 500 para operador
comum durante meses com a suíte verde.
"""
import uuid

import pytest
import pytest_asyncio
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

# Rota de leitura × transação que ela passou a exigir. Amostra deliberada de
# routers DIFERENTES: o gate foi aplicado em lote por script, e o erro que um
# lote produz é sistemático (o código de um router vazando para o vizinho),
# não pontual. Testar seis rotas do mesmo arquivo não pegaria isso.
ROTAS = [
    ("/api/v2/processos", "processo"),
    ("/api/v2/usuarios", "usuario"),
    ("/api/v2/audit", "auditoria"),
    ("/api/v2/unidades-trabalho", "unidadeTrabalho"),
    ("/api/v2/workflow-definitions", "workflow"),
    ("/api/v2/relatorios/processos.json", "processo"),
]

# Todos os módulos, para que a contratação nunca seja a causa do 403 — o que
# se mede aqui é permissão, e um 403 de módulo se pareceria com sucesso.
TODOS_OS_MODULOS = ["protocolo", "pagamentos", "frota", "transporte", "administracao"]


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _nivel_operacional(s) -> int:
    """get-or-create. O bootstrap garante SÓ o nível 0; em banco limpo (CI,
    instalação nova) o nível 1 não existe — supor que exista é a causa exata
    do item 1.0.65, que passava aqui por herança do legado."""
    nid = (await s.execute(text(
        "SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1"
    ))).scalar_one_or_none()
    if nid is None:
        nid = (await s.execute(text(
            "INSERT INTO utils.nivel (nivel, valor, excluido) "
            "VALUES ('Operacional', 1, false) RETURNING id"
        ))).scalar_one()
    return int(nid)


async def _cria_comum(s, tenant_id: int, codigos: list[str], sufixo: str) -> int:
    sistema_id = int((await s.execute(text(
        "SELECT id FROM utils.sistema WHERE app = :a AND excluido = false LIMIT 1"
    ), {"a": APP})).scalar_one())
    nivel_id = await _nivel_operacional(s)
    uid = int((await s.execute(text("""
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo)
        VALUES (:t, 'Operador 108', :e, '', :cpf, true, false, :a, 'ultrassecreto')
        RETURNING id
    """), {
        "t": tenant_id,
        "e": f"op-108-{sufixo}@leitura.test",
        "cpf": uuid.uuid4().hex[:11],
        "a": APP,
    })).scalar_one())
    gid = int((await s.execute(text("""
        INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
        VALUES (:t, :n, :s, :g, false) RETURNING id
    """), {"t": tenant_id, "n": nivel_id, "s": sistema_id, "g": f"Operacional 108 {sufixo}"})).scalar_one())
    await s.execute(text("""
        INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
        VALUES (:t, :u, :g, true, false, :a)
    """), {"t": tenant_id, "u": uid, "g": gid, "a": APP})
    for codigo in codigos:
        tr = (await s.execute(text(
            "SELECT id FROM utils.transacao WHERE codigo = :c AND excluido = false LIMIT 1"
        ), {"c": codigo})).scalar_one_or_none()
        assert tr is not None, (
            f"transação '{codigo}' não existe em utils.transacao — o gate desta "
            "fatia aponta para um código inexistente, o que dá 403 para todo "
            "não-SU e passa despercebido no SU"
        )
        await s.execute(text("""
            INSERT INTO utils.grupo_transacao
                (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
            VALUES (:t, :g, :tr, false, false, false, false)
        """), {"t": tenant_id, "g": gid, "tr": int(tr)})
    await s.commit()
    return uid


def _autentica(engine, usuario_id: int, tenant_id: int, tenant_slug: str) -> None:
    async def _get_user():
        async with _sm(engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == usuario_id))
            ).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, tenant_slug)


@pytest_asyncio.fixture
async def cenario(admin_engine):
    """Um tenant com todos os módulos e três sujeitos: o SU do provisionamento,
    um operador COM as transações de leitura e um operador SEM nenhuma."""
    slug = f"leitura{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Leitura", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, TODOS_OS_MODULOS)
            await s.commit()

        codigos = sorted({c for _, c in ROTAS})
        async with _sm(admin_engine)() as s:
            com = await _cria_comum(s, tenant.id, codigos, "com")
        async with _sm(admin_engine)() as s:
            sem = await _cria_comum(s, tenant.id, [], "sem")
        async with _sm(admin_engine)() as s:
            su = int((await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t AND email=:e"
            ), {"t": tenant.id, "e": f"{slug}@t.local"})).scalar_one())

        yield {"tenant": tenant, "com": com, "sem": sem, "su": su}
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
        async with _sm(admin_engine)() as s:
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
                await s.execute(text(stmt), {"t": tenant.id})
            await s.commit()


async def _get(engine, cenario, quem: str, caminho: str) -> int:
    t = cenario["tenant"]
    _autentica(engine, cenario[quem], t.id, t.slug)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(caminho)
    app.dependency_overrides.clear()
    return r.status_code


@pytest.mark.asyncio
@pytest.mark.parametrize("caminho,codigo", ROTAS)
async def test_operador_sem_a_transacao_leva_403(
    admin_engine, cenario, caminho, codigo
) -> None:
    """O buraco do 1.0.8, medido pela borda HTTP: antes desta fatia, qualquer
    autenticado do tenant lia tudo isto com 200."""
    assert await _get(admin_engine, cenario, "sem", caminho) == 403, caminho


@pytest.mark.asyncio
@pytest.mark.parametrize("caminho,codigo", ROTAS)
async def test_operador_com_a_transacao_le(
    admin_engine, cenario, caminho, codigo
) -> None:
    """O par indispensável do teste acima.

    Sozinho, "sem a transação dá 403" passaria com um gate que negasse SEMPRE
    — e um gate assim é indistinguível de correto até alguém abrir a tela. É
    aqui que o CÓDIGO de cada rota é de fato verificado: o operador recebeu
    exatamente as transações da tabela `ROTAS`, então um router gateado com o
    código do vizinho reprova neste teste, não no outro.
    """
    assert await _get(admin_engine, cenario, "com", caminho) == 200, caminho


@pytest.mark.asyncio
async def test_super_usuario_continua_lendo_tudo(admin_engine, cenario) -> None:
    """Controle: a fatia é INERTE para quem é SU — que hoje é todo mundo.

    Este teste é o que sustenta a afirmação central do escopo ("ninguém perde
    acesso no dia em que isto entra"). Se ele ficasse vermelho, a fatia teria
    de ser revertida, não ajustada.
    """
    for caminho, _ in ROTAS:
        assert await _get(admin_engine, cenario, "su", caminho) == 200, caminho


@pytest.mark.asyncio
async def test_catalogo_de_formulario_segue_livre(admin_engine, cenario) -> None:
    """A outra metade da decisão, e ela também precisa de teste.

    `/estados` é a lista que preenche `<select>` em todo módulo. A decisão
    registrada é deixá-la livre ao autenticado do tenant; sem este teste,
    alguém "uniformiza" o gate num refactor futuro e quebra o formulário de
    todo grupo não-SU — sintoma que ninguém liga ao commit que o causou.
    """
    assert await _get(admin_engine, cenario, "sem", "/api/v2/estados") == 200
