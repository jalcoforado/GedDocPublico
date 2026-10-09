"""Caixas de trabalho da tela de Processos (filtro `caixa` + contadores).

O que este arquivo existe para pegar
------------------------------------
**Contador que não bate com a lista.** As definições moram num lugar só
(`services/processos.py::_predicado_caixa`); se alguém duplicar a regra, o
número da lateral passa a divergir do `total` da lista. Há teste que compara
os dois caixa por caixa.

**Caixa que não é disjunta.** Encaminhar NÃO muda `id_local_atual` — só o
recebimento muda. Um predicado ingênuo ("local atual = minha unidade") deixaria
o processo que acabei de mandar embora ainda na minha Análise, e o mesmo
processo apareceria em duas caixas.

**Vazamento.** Um filtro errado não estoura: devolve uma lista plausível. Os
testes de tenant e de sigilo provam que a caixa não afrouxa nenhum dos dois, e
o de contexto ausente prova que usuário sem lotação recebe NADA, não "tudo o
que tem campo nulo".

**Usuário comum.** O bypass de super-usuário em `auth/perms.py` esconde
defeito de gate; os testes HTTP daqui usam operador não-SU.
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
from app.main import app
from app.models import (
    Anexo,
    AssinaturaAnexo,
    Assunto,
    Encaminhamento,
    Manifestante,
    Prioridade,
    Processo,
    SolicitacaoAssinatura,
    TipoProcesso,
    UnidadeTrabalho,
    Usuario,
    UsuarioAssinatura,
)
from app.schemas.processo import ArquivarRequest, CaixaProcesso
from app.services.acoes_processo import arquivar
from app.services.processos import contar_caixas, list_processos
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http
from tests.test_processo_responsavel import _cria_usuario_comum

LIMPEZA = (
    "UPDATE protocolos.processo SET id_ultima_movimentacao=NULL, "
    "  id_local_atual=NULL, id_usuario_responsavel=NULL WHERE tenant_id=:t",
    "DELETE FROM protocolos.assinatura_anexo WHERE tenant_id=:t",
    "DELETE FROM protocolos.usuario_assinatura WHERE tenant_id=:t",
    "DELETE FROM protocolos.solicitacao_assinatura WHERE tenant_id=:t",
    "DELETE FROM protocolos.anexo WHERE tenant_id=:t",
    "DELETE FROM protocolos.encaminhamento WHERE tenant_id=:t",
    "DELETE FROM protocolos.despacho WHERE tenant_id=:t",
    "DELETE FROM protocolos.movimentacao WHERE tenant_id=:t",
    "DELETE FROM protocolos.arquivamento WHERE tenant_id=:t",
    "DELETE FROM protocolos.processo WHERE tenant_id=:t",
    "DELETE FROM protocolos.assunto WHERE tenant_id=:t",
    "DELETE FROM protocolos.tipo_processo WHERE tenant_id=:t",
    "DELETE FROM protocolos.manifestante WHERE tenant_id=:t",
    "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
    "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
    "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
    "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
    "DELETE FROM utils.grupo WHERE tenant_id=:t",
    "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
    "DELETE FROM utils.usuario WHERE tenant_id=:t",
    "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
    "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
    "DELETE FROM aprimora_py.tenant WHERE id=:t",
)


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _monta_tenant(s: AsyncSession, prefixo: str) -> dict:
    """Tenant com duas unidades (A = a do operador, B = a outra) e o catálogo
    mínimo para abrir processo."""
    slug = f"{prefixo}{uuid.uuid4().hex[:8]}"
    tenant, _ = await provisionar_tenant(
        s,
        slug=slug,
        nome="Pref Caixas",
        admin_email=f"{slug}@t.local",
        admin_nome="Adm",
        admin_cpf=uuid.uuid4().hex[:11],
        plano="basico",
    )
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
    a = UnidadeTrabalho(
        tenant_id=tenant.id, unidade_trabalho="A", excluido=False,
        id_tipo_unidade_trabalho=tipo_unidade,
    )
    b = UnidadeTrabalho(
        tenant_id=tenant.id, unidade_trabalho="B", excluido=False,
        id_tipo_unidade_trabalho=tipo_unidade,
    )
    tp = TipoProcesso(
        tenant_id=tenant.id, tipo_processo="Geral", exige_processo_pai=False,
        ativo=True, excluido=False,
    )
    manif = Manifestante(
        tenant_id=tenant.id, id_tipo_manifestante=id_tipo_manif, nome="Maria",
        ativo=True, excluido=False,
    )
    s.add_all([a, b, tp, manif])
    await s.flush()
    assunto = Assunto(
        tenant_id=tenant.id, assunto="Solicitação", id_tipo_processo=tp.id,
        exige_processo_pai=False, ativo=True, excluido=False,
    )
    s.add(assunto)
    await s.flush()
    return {
        "tenant": tenant, "slug": slug, "a": a.id, "b": b.id,
        "assunto": assunto.id, "manif": manif.id,
    }


def _processo(base: dict, rotulo: str, local: int | None, **kw) -> Processo:
    # Processo sem local atual existe (legado, ou aberto antes do primeiro
    # recebimento); a unidade proprietária, não: é NOT NULL.
    proprietaria = local if local is not None else base["b"]
    return Processo(
        tenant_id=base["tenant"].id,
        id_assunto=base["assunto"],
        virtual=True,
        data_hora_abertura=datetime.now(),
        # Rascunho não tem número: `ck_processo_situacao_numero` reprova.
        numero_processo=(
            None if kw.get("situacao") == "rascunho" else f"{base['slug']}-{rotulo}"
        ),
        id_unidade_proprietaria=proprietaria,
        id_manifestante=base["manif"],
        id_local_atual=local,
        nivel_sigilo=kw.pop("nivel_sigilo", "ostensivo"),
        ativo=True,
        excluido=False,
        **kw,
    )


@pytest_asyncio.fixture
async def cen(admin_engine):
    """Um processo por estado, todos vistos do ponto de vista da unidade A.

    rótulo        local  estado                                  caixa (de A)
    ------------  -----  --------------------------------------  -------------
    na_mesa       A      nada pendente                           analise
    externo       A      nada pendente, `externo=True`           analise+externos
    saindo        A      encaminhado A→B, não recebido           saida
    chegando      B      encaminhado B→A, não recebido           entrada
    recebido      A      encaminhado B→A, JÁ recebido            analise
    cancelado     A      encaminhado A→B, CANCELADO              analise
    arquivado     A      arquivado                               arquivados
    de_b          B      nada pendente                           (nenhuma)
    rascunho      A      `situacao='rascunho'`                   (nenhuma)
    sigiloso      A      `nivel_sigilo='secreto'`                analise (se a
                                                                 credencial alcança)
    sem_local     —      `id_local_atual` NULO                   (nenhuma)
    orfao         —      local NULO, encaminhado de origem NULA  (nenhuma)
                         para B, não recebido

    Os dois últimos existem para o teste de contexto ausente NÃO passar por
    vacuidade: sem linha com campo nulo no banco, `coluna IS NULL` não casa
    nada e o defeito que o teste procura fica invisível.
    """
    async with _sm(admin_engine)() as s:
        base = await _monta_tenant(s, "cx-")
        t = base["tenant"]
        operador = await _cria_usuario_comum(s, t.id, unidade_id=base["a"])
        colega_b = await _cria_usuario_comum(s, t.id, unidade_id=base["b"])
        sem_lotacao = await _cria_usuario_comum(s, t.id, unidade_id=None)

        # `Prioridade` é catálogo GLOBAL (sem tenant_id): cria a própria e a
        # apaga no fim, para não depender do que outro teste deixou.
        prio = Prioridade(prioridade="Normal", fator=1, cor="#999999", ativo=True, excluido=False)
        s.add(prio)

        procs: dict[str, Processo] = {
            "na_mesa": _processo(base, "na_mesa", base["a"]),
            "externo": _processo(base, "externo", base["a"], externo=True),
            "saindo": _processo(base, "saindo", base["a"]),
            "chegando": _processo(base, "chegando", base["b"]),
            "recebido": _processo(base, "recebido", base["a"]),
            "cancelado": _processo(base, "cancelado", base["a"]),
            "arquivado": _processo(base, "arquivado", base["a"]),
            "de_b": _processo(base, "de_b", base["b"]),
            "rascunho": _processo(base, "rascunho", base["a"], situacao="rascunho"),
            "sigiloso": _processo(base, "sigiloso", base["a"], nivel_sigilo="secreto"),
            "sem_local": _processo(base, "sem_local", None),
            "orfao": _processo(base, "orfao", None),
        }
        s.add_all(procs.values())
        await s.flush()

        def _enc(rotulo: str, origem: int | None, destino: int, **kw) -> Encaminhamento:
            return Encaminhamento(
                tenant_id=t.id, id_processo=procs[rotulo].id,
                id_unidade_origem=origem, id_unidade_destino=destino,
                id_prioridade=prio.id, quantidade_folhas=0, externo=False,
                recebido=kw.get("recebido", False),
                cancelado=kw.get("cancelado", False),
                id_usuario=operador, ativo=True, excluido=False,
            )

        s.add_all([
            _enc("saindo", base["a"], base["b"]),
            _enc("chegando", base["b"], base["a"]),
            _enc("recebido", base["b"], base["a"], recebido=True),
            _enc("cancelado", base["a"], base["b"], cancelado=True),
            _enc("orfao", None, base["b"]),
        ])

        # Assinaturas — o operador TEM de assinar um documento de `na_mesa`, e
        # PEDIU a assinatura de um documento de `de_b` (processo de outra
        # unidade: a caixa de assinatura é da pessoa, não da unidade).
        async def _solicitacao(rotulo: str, solicitante: int, assinante: int, assinado):
            anexo = Anexo(tenant_id=t.id, publico=False, ativo=True, excluido=False, descricao="doc")
            sol = SolicitacaoAssinatura(
                tenant_id=t.id, id_processo=procs[rotulo].id, id_solicitante=solicitante,
                id_usuario=solicitante, dt_inicio=datetime.now(), cancelada=False,
                realizada=False, ativo=True, excluido=False,
            )
            s.add_all([anexo, sol])
            await s.flush()
            ua = UsuarioAssinatura(
                tenant_id=t.id, id_solicitacao_assinatura=sol.id, id_assinante=assinante,
                id_unidade_trabalho=base["a"], ordem=1, id_usuario=solicitante,
                realizada=False, ativo=True, excluido=False,
            )
            s.add(ua)
            await s.flush()
            s.add(AssinaturaAnexo(
                tenant_id=t.id, id_usuario_assinatura=ua.id, id_anexo=anexo.id,
                assinado=assinado, id_usuario=solicitante, id_processo=procs[rotulo].id,
                ativo=True, excluido=False,
            ))

        await _solicitacao("na_mesa", colega_b, operador, None)
        await _solicitacao("de_b", operador, colega_b, None)
        # Já assinada: não é pendência de ninguém.
        await _solicitacao("recebido", colega_b, operador, True)
        await s.commit()

        dados = {
            **base,
            "operador": operador, "colega_b": colega_b, "sem_lotacao": sem_lotacao,
            "prioridade": prio.id,
            "procs": {k: p.id for k, p in procs.items()},
        }

    # Arquiva pelo caminho REAL: é ele que grava a `Movimentacao` com
    # `id_arquivamento`, e é por ela que a caixa reconhece o arquivado.
    async with _sm(admin_engine)() as s:
        await arquivar(
            s, dados["procs"]["arquivado"], ArquivarRequest(motivo="Demanda atendida"),
            tenant_id=dados["tenant"].id, usuario_id=operador, is_super_usuario=True,
        )
        await s.commit()

    yield dados

    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    async with _sm(admin_engine)() as s:
        for stmt in LIMPEZA:
            await s.execute(text(stmt), {"t": dados["tenant"].id})
        # Por último: `encaminhamento.id_prioridade` apontava para ela.
        await s.execute(
            text("DELETE FROM protocolos.prioridade WHERE id=:p"), {"p": dados["prioridade"]}
        )
        await s.commit()


async def _ids(engine, cen, caixa: CaixaProcesso, **kw) -> set[str]:
    """Rótulos (não ids) dos processos que a caixa devolve ao operador."""
    kw.setdefault("id_usuario_contexto", cen["operador"])
    kw.setdefault("id_unidade_contexto", cen["a"])
    async with _sm(engine)() as s:
        items, total = await list_processos(
            s, tenant_id=cen["tenant"].id, page=1, page_size=100, caixa=caixa, **kw
        )
    por_id = {v: k for k, v in cen["procs"].items()}
    achados = {por_id[i.id] for i in items}
    assert total == len(achados)
    return achados


# --------------------------------------------------------------------------
# Definições
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cada_caixa_devolve_o_que_promete(admin_engine, cen):
    assert await _ids(admin_engine, cen, CaixaProcesso.entrada) == {"chegando"}
    assert await _ids(admin_engine, cen, CaixaProcesso.saida) == {"saindo"}
    assert await _ids(admin_engine, cen, CaixaProcesso.analise) == {
        "na_mesa", "externo", "recebido", "cancelado", "sigiloso",
    }
    assert await _ids(admin_engine, cen, CaixaProcesso.externos) == {"externo"}
    assert await _ids(admin_engine, cen, CaixaProcesso.arquivados) == {"arquivado"}
    assert await _ids(admin_engine, cen, CaixaProcesso.aguardando_assinatura) == {"na_mesa"}
    assert await _ids(admin_engine, cen, CaixaProcesso.enviado_para_assinatura) == {"de_b"}


@pytest.mark.asyncio
async def test_encaminhado_sai_da_analise_mesmo_com_local_atual_na_origem(admin_engine, cen):
    """`id_local_atual` de `saindo` ainda é A — só o recebimento o muda. A
    caixa tem de ler o encaminhamento, não o local."""
    async with _sm(admin_engine)() as s:
        local = (
            await s.execute(
                select(Processo.id_local_atual).where(Processo.id == cen["procs"]["saindo"])
            )
        ).scalar_one()
    assert local == cen["a"]
    assert "saindo" not in await _ids(admin_engine, cen, CaixaProcesso.analise)


@pytest.mark.asyncio
async def test_entrada_saida_analise_e_arquivados_nao_se_sobrepoem(admin_engine, cen):
    caixas = [
        await _ids(admin_engine, cen, c)
        for c in (
            CaixaProcesso.entrada, CaixaProcesso.saida,
            CaixaProcesso.analise, CaixaProcesso.arquivados,
        )
    ]
    todos = [r for c in caixas for r in c]
    assert len(todos) == len(set(todos)), f"processo em duas caixas: {caixas}"


@pytest.mark.asyncio
async def test_a_mesma_tramitacao_vista_da_outra_unidade(admin_engine, cen):
    """O que é SAÍDA para A é ENTRADA para B, e vice-versa."""
    kw = {"id_usuario_contexto": cen["colega_b"], "id_unidade_contexto": cen["b"]}
    assert await _ids(admin_engine, cen, CaixaProcesso.entrada, **kw) == {"saindo", "orfao"}
    assert await _ids(admin_engine, cen, CaixaProcesso.saida, **kw) == {"chegando"}
    assert await _ids(admin_engine, cen, CaixaProcesso.analise, **kw) == {"de_b"}


@pytest.mark.asyncio
async def test_rascunho_nao_entra_em_caixa_nenhuma(admin_engine, cen):
    for caixa in CaixaProcesso:
        assert "rascunho" not in await _ids(admin_engine, cen, caixa)


# --------------------------------------------------------------------------
# Contadores
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contador_e_o_total_da_lista_caixa_por_caixa(admin_engine, cen):
    """A propriedade que a tela promete: o número da lateral é o que a lista
    mostra ao abrir a caixa."""
    async with _sm(admin_engine)() as s:
        contagem = await contar_caixas(
            s, tenant_id=cen["tenant"].id,
            id_usuario_contexto=cen["operador"], id_unidade_contexto=cen["a"],
        )
    for caixa in CaixaProcesso:
        na_lista = await _ids(admin_engine, cen, caixa)
        assert getattr(contagem, caixa.value) == len(na_lista), caixa.value
    assert contagem.model_dump() == {
        "entrada": 1, "saida": 1, "analise": 5, "externos": 1,
        "aguardando_assinatura": 1, "enviado_para_assinatura": 1, "arquivados": 1,
    }


@pytest.mark.asyncio
async def test_sigilo_reduz_lista_e_contador_juntos(admin_engine, cen):
    """Credencial que não alcança `secreto` não vê o processo — nem o conta.
    Contar o que não se pode ver confirmaria a existência dele."""
    niveis = ["ostensivo", "interno"]
    assert "sigiloso" not in await _ids(
        admin_engine, cen, CaixaProcesso.analise, niveis_permitidos=niveis
    )
    async with _sm(admin_engine)() as s:
        contagem = await contar_caixas(
            s, tenant_id=cen["tenant"].id, niveis_permitidos=niveis,
            id_usuario_contexto=cen["operador"], id_unidade_contexto=cen["a"],
        )
    assert contagem.analise == 4


@pytest.mark.asyncio
async def test_usuario_sem_lotacao_recebe_nada_nas_caixas_de_unidade(admin_engine, cen):
    """`coluna == None` compila para `IS NULL`: escrito ingenuamente, quem não
    tem lotação veria tudo o que não tem local/destino."""
    kw = {"id_usuario_contexto": cen["sem_lotacao"], "id_unidade_contexto": None}
    for caixa in (
        CaixaProcesso.entrada, CaixaProcesso.saida, CaixaProcesso.analise,
        CaixaProcesso.externos, CaixaProcesso.arquivados,
    ):
        assert await _ids(admin_engine, cen, caixa, **kw) == set(), caixa.value
    async with _sm(admin_engine)() as s:
        contagem = await contar_caixas(s, tenant_id=cen["tenant"].id, **kw)
    assert sum(contagem.model_dump().values()) == 0


@pytest.mark.asyncio
async def test_caixa_nao_atravessa_tenant(admin_engine, cen):
    """Outro tenant, consultando com os ids de unidade e usuário DESTE: os ids
    existem, mas não são dele — e não podem render nada."""
    async with _sm(admin_engine)() as s:
        outro = await _monta_tenant(s, "cx2-")
        await s.commit()
    try:
        async with _sm(admin_engine)() as s:
            contagem = await contar_caixas(
                s, tenant_id=outro["tenant"].id,
                id_usuario_contexto=cen["operador"], id_unidade_contexto=cen["a"],
            )
            assert sum(contagem.model_dump().values()) == 0
            for caixa in CaixaProcesso:
                items, total = await list_processos(
                    s, tenant_id=outro["tenant"].id, page=1, page_size=100, caixa=caixa,
                    id_usuario_contexto=cen["operador"], id_unidade_contexto=cen["a"],
                )
                assert (items, total) == ([], 0), caixa.value
    finally:
        async with _sm(admin_engine)() as s:
            for stmt in LIMPEZA:
                await s.execute(text(stmt), {"t": outro["tenant"].id})
            await s.commit()


# --------------------------------------------------------------------------
# HTTP — usuário COMUM
# --------------------------------------------------------------------------


def _como(admin_engine, usuario_id: int):
    async def _get_user():
        async with _sm(admin_engine)() as s:
            return (await s.execute(select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    return _get_user


@pytest.mark.asyncio
async def test_http_usuario_comum_le_contadores_e_abre_a_caixa(admin_engine, cen):
    """Passa pelo roteamento de verdade: `/caixas` é literal e tem de casar
    ANTES de `/{processo_id}` (senão morre em 422), e o gate é o da listagem."""
    t = cen["tenant"]
    app.dependency_overrides[get_current_user] = _como(admin_engine, cen["operador"])
    arreio_tenant_http(t.id, t.slug)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v2/processos/caixas")
        assert r.status_code == 200, r.text
        assert r.json() == {
            "entrada": 1, "saida": 1, "analise": 5, "externos": 1,
            "aguardando_assinatura": 1, "enviado_para_assinatura": 1, "arquivados": 1,
        }

        r2 = await client.get("/api/v2/processos", params={"caixa": "entrada"})
        assert r2.status_code == 200, r2.text
        assert [i["id"] for i in r2.json()["items"]] == [cen["procs"]["chegando"]]
        assert r2.json()["total"] == r.json()["entrada"]


@pytest.mark.asyncio
async def test_http_caixa_invalida_e_422_e_nao_lista_tudo(admin_engine, cen):
    """"recusados" não existe. Ignorar o valor devolveria a lista inteira sob
    um rótulo que promete um recorte."""
    t = cen["tenant"]
    app.dependency_overrides[get_current_user] = _como(admin_engine, cen["operador"])
    arreio_tenant_http(t.id, t.slug)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v2/processos", params={"caixa": "recusados"})
        assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_http_sem_a_transacao_processo_e_403(admin_engine, cen):
    """Contador também é leitura gateada: usuário sem `processo` não descobre
    quantos processos a unidade tem."""
    t = cen["tenant"]
    async with _sm(admin_engine)() as s:
        await s.execute(
            text("DELETE FROM utils.grupo_transacao WHERE tenant_id=:t"), {"t": t.id}
        )
        await s.commit()
    app.dependency_overrides[get_current_user] = _como(admin_engine, cen["operador"])
    arreio_tenant_http(t.id, t.slug)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v2/processos/caixas")
        assert r.status_code == 403, r.text


# --------------------------------------------------------------------------
# Tempo na caixa — `parado_desde` e a ordem `parados`
# --------------------------------------------------------------------------


async def _envelhece(engine, cen, **dias_por_rotulo: int) -> None:
    """Recuar a abertura de alguns processos, para a ordem ter o que ordenar."""
    async with _sm(engine)() as s:
        for rotulo, dias in dias_por_rotulo.items():
            await s.execute(
                text(
                    "UPDATE protocolos.processo "
                    "SET data_hora_abertura = now() - make_interval(days => :d) WHERE id=:p"
                ),
                {"d": dias, "p": cen["procs"][rotulo]},
            )
        await s.commit()


@pytest.mark.asyncio
async def test_parado_desde_e_a_ultima_movimentacao_nao_a_abertura(admin_engine, cen):
    """`arquivado` foi aberto "há 40 dias" e arquivado agora: está nesse
    estado desde AGORA. Usar a abertura diria que o arquivo tem 40 dias."""
    from app.schemas.processo import OrdemProcesso  # noqa: F401 — só garante o import

    await _envelhece(admin_engine, cen, arquivado=40, na_mesa=10)
    async with _sm(admin_engine)() as s:
        items, _ = await list_processos(
            s, tenant_id=cen["tenant"].id, page=1, page_size=100, situacao="todos",
            id_usuario_contexto=cen["operador"], id_unidade_contexto=cen["a"],
        )
    por_id = {i.id: i for i in items}
    agora = datetime.now()

    arquivado = por_id[cen["procs"]["arquivado"]]
    assert (agora - arquivado.data_hora_abertura).days >= 39
    assert abs((agora - arquivado.parado_desde).total_seconds()) < 600

    # Sem movimentação nenhuma, cai na abertura — nunca fica nulo.
    na_mesa = por_id[cen["procs"]["na_mesa"]]
    assert na_mesa.parado_desde == na_mesa.data_hora_abertura
    assert all(i.parado_desde is not None for i in items)


@pytest.mark.asyncio
async def test_ordem_parados_poe_no_topo_o_que_espera_ha_mais_tempo(admin_engine, cen):
    from app.schemas.processo import OrdemProcesso

    await _envelhece(admin_engine, cen, cancelado=30, externo=20, na_mesa=10)
    async with _sm(admin_engine)() as s:
        parados, _ = await list_processos(
            s, tenant_id=cen["tenant"].id, page=1, page_size=100,
            caixa=CaixaProcesso.analise, ordem=OrdemProcesso.parados,
            id_usuario_contexto=cen["operador"], id_unidade_contexto=cen["a"],
        )
        recentes, _ = await list_processos(
            s, tenant_id=cen["tenant"].id, page=1, page_size=100,
            caixa=CaixaProcesso.analise,
            id_usuario_contexto=cen["operador"], id_unidade_contexto=cen["a"],
        )
    por_id = {v: k for k, v in cen["procs"].items()}
    assert [por_id[i.id] for i in parados][:3] == ["cancelado", "externo", "na_mesa"]
    datas = [i.parado_desde for i in parados]
    assert datas == sorted(datas)
    # O padrão não mudou: abertura, do mais novo — os três envelhecidos no fim.
    assert [por_id[i.id] for i in recentes][-3:] == ["na_mesa", "externo", "cancelado"]


@pytest.mark.asyncio
async def test_http_ordem_parados_e_o_campo_chegam_pela_borda(admin_engine, cen):
    t = cen["tenant"]
    await _envelhece(admin_engine, cen, cancelado=30)
    app.dependency_overrides[get_current_user] = _como(admin_engine, cen["operador"])
    arreio_tenant_http(t.id, t.slug)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/v2/processos", params={"caixa": "analise", "ordem": "parados"}
        )
        assert r.status_code == 200, r.text
        itens = r.json()["items"]
        assert itens[0]["id"] == cen["procs"]["cancelado"]
        assert itens[0]["parado_desde"] is not None

        r2 = await client.get("/api/v2/processos", params={"ordem": "aleatoria"})
        assert r2.status_code == 422, r2.text
