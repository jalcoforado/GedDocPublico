"""Pedido de avaliação e decisão por documento (SI-73, RF-04 V2).

Tudo pela API e com usuários COMUNS (o super-usuário passaria por cima da
permissão e do sigilo — CLAUDE.md §Testes). O cenário é o do SI-72
(`test_anexo_versao.py`), com três pessoas por prefeitura:

- `servidor`: tramita (transação `processo`), é quem pede;
- `avaliador`: tem `documento_avaliar` (e a leitura de `processo`);
- `colega`: também tem `documento_avaliar`, mas não foi designado.

Cobre o "pronto quando" do card — AC-01 (três documentos, aprova dois,
devolve um) e AC-04 (sem atribuição ou sem permissão não decide) — e as
regras combinadas: versão exata, reenvio após versão nova, trava de versão
nova e de exclusão, validação do avaliador, sigilo e outra prefeitura.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.auth.deps import get_current_user
from app.main import app
from app.models import Usuario
from app.services.avaliacoes import pendencias_do_processo
from tests.conftest import arreio_tenant_http
from tests.test_anexo_versao import APP, _anexar, _limpar, _nova_versao, _prefeitura, _sm

JUSTIFICATIVA = "Falta a assinatura do responsável técnico"


async def _usuario(s, tenant_id: int, unidade_id: int, transacoes: tuple[str, ...],
                   credencial: str = "interno") -> int:
    """Usuário não-SU com as transações dadas (grupo próprio)."""
    sistema_id = (await s.execute(text(
        "SELECT id FROM utils.sistema WHERE app = :app AND excluido = false LIMIT 1"
    ), {"app": APP})).scalar_one()
    nivel_id = (await s.execute(text(
        "SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1"
    ))).scalar_one()
    uid = (await s.execute(text("""
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo, id_unidade_trabalho)
        VALUES (:t, :n, :e, '', :c, true, false, :app, :cred, :u) RETURNING id
    """), {"t": tenant_id, "n": f"Servidor {uuid.uuid4().hex[:4]}",
           "e": f"aval-{uuid.uuid4().hex[:8]}@avaliacao.test", "c": uuid.uuid4().hex[:11],
           "app": APP, "cred": credencial, "u": unidade_id})).scalar_one()
    gid = (await s.execute(text(
        "INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido) "
        "VALUES (:t, :n, :s, 'Grupo Avaliacao', false) RETURNING id"
    ), {"t": tenant_id, "n": nivel_id, "s": sistema_id})).scalar_one()
    await s.execute(text(
        "INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app) "
        "VALUES (:t, :u, :g, true, false, :app)"
    ), {"t": tenant_id, "u": uid, "g": gid, "app": APP})
    await s.execute(text("""
        INSERT INTO utils.grupo_transacao
            (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
        SELECT :t, :g, tr.id, false, false, false, false
          FROM utils.transacao tr WHERE tr.codigo = ANY(:cods) AND tr.excluido = false
    """), {"t": tenant_id, "g": gid, "cods": list(transacoes)})
    return uid


async def _com_avaliadores(admin_engine, pref: dict) -> dict:
    async with _sm(admin_engine)() as s:
        t, u = pref["tenant"].id, pref["unidade"]
        pref["avaliador"] = await _usuario(s, t, u, ("processo", "documento_avaliar"))
        pref["colega"] = await _usuario(s, t, u, ("processo", "documento_avaliar"))
        pref["sem_permissao"] = await _usuario(s, t, u, ("processo",))
        pref["so_ostensivo"] = await _usuario(
            s, t, u, ("processo", "documento_avaliar"), credencial="ostensivo")
        await s.commit()
    return pref


async def _limpar_tudo(admin_engine, tenant_id: int) -> None:
    async with _sm(admin_engine)() as s:
        for stmt in (
            "DELETE FROM aprimora_py.notificacao WHERE tenant_id=:t",
            "UPDATE protocolos.avaliacao_documento SET id_avaliacao_anterior=NULL "
            "  WHERE tenant_id=:t",
            "DELETE FROM protocolos.avaliacao_documento WHERE tenant_id=:t",
            "DELETE FROM protocolos.avaliacao_pedido WHERE tenant_id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()
    await _limpar(admin_engine, tenant_id)


@pytest_asyncio.fixture
async def cen(admin_engine):
    a = await _com_avaliadores(admin_engine, await _prefeitura(admin_engine, "aval-a-"))
    b = await _com_avaliadores(admin_engine, await _prefeitura(admin_engine, "aval-b-"))
    yield {"a": a, "b": b}
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    await _limpar_tudo(admin_engine, a["tenant"].id)
    await _limpar_tudo(admin_engine, b["tenant"].id)


def _como(admin_engine, pref: dict, quem: str = "servidor") -> AsyncClient:
    uid = pref[quem]

    async def _u():
        async with _sm(admin_engine)() as s:
            return (await s.execute(select(Usuario).where(Usuario.id == uid))).scalar_one()

    app.dependency_overrides[get_current_user] = _u
    arreio_tenant_http(pref["tenant"].id, pref["tenant"].slug)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _tres_documentos(admin_engine, a: dict) -> list[int]:
    async with _como(admin_engine, a) as cli:
        ids = []
        for nome in ("Projeto", "Memorial", "ART"):
            r = await _anexar(cli, a["principal"], nome)
            assert r.status_code == 201, r.text
            ids.append(r.json()["id"])
    return ids


async def _pedir(admin_engine, a: dict, anexos: list[int], *, avaliador: str = "avaliador",
                 processo: str = "principal", **extra):
    async with _como(admin_engine, a) as cli:
        return await cli.post(
            f"/api/v2/processos/{a[processo]}/avaliacoes",
            json={"id_avaliador": a[avaliador], "id_anexos": anexos,
                  "orientacao": "Conferir com a norma municipal", **extra},
        )


async def _avisos(admin_engine, tenant_id: int, tipo: str) -> list[tuple]:
    async with _sm(admin_engine)() as s:
        return (await s.execute(text(
            "SELECT id_usuario, link_url FROM aprimora_py.notificacao "
            "WHERE tenant_id=:t AND tipo=:tipo ORDER BY id"), {"t": tenant_id, "tipo": tipo}
        )).all()


async def _pendencias(admin_engine, a: dict):
    async with _sm(admin_engine)() as s:
        return await pendencias_do_processo(s, a["principal"], tenant_id=a["tenant"].id)


# --------------------------------------------------------------------------
# AC-01 — três documentos: aprova dois, devolve um; o devolvido volta corrigido
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac01_aprova_dois_devolve_um_e_o_corrigido_volta(admin_engine, cen):
    a = cen["a"]
    projeto, memorial, art = await _tres_documentos(admin_engine, a)
    link = f"/m/protocolo/processos/{a['principal']}"

    r = await _pedir(admin_engine, a, [projeto, memorial, art])
    assert r.status_code == 201, r.text
    pedido = r.json()
    assert pedido["situacao"] == "pendente"
    assert pedido["id_usuario_solicitante"] == a["servidor"]
    assert [i["situacao"] for i in pedido["itens"]] == ["aguardando"] * 3
    assert await _avisos(admin_engine, a["tenant"].id, "avaliacao_solicitada") == [
        (a["avaliador"], link)]
    assert (await _pendencias(admin_engine, a)).aguardando == 3

    item = {i["id_anexo"]: i["id"] for i in pedido["itens"]}
    async with _como(admin_engine, a, "avaliador") as cli:
        caixa = (await cli.get("/api/v2/avaliacoes", params={"papel": "avaliador"})).json()
        assert [p["id"] for p in caixa["items"]] == [pedido["id"]] and caixa["total"] == 1
        r = await cli.post(f"/api/v2/avaliacoes/{pedido['id']}/decisoes", json={"decisoes": [
            {"id_item": item[projeto], "resultado": "aprovado"},
            {"id_item": item[memorial], "resultado": "aprovado"},
            {"id_item": item[art], "resultado": "devolvido", "justificativa": JUSTIFICATIVA},
        ]})
        assert r.status_code == 200, r.text
    decidido = r.json()
    assert decidido["situacao"] == "concluida" and decidido["concluido_em"]
    sit = {i["id_anexo"]: i for i in decidido["itens"]}
    assert sit[projeto]["situacao"] == sit[memorial]["situacao"] == "aprovado"
    assert sit[art]["situacao"] == "devolvido"
    assert sit[art]["justificativa"] == JUSTIFICATIVA
    assert sit[art]["pode_reenviar"] is False  # ainda não há versão corrigida
    assert await _avisos(admin_engine, a["tenant"].id, "avaliacao_decidida") == [
        (a["servidor"], link)]
    p = await _pendencias(admin_engine, a)
    assert (p.aguardando, p.devolvidos_sem_reenvio, p.livre) == (0, 1, False)

    async with _como(admin_engine, a) as cli:
        # Reenviar sem corrigir não faz sentido.
        r = await cli.post(f"/api/v2/avaliacoes/{pedido['id']}/itens/{item[art]}/reenviar")
        assert r.status_code == 409, r.text
        # Aprovado não se reenvia.
        r = await cli.post(f"/api/v2/avaliacoes/{pedido['id']}/itens/{item[projeto]}/reenviar")
        assert r.status_code == 409, r.text

        v2 = await _nova_versao(cli, a["principal"], art)
        assert v2.status_code == 201, v2.text
        v2 = v2.json()["id"]
        lista = (await cli.get(f"/api/v2/processos/{a['principal']}/avaliacoes")).json()
        assert next(i for i in lista[0]["itens"] if i["id"] == item[art])["pode_reenviar"]

        r = await cli.post(f"/api/v2/avaliacoes/{pedido['id']}/itens/{item[art]}/reenviar")
        assert r.status_code == 200, r.text
        reenviado = r.json()
        de_novo = await cli.post(
            f"/api/v2/avaliacoes/{pedido['id']}/itens/{item[art]}/reenviar")
        assert de_novo.status_code == 409, de_novo.text

    assert reenviado["situacao"] == "pendente"
    novo = next(i for i in reenviado["itens"] if i["id_avaliacao_anterior"] == item[art])
    # A avaliação aponta para a VERSÃO corrigida, não para o documento em geral.
    assert novo["id_anexo"] == v2 and novo["versao"] == 2 and novo["situacao"] == "aguardando"
    antigo = next(i for i in reenviado["itens"] if i["id"] == item[art])
    assert antigo["id_avaliacao_reenvio"] == novo["id"] and antigo["situacao"] == "devolvido"
    assert await _avisos(admin_engine, a["tenant"].id, "avaliacao_reenviada") == [
        (a["avaliador"], link)]

    async with _como(admin_engine, a, "avaliador") as cli:
        r = await cli.post(f"/api/v2/avaliacoes/{pedido['id']}/decisoes", json={"decisoes": [
            {"id_item": novo["id"], "resultado": "aprovado"}]})
        assert r.status_code == 200, r.text
        assert r.json()["situacao"] == "concluida"
    assert (await _pendencias(admin_engine, a)).livre

    async with _sm(admin_engine)() as s:
        acoes = (await s.execute(text(
            "SELECT acao FROM aprimora_py.audit_log WHERE tenant_id=:t "
            "AND acao LIKE 'processo.avaliacao_%' ORDER BY id"), {"t": a["tenant"].id}
        )).scalars().all()
    assert acoes == ["processo.avaliacao_solicitada", "processo.avaliacao_decidida",
                     "processo.avaliacao_reenviada", "processo.avaliacao_decidida"]


# --------------------------------------------------------------------------
# AC-04 — sem atribuição ou sem permissão não decide
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac04_sem_atribuicao_ou_permissao_nao_decide(admin_engine, cen):
    a = cen["a"]
    projeto, *_ = await _tres_documentos(admin_engine, a)
    pedido = (await _pedir(admin_engine, a, [projeto])).json()
    corpo = {"decisoes": [{"id_item": pedido["itens"][0]["id"], "resultado": "aprovado"}]}
    url = f"/api/v2/avaliacoes/{pedido['id']}/decisoes"

    # Tem a transação, mas não foi designado.
    async with _como(admin_engine, a, "colega") as cli:
        r = await cli.post(url, json=corpo)
        assert r.status_code == 403, r.text
        # E a caixa "Para avaliar" dele não mostra o pedido alheio.
        caixa = (await cli.get("/api/v2/avaliacoes", params={"papel": "avaliador"})).json()
        assert caixa["total"] == 0
    # Quem pediu não tem a transação de avaliar.
    async with _como(admin_engine, a) as cli:
        r = await cli.post(url, json=corpo)
        assert r.status_code == 403, r.text
    # O designado que perdeu a transação depois do pedido também não decide.
    async with _sm(admin_engine)() as s:
        await s.execute(text("""
            UPDATE utils.grupo_transacao gt SET excluido = true
              FROM utils.usuario_grupo ug, utils.transacao tr
             WHERE ug.id_usuario = :u AND gt.id_grupo = ug.id_grupo
               AND gt.id_transacao = tr.id AND tr.codigo = 'documento_avaliar'
        """), {"u": a["avaliador"]})
        await s.commit()
    async with _como(admin_engine, a, "avaliador") as cli:
        r = await cli.post(url, json=corpo)
        assert r.status_code == 403, r.text

    async with _como(admin_engine, a) as cli:
        det = (await cli.get(f"/api/v2/avaliacoes/{pedido['id']}")).json()
    assert det["situacao"] == "pendente" and det["itens"][0]["situacao"] == "aguardando"


@pytest.mark.asyncio
async def test_devolucao_exige_justificativa_e_decisao_nao_se_repete(admin_engine, cen):
    a = cen["a"]
    projeto, memorial, _ = await _tres_documentos(admin_engine, a)
    pedido = (await _pedir(admin_engine, a, [projeto, memorial])).json()
    item = {i["id_anexo"]: i["id"] for i in pedido["itens"]}
    url = f"/api/v2/avaliacoes/{pedido['id']}/decisoes"
    async with _como(admin_engine, a, "avaliador") as cli:
        r = await cli.post(url, json={"decisoes": [
            {"id_item": item[projeto], "resultado": "devolvido", "justificativa": "  "}]})
        assert r.status_code == 422, r.text
        r = await cli.post(url, json={"decisoes": [
            {"id_item": item[projeto], "resultado": "aprovado"}]})
        assert r.status_code == 200 and r.json()["situacao"] == "pendente"
        r = await cli.post(url, json={"decisoes": [
            {"id_item": item[projeto], "resultado": "devolvido", "justificativa": JUSTIFICATIVA}]})
        assert r.status_code == 409, r.text
        # Item de outro pedido não entra.
        r = await cli.post(url, json={"decisoes": [{"id_item": 0, "resultado": "aprovado"}]})
        assert r.status_code == 404, r.text


# --------------------------------------------------------------------------
# Quem pode avaliar
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_avaliador_precisa_ser_do_municipio_com_permissao_e_credencial(admin_engine, cen):
    a, b = cen["a"], cen["b"]
    projeto, *_ = await _tres_documentos(admin_engine, a)

    assert (await _pedir(admin_engine, a, [projeto], avaliador="servidor")).status_code == 422
    r = await _pedir(admin_engine, a, [projeto], avaliador="sem_permissao")
    assert r.status_code == 422 and "permissão" in r.json()["detail"]
    async with _como(admin_engine, a) as cli:
        r = await cli.post(f"/api/v2/processos/{a['principal']}/avaliacoes",
                           json={"id_avaliador": b["avaliador"], "id_anexos": [projeto]})
        assert r.status_code == 422, r.text
        r = await cli.post(f"/api/v2/processos/{a['principal']}/avaliacoes",
                           json={"id_avaliador": a["avaliador"], "id_anexos": [projeto],
                                 "prazo": "2020-01-01"})
        assert r.status_code == 422, r.text

    # Processo `interno` (o padrão do cenário é ostensivo): credencial
    # `ostensivo` não alcança.
    async with _sm(admin_engine)() as s:
        await s.execute(text("UPDATE protocolos.processo SET nivel_sigilo='interno' WHERE id=:p"),
                        {"p": a["principal"]})
        await s.commit()
    r = await _pedir(admin_engine, a, [projeto], avaliador="so_ostensivo")
    assert r.status_code == 422 and "sigilo" in r.json()["detail"]
    # Não precisa ser da unidade do processo: o colega de outra lotação serve.
    async with _sm(admin_engine)() as s:
        await s.execute(text("UPDATE utils.usuario SET id_unidade_trabalho=NULL WHERE id=:u"),
                        {"u": a["colega"]})
        await s.commit()
    assert (await _pedir(admin_engine, a, [projeto], avaliador="colega")).status_code == 201
    assert not await _avisos(admin_engine, b["tenant"].id, "avaliacao_solicitada")


# --------------------------------------------------------------------------
# O documento em avaliação: versão exata, sem versão nova, sem exclusão
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_documento_em_avaliacao_nao_recebe_versao_nem_sai(admin_engine, cen):
    a = cen["a"]
    projeto, memorial, art = await _tres_documentos(admin_engine, a)
    pedido = (await _pedir(admin_engine, a, [projeto])).json()

    async with _como(admin_engine, a) as cli:
        r = await _nova_versao(cli, a["principal"], projeto)
        assert r.status_code == 409 and "avaliação" in r.json()["detail"]
        r = await cli.delete(f"/api/v2/processos/{a['principal']}/anexos/{projeto}")
        assert r.status_code == 400, r.text
        det = (await cli.get(f"/api/v2/processos/{a['principal']}")).json()
        na_lista = next(x for x in det["anexos"] if x["id"] == projeto)
        assert na_lista["aceita_nova_versao"] is False
        assert na_lista["avaliacao"] == "aguardando"
        assert next(x for x in det["anexos"] if x["id"] == memorial)["avaliacao"] is None
    # Outro pedido para o mesmo documento, ainda aguardando: 409.
    assert (await _pedir(admin_engine, a, [projeto, memorial])).status_code == 409

    async with _como(admin_engine, a, "avaliador") as cli:
        await cli.post(f"/api/v2/avaliacoes/{pedido['id']}/decisoes", json={"decisoes": [
            {"id_item": pedido["itens"][0]["id"], "resultado": "aprovado"}]})
    async with _como(admin_engine, a) as cli:
        # Aprovado é histórico: não sai, mas aceita versão nova (que nasce sem aprovação).
        r = await cli.delete(f"/api/v2/processos/{a['principal']}/anexos/{projeto}")
        assert r.status_code == 400, r.text
        v2 = await _nova_versao(cli, a["principal"], projeto)
        assert v2.status_code == 201, v2.text
        # A versão substituída não pode mais ser pedida: só a vigente.
        assert (await _pedir(admin_engine, a, [projeto])).status_code == 409
        # Documento sem avaliação continua podendo sair.
        r = await cli.delete(f"/api/v2/processos/{a['principal']}/anexos/{art}")
        assert r.status_code == 204, r.text
    assert (await _pedir(admin_engine, a, [v2.json()["id"]])).status_code == 201


# --------------------------------------------------------------------------
# Sigilo e outra prefeitura
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sigilo_e_outra_prefeitura_dao_404(admin_engine, cen):
    a, b = cen["a"], cen["b"]
    projeto, *_ = await _tres_documentos(admin_engine, a)
    pedido = (await _pedir(admin_engine, a, [projeto])).json()
    corpo = {"decisoes": [{"id_item": pedido["itens"][0]["id"], "resultado": "aprovado"}]}

    # Avaliador da prefeitura B, com a transação, não alcança o pedido da A.
    async with _como(admin_engine, b, "avaliador") as cli:
        assert (await cli.get(f"/api/v2/avaliacoes/{pedido['id']}")).status_code == 404
        r = await cli.post(f"/api/v2/avaliacoes/{pedido['id']}/decisoes", json=corpo)
        assert r.status_code == 404, r.text
        r = await cli.get(f"/api/v2/processos/{a['principal']}/avaliacoes")
        assert r.status_code == 404 or r.json() == []

    # O processo sobe para `reservado`, acima da credencial `interno` de todos:
    # o pedido some até para o avaliador designado — sem confirmar que existe.
    async with _sm(admin_engine)() as s:
        await s.execute(text("UPDATE protocolos.processo SET nivel_sigilo='reservado' "
                             "WHERE id=:p"), {"p": a["principal"]})
        await s.commit()
    async with _como(admin_engine, a, "avaliador") as cli:
        assert (await cli.get(f"/api/v2/avaliacoes/{pedido['id']}")).status_code == 404
        r = await cli.post(f"/api/v2/avaliacoes/{pedido['id']}/decisoes", json=corpo)
        assert r.status_code == 404, r.text
        caixa = (await cli.get("/api/v2/avaliacoes", params={"papel": "avaliador"})).json()
        assert caixa["total"] == 0
    async with _como(admin_engine, a) as cli:
        r = await cli.get(f"/api/v2/processos/{a['principal']}/avaliacoes")
        assert r.status_code == 404, r.text
        r = await cli.post(f"/api/v2/processos/{a['reservado']}/avaliacoes",
                           json={"id_avaliador": a["avaliador"], "id_anexos": [projeto]})
        assert r.status_code == 404, r.text
