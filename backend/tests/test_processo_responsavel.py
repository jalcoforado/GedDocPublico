"""Responsável-pessoa e recorte por escopo (fatia F2).

Plano: `docs/superpowers/plans/2026-09-16-aproveitamento-suite.md`.

O que cada grupo de testes existe para pegar
--------------------------------------------
**Escopo.** Um filtro de lista errado não estoura: devolve uma lista plausível.
O modo de falha que importa é vazar processo de outra pessoa sob um rótulo que
promete o contrário ("meus processos"), e o segundo é o oposto — esconder os
processos SEM responsável no recorte da unidade, que são justamente os que
precisam de alguém.

**Hierarquia.** `routers/unidades.py` tolera ciclo pré-existente por decisão
explícita. Uma recursiva ingênua giraria para sempre e derrubaria a listagem
inteira, não só o filtro. Há teste dedicado.

**Same-tenant.** A FK aponta para `utils.usuario` e NÃO filtra por tenant: sem
checagem no service, daria para atribuir um processo a um usuário de outra
prefeitura informando o id dele.

**Usuário comum.** A suíte inteira deste repositório exercita super-usuário, e
o bypass em `auth/perms.py` retorna ANTES de olhar `action` — foi assim que 10
rotas do transporte ficaram devolvendo 500 para não-SU sem nenhum teste
vermelho. O teste HTTP daqui usa usuário comum de propósito.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import (
    Assunto,
    Manifestante,
    Processo,
    TipoProcesso,
    UnidadeTrabalho,
    Usuario,
)
from app.schemas.processo import EscopoProcesso
from app.services.acoes_processo import AcaoError, atribuir_responsavel
from app.services.processos import list_processos
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _cria_usuario_comum(session, tenant_id: int, *, unidade_id: int | None) -> int:
    """Usuário nível != 0 com a transação `processo` concedida por grupo.

    Cópia deliberada do helper de `test_permissoes_modulo.py`: aquele fixa a
    transação e não aceita unidade, e aqui a lotação é o dado central. O
    get-or-create do nível repete pelo mesmo motivo registrado lá — em banco
    limpo (CI) só existe o nível 0.
    """
    sistema_id = (
        await session.execute(
            text(
                "SELECT id FROM utils.sistema WHERE app = :app AND excluido = false LIMIT 1"
            ),
            {"app": APP},
        )
    ).scalar_one()
    nivel_id = (
        await session.execute(
            text("SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1")
        )
    ).scalar_one_or_none()
    if nivel_id is None:
        nivel_id = (
            await session.execute(
                text(
                    "INSERT INTO utils.nivel (nivel, valor, excluido) "
                    "VALUES ('Operacional', 1, false) RETURNING id"
                )
            )
        ).scalar_one()
    transacao_id = (
        await session.execute(
            text(
                "SELECT id FROM utils.transacao WHERE codigo = 'processo' "
                "AND excluido = false LIMIT 1"
            )
        )
    ).scalar_one()
    uid = (
        await session.execute(
            text(
                """
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo,
                                   id_unidade_trabalho)
        VALUES (:t, 'Operador', :email, '', :cpf, true, false, :app,
                'ultrassecreto', :u)
        RETURNING id
    """
            ),
            {
                "t": tenant_id,
                "email": f"op-{uuid.uuid4().hex[:8]}@f2.test",
                "cpf": uuid.uuid4().hex[:11],
                "app": APP,
                "u": unidade_id,
            },
        )
    ).scalar_one()
    gid = (
        await session.execute(
            text(
                """
        INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
        VALUES (:t, :n, :s, 'Grupo F2', false) RETURNING id
    """
            ),
            {"t": tenant_id, "n": nivel_id, "s": sistema_id},
        )
    ).scalar_one()
    await session.execute(
        text(
            """
        INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
        VALUES (:t, :u, :g, true, false, :app)
    """
        ),
        {"t": tenant_id, "u": uid, "g": gid, "app": APP},
    )
    await session.execute(
        text(
            """
        INSERT INTO utils.grupo_transacao
            (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
        VALUES (:t, :g, :tr, true, true, true, false)
    """
        ),
        {"t": tenant_id, "g": gid, "tr": transacao_id},
    )
    return uid


@pytest_asyncio.fixture
async def cen(admin_engine):
    """Hierarquia A > B > C, mais a irmã D, e um processo em cada.

        A (lotação do operador)   D (irmã de A — fora do escopo)
        └── B
            └── C                 <- o "neto", que `subordinadas` tem de alcançar

    Um processo por unidade, mais um segundo em A já atribuído, para que
    `escopo=unidade` possa provar que INCLUI o não atribuído.
    """
    slug = _slug("f2-")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref F2",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )

    async with _sm(admin_engine)() as s:
        tipo_unidade = (
            await s.execute(
                text(
                    "SELECT id_tipo_unidade_trabalho FROM utils.unidade_trabalho "
                    "WHERE tenant_id=:t ORDER BY id LIMIT 1"
                ),
                {"t": tenant.id},
            )
        ).scalar_one()
        id_tipo_manif = (
            await s.execute(
                text(
                    "SELECT id FROM protocolos.tipo_manifestante WHERE tenant_id=:t "
                    "ORDER BY id LIMIT 1"
                ),
                {"t": tenant.id},
            )
        ).scalar_one()

        def _un(nome: str, pai: int | None) -> UnidadeTrabalho:
            return UnidadeTrabalho(
                tenant_id=tenant.id,
                unidade_trabalho=nome,
                id_tipo_unidade_trabalho=tipo_unidade,
                id_unidade_pai=pai,
                excluido=False,
            )

        a = _un("A", None)
        d = _un("D", None)
        s.add_all([a, d])
        await s.flush()
        b = _un("B", a.id)
        s.add(b)
        await s.flush()
        c = _un("C", b.id)
        s.add(c)

        tp = TipoProcesso(
            tenant_id=tenant.id, tipo_processo="Geral", exige_processo_pai=False,
            ativo=True, excluido=False,
        )
        manif = Manifestante(
            tenant_id=tenant.id, id_tipo_manifestante=id_tipo_manif, nome="Maria",
            ativo=True, excluido=False,
        )
        s.add_all([tp, manif])
        await s.flush()
        assunto = Assunto(
            tenant_id=tenant.id, assunto="Solicitação", id_tipo_processo=tp.id,
            exige_processo_pai=False, ativo=True, excluido=False,
        )
        s.add(assunto)
        await s.flush()

        operador = await _cria_usuario_comum(s, tenant.id, unidade_id=a.id)
        outro = await _cria_usuario_comum(s, tenant.id, unidade_id=a.id)

        procs: dict[str, int] = {}
        for rotulo, unidade in (
            ("a_sem_dono", a.id),
            ("a_do_operador", a.id),
            ("b_filha", b.id),
            ("c_neto", c.id),
            ("d_irma", d.id),
        ):
            p = Processo(
                tenant_id=tenant.id,
                id_assunto=assunto.id,
                virtual=True,
                data_hora_abertura=datetime.now(),
                numero_processo=f"{slug}-{rotulo}",
                id_unidade_proprietaria=unidade,
                id_manifestante=manif.id,
                id_local_atual=unidade,
                nivel_sigilo="ostensivo",
                ativo=True,
                excluido=False,
            )
            s.add(p)
            await s.flush()
            procs[rotulo] = p.id

        await s.execute(
            text(
                "UPDATE protocolos.processo SET id_usuario_responsavel=:u WHERE id=:p"
            ),
            {"u": operador, "p": procs["a_do_operador"]},
        )
        await s.commit()

        dados = {
            "tenant": tenant,
            "unidades": {"a": a.id, "b": b.id, "c": c.id, "d": d.id},
            "operador": operador,
            "outro": outro,
            "procs": procs,
        }

    yield dados

    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    async with _sm(admin_engine)() as s:
        for stmt in (
            "UPDATE protocolos.processo SET id_ultima_movimentacao=NULL, "
            "  id_local_atual=NULL, id_usuario_responsavel=NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.movimentacao WHERE tenant_id=:t",
            "DELETE FROM protocolos.processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.assunto WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.manifestante WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "UPDATE utils.unidade_trabalho SET id_unidade_pai=NULL WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": dados["tenant"].id})
        await s.commit()


async def _lista(engine, tenant_id, *, timeout_s: int | None = None, **kw) -> set[int]:
    async with _sm(engine)() as s:
        if timeout_s is not None:
            # `SET LOCAL` vale só nesta transação. Serve ao teste do ciclo:
            # sem limite, uma recursiva infinita PENDURA o job em vez de
            # reprovar, e um CI travado é pior que um CI vermelho — ninguém
            # sabe o que aconteceu até o timeout global do runner.
            await s.execute(text(f"SET LOCAL statement_timeout = '{timeout_s}s'"))
        items, _ = await list_processos(
            s, tenant_id=tenant_id, page=1, page_size=100, **kw
        )
    return {i.id for i in items}


# --------------------------------------------------------------------------
# A coluna
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_processo_nasce_sem_responsavel(admin_engine, cen):
    """NULL é o estado inicial, e é um estado — não um campo por preencher."""
    async with _sm(admin_engine)() as s:
        p = (
            await s.execute(
                select(Processo).where(Processo.id == cen["procs"]["a_sem_dono"])
            )
        ).scalar_one()
    assert p.id_usuario_responsavel is None


@pytest.mark.asyncio
async def test_atribuicao_fica_no_historico(admin_engine, cen):
    """Designar é ato: tem de deixar rastro de quem, para quem e a partir de quê."""
    t = cen["tenant"]
    async with _sm(admin_engine)() as s:
        await atribuir_responsavel(
            s,
            cen["procs"]["a_sem_dono"],
            tenant_id=t.id,
            id_usuario=cen["operador"],
            usuario_id=cen["operador"],
        )

    async with _sm(admin_engine)() as s:
        linhas = (
            await s.execute(
                text(
                    "SELECT acao, payload FROM aprimora_py.audit_log "
                    "WHERE tenant_id=:t AND id_entidade=:p ORDER BY id DESC"
                ),
                {"t": t.id, "p": cen["procs"]["a_sem_dono"]},
            )
        ).all()

    assert linhas, "nenhuma entrada de auditoria para a atribuição"
    acao, payload = linhas[0]
    assert acao == "processo.responsavel_atribuido"
    assert payload["id_usuario_responsavel"] == cen["operador"]
    assert payload["id_usuario_responsavel_anterior"] is None


@pytest.mark.asyncio
async def test_reatribuir_a_mesma_pessoa_nao_duplica_historico(admin_engine, cen):
    """Idempotência: sem ela, um duplo clique vira duas entradas de auditoria."""
    t = cen["tenant"]
    pid = cen["procs"]["a_sem_dono"]
    for _ in range(3):
        async with _sm(admin_engine)() as s:
            await atribuir_responsavel(
                s, pid, tenant_id=t.id, id_usuario=cen["operador"],
                usuario_id=cen["operador"],
            )

    async with _sm(admin_engine)() as s:
        n = (
            await s.execute(
                text(
                    "SELECT count(*) FROM aprimora_py.audit_log "
                    "WHERE tenant_id=:t AND id_entidade=:p"
                ),
                {"t": t.id, "p": pid},
            )
        ).scalar_one()
    assert n == 1, f"esperava 1 entrada, veio {n}"


@pytest.mark.asyncio
async def test_desatribuir_volta_ao_estado_pendente(admin_engine, cen):
    t = cen["tenant"]
    pid = cen["procs"]["a_do_operador"]
    async with _sm(admin_engine)() as s:
        p = await atribuir_responsavel(
            s, pid, tenant_id=t.id, id_usuario=None, usuario_id=cen["operador"]
        )
    assert p.id_usuario_responsavel is None

    async with _sm(admin_engine)() as s:
        acao = (
            await s.execute(
                text(
                    "SELECT acao FROM aprimora_py.audit_log WHERE tenant_id=:t "
                    "AND id_entidade=:p ORDER BY id DESC LIMIT 1"
                ),
                {"t": t.id, "p": pid},
            )
        ).scalar_one()
    assert acao == "processo.responsavel_removido"


@pytest.mark.asyncio
async def test_nao_atribui_usuario_de_outro_tenant(admin_engine, cen, two_tenants):
    """A FK aponta para `utils.usuario` e não filtra tenant. O service filtra.

    Usuário cru, sem grupo nem transação: o que se testa é o filtro por tenant,
    e `_cria_usuario_comum` deixaria um `grupo` no tenant da fixture
    `two_tenants`, cuja limpeza não o conhece — a primeira versão deste teste
    passou nas asserções e derrubou o teardown por FK.
    """
    outro_tenant, _ = two_tenants
    async with _sm(admin_engine)() as s:
        alheio = (
            await s.execute(
                text(
                    "INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf,"
                    " ativo, excluido, app, nivel_acesso_sigilo)"
                    " VALUES (:t, 'Alheio', :e, '', :c, true, false, :app,"
                    " 'ostensivo') RETURNING id"
                ),
                {
                    "t": outro_tenant,
                    "e": f"alheio-{uuid.uuid4().hex[:8]}@f2.test",
                    "c": uuid.uuid4().hex[:11],
                    "app": APP,
                },
            )
        ).scalar_one()
        await s.commit()

    try:
        async with _sm(admin_engine)() as s:
            with pytest.raises(AcaoError, match="não encontrado neste tenant"):
                await atribuir_responsavel(
                    s,
                    cen["procs"]["a_sem_dono"],
                    tenant_id=cen["tenant"].id,
                    id_usuario=alheio,
                    usuario_id=cen["operador"],
                )
    finally:
        async with _sm(admin_engine)() as s:
            await s.execute(
                text("DELETE FROM utils.usuario WHERE id=:u"), {"u": alheio}
            )
            await s.commit()


@pytest.mark.asyncio
async def test_responsavel_precisa_estar_lotado_na_unidade_do_processo(
    admin_engine, cen
):
    """Sem esta regra, "atribuir" viraria um jeito de empurrar trabalho para
    fora da unidade sem tramitar — e a permanência (F1) contaria o tempo para o
    setor errado."""
    async with _sm(admin_engine)() as s:
        de_outra_unidade = await _cria_usuario_comum(
            s, cen["tenant"].id, unidade_id=cen["unidades"]["d"]
        )
        await s.commit()

    async with _sm(admin_engine)() as s:
        with pytest.raises(AcaoError, match="lotado na unidade"):
            await atribuir_responsavel(
                s,
                cen["procs"]["a_sem_dono"],  # está em A
                tenant_id=cen["tenant"].id,
                id_usuario=de_outra_unidade,  # lotado em D
                usuario_id=cen["operador"],
            )


@pytest.mark.asyncio
async def test_lotacao_secundaria_tambem_habilita(admin_engine, cen):
    """Lotação tem DUAS representações, e ambas valem.

    `utils.usuario.id_unidade_trabalho` é a principal; `utils.usuario_unidade_
    trabalho` é a tabela N:N das demais, editável em `PUT /usuarios/{id}/unidades`.
    A primeira versão da regra olhava só a principal e rejeitaria o servidor que
    atua em dois setores — que é exatamente o caso para o qual a N:N existe.
    """
    async with _sm(admin_engine)() as s:
        # Principal em D, secundária em A.
        uid = await _cria_usuario_comum(
            s, cen["tenant"].id, unidade_id=cen["unidades"]["d"]
        )
        await s.execute(
            text(
                "INSERT INTO utils.usuario_unidade_trabalho "
                "(tenant_id, id_usuario, id_unidade_trabalho, excluido) "
                "VALUES (:t, :u, :un, false)"
            ),
            {"t": cen["tenant"].id, "u": uid, "un": cen["unidades"]["a"]},
        )
        await s.commit()

    async with _sm(admin_engine)() as s:
        p = await atribuir_responsavel(
            s,
            cen["procs"]["a_sem_dono"],  # está em A
            tenant_id=cen["tenant"].id,
            id_usuario=uid,
            usuario_id=cen["operador"],
        )
    assert p.id_usuario_responsavel == uid


# --------------------------------------------------------------------------
# O escopo
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escopo_meus_nao_vaza_processo_alheio(admin_engine, cen):
    t = cen["tenant"]
    meus = await _lista(
        admin_engine, t.id, escopo=EscopoProcesso.meus,
        id_usuario_contexto=cen["operador"], id_unidade_contexto=cen["unidades"]["a"],
    )
    assert meus == {cen["procs"]["a_do_operador"]}

    # O outro operador, na MESMA unidade, não vê o processo do primeiro.
    dos_outros = await _lista(
        admin_engine, t.id, escopo=EscopoProcesso.meus,
        id_usuario_contexto=cen["outro"], id_unidade_contexto=cen["unidades"]["a"],
    )
    assert dos_outros == set()


@pytest.mark.asyncio
async def test_escopo_unidade_inclui_os_sem_responsavel(admin_engine, cen):
    """O caso que a fatia existe para resolver: processo sem dono não pode
    sumir do recorte da unidade — é o que precisa de alguém."""
    vistos = await _lista(
        admin_engine, cen["tenant"].id, escopo=EscopoProcesso.unidade,
        id_usuario_contexto=cen["operador"], id_unidade_contexto=cen["unidades"]["a"],
    )
    assert cen["procs"]["a_sem_dono"] in vistos
    assert vistos == {cen["procs"]["a_sem_dono"], cen["procs"]["a_do_operador"]}


@pytest.mark.asyncio
async def test_escopo_unidade_nao_alcanca_subordinada(admin_engine, cen):
    vistos = await _lista(
        admin_engine, cen["tenant"].id, escopo=EscopoProcesso.unidade,
        id_usuario_contexto=cen["operador"], id_unidade_contexto=cen["unidades"]["a"],
    )
    assert cen["procs"]["b_filha"] not in vistos


@pytest.mark.asyncio
async def test_subordinadas_alcanca_o_neto_e_nao_alcanca_a_irma(admin_engine, cen):
    """Dois erros opostos num teste só: parar no primeiro nível (perde o neto)
    e varrer o tenant inteiro (pega a irmã)."""
    vistos = await _lista(
        admin_engine, cen["tenant"].id,
        escopo=EscopoProcesso.unidade_e_subordinadas,
        id_usuario_contexto=cen["operador"], id_unidade_contexto=cen["unidades"]["a"],
    )
    assert cen["procs"]["c_neto"] in vistos, "a recursiva parou antes do neto"
    assert cen["procs"]["d_irma"] not in vistos, "o escopo vazou para a irmã"
    assert vistos == {
        cen["procs"]["a_sem_dono"],
        cen["procs"]["a_do_operador"],
        cen["procs"]["b_filha"],
        cen["procs"]["c_neto"],
    }


@pytest.mark.asyncio
async def test_ciclo_na_hierarquia_nao_trava_a_listagem(admin_engine, cen):
    """Ciclo A > B > C > A não pode fazer a recursiva girar para sempre.

    `routers/unidades.py::_validar_sem_ciclo` impede criar ciclo NOVO, mas
    tolera o pré-existente por decisão explícita — então este estado é
    alcançável em base herdada, e com `UNION ALL` a listagem inteira cairia,
    não só o filtro. O teste escreve o ciclo direto no banco porque é
    exatamente assim que ele chega: por dados, não pela API.
    """
    async with _sm(admin_engine)() as s:
        await s.execute(
            text("UPDATE utils.unidade_trabalho SET id_unidade_pai=:c WHERE id=:a"),
            {"c": cen["unidades"]["c"], "a": cen["unidades"]["a"]},
        )
        await s.commit()

    # Medido em 2026-09-16: trocando `UNION` por `UNION ALL` no helper, esta
    # chamada não termina — 150 s sem retorno. O limite de 10 s transforma esse
    # laço numa falha limpa (`QueryCanceled`) em vez de um job pendurado.
    vistos = await _lista(
        admin_engine, cen["tenant"].id,
        timeout_s=10,
        escopo=EscopoProcesso.unidade_e_subordinadas,
        id_usuario_contexto=cen["operador"], id_unidade_contexto=cen["unidades"]["a"],
    )
    # Termina, e o ciclo faz A alcançar tudo menos a irmã.
    assert cen["procs"]["d_irma"] not in vistos
    assert cen["procs"]["c_neto"] in vistos


@pytest.mark.asyncio
async def test_escopo_sem_contexto_devolve_vazio_e_nao_tudo(admin_engine, cen):
    """`coluna == None` no SQLAlchemy vira `IS NULL`.

    Escrito ingenuamente, um usuário sem lotação pedindo "meus" receberia todos
    os processos SEM responsável — uma lista cheia sob um rótulo que promete o
    contrário. Vazio é errado de um jeito que a pessoa percebe.
    """
    for escopo in EscopoProcesso:
        vistos = await _lista(
            admin_engine, cen["tenant"].id, escopo=escopo,
            id_usuario_contexto=None, id_unidade_contexto=None,
        )
        assert vistos == set(), f"{escopo.value} vazou sem contexto"


@pytest.mark.asyncio
async def test_sem_escopo_a_lista_nao_muda(admin_engine, cen):
    """O recorte é opcional e não pode alterar o comportamento de quem não o usa."""
    vistos = await _lista(admin_engine, cen["tenant"].id)
    assert set(cen["procs"].values()) <= vistos


# --------------------------------------------------------------------------
# A borda HTTP, com usuário comum
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_usuario_comum_atribui_e_le_o_responsavel(admin_engine, cen):
    """Usuário COMUM, não super-usuário.

    O bypass de SU em `auth/perms.py` retorna antes de olhar `action`, então um
    teste com SU passaria mesmo se o `action` daqui não existisse no `Literal`
    de `Action` — que é exatamente o defeito que deixou 10 rotas do transporte
    em 500 para operador.
    """
    t = cen["tenant"]
    pid = cen["procs"]["a_sem_dono"]

    async def _get_user():
        async with _sm(admin_engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == cen["operador"]))
            ).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(t.id, t.slug)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.put(
            f"/api/v2/processos/{pid}/responsavel",
            json={"id_usuario": cen["operador"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["id_usuario_responsavel"] == cen["operador"]
        assert r.json()["responsavel"] == "Operador"

        # E o recorte pela mesma borda.
        r2 = await client.get("/api/v2/processos", params={"escopo": "meus"})
        assert r2.status_code == 200, r2.text
        ids = {i["id"] for i in r2.json()["items"]}
        assert pid in ids
        assert cen["procs"]["d_irma"] not in ids

        # Desatribuir pela borda devolve ao estado pendente.
        r3 = await client.put(
            f"/api/v2/processos/{pid}/responsavel", json={"id_usuario": None}
        )
        assert r3.status_code == 200, r3.text
        assert r3.json()["id_usuario_responsavel"] is None


@pytest.mark.asyncio
async def test_http_escopo_invalido_e_422_e_nao_lista_tudo(admin_engine, cen):
    """Valor fora do enum tem de ser recusado, não ignorado.

    Ignorar transformaria um erro de digitação no cliente numa listagem
    completa — o oposto do que o parâmetro pede, e silencioso.
    """
    t = cen["tenant"]

    async def _get_user():
        async with _sm(admin_engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == cen["operador"]))
            ).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(t.id, t.slug)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v2/processos", params={"escopo": "tudo"})
    assert r.status_code == 422, r.text
