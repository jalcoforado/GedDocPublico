"""Ações em lote sobre processos selecionados (`services/processos_lote.py`).

O que este arquivo existe para pegar:

- **Lote com regra própria.** Cada processo tem de passar pela mesma função e
  pelo mesmo guard de sigilo da ação individual. Os testes usam casos que a
  ação individual recusa (outra unidade, nada pendente, já arquivado, sigilo)
  e conferem que o lote recusa igual.
- **Tudo-ou-nada por engano.** Uma falha no meio não pode desfazer os que já
  deram certo, nem impedir os seguintes.
- **Vazamento pelo erro.** Processo acima da credencial vira "não
  encontrado", nunca "sem permissão".
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select, text

from app.auth.deps import get_current_user
from app.main import app
from app.models import Usuario
from app.schemas.processo import ArquivarRequest, CaixaProcesso, LoteRequest
from app.services.processos import contar_caixas
from app.services.processos_lote import executar_lote
from tests.conftest import arreio_tenant_http
from tests.test_processo_caixas import _como, _ids, _sm, cen  # noqa: F401 — fixture


async def _lote(engine, cen, pedido: LoteRequest, *, por: str = "operador", su: bool = False):
    async with _sm(engine)() as s:
        usuario = (await s.execute(select(Usuario).where(Usuario.id == cen[por]))).scalar_one()
        return await executar_lote(
            s, pedido, tenant_id=cen["tenant"].id, usuario=usuario, is_super_usuario=su)


def _por_rotulo(cen, resultado) -> dict[str, tuple[bool, str | None]]:
    rotulo = {v: k for k, v in cen["procs"].items()}
    return {rotulo[i.id]: (i.ok, i.erro) for i in resultado.itens}


@pytest.mark.asyncio
async def test_receber_em_lote_aplica_a_regra_de_cada_um_e_nao_para_na_falha(admin_engine, cen):
    """`chegando` vem de B para A: o operador, de A, recebe. `saindo` vai para
    B: não é dele. `na_mesa` não tem nada pendente. A falha do meio não
    impede o terceiro."""
    p = cen["procs"]
    r = await _lote(admin_engine, cen, LoteRequest(
        acao="receber", ids=[p["saindo"], p["chegando"], p["na_mesa"]]))

    assert (r.concluidos, r.falhas) == (1, 2)
    res = _por_rotulo(cen, r)
    assert res["chegando"] == (True, None)
    assert res["saindo"][0] is False and "unidade de destino" in res["saindo"][1]
    assert res["na_mesa"][0] is False and "Nenhum encaminhamento pendente" in res["na_mesa"][1]
    # Na ordem do pedido.
    assert [i.id for i in r.itens] == [p["saindo"], p["chegando"], p["na_mesa"]]
    assert "chegando" in await _ids(admin_engine, cen, CaixaProcesso.analise)


@pytest.mark.asyncio
async def test_encaminhar_em_lote_leva_todos_para_o_mesmo_destino(admin_engine, cen):
    from app.schemas.processo import EncaminharRequest

    p = cen["procs"]
    antes = await _ids(admin_engine, cen, CaixaProcesso.saida)
    r = await _lote(admin_engine, cen, LoteRequest(
        acao="encaminhar", ids=[p["na_mesa"], p["externo"]],
        encaminhar=EncaminharRequest(id_unidade_destino=cen["b"], id_prioridade=cen["prioridade"]),
    ), su=True)

    assert (r.concluidos, r.falhas) == (2, 0)
    assert await _ids(admin_engine, cen, CaixaProcesso.saida) == antes | {"na_mesa", "externo"}


@pytest.mark.asyncio
async def test_arquivar_em_lote_recusa_o_que_ja_estava_arquivado(admin_engine, cen):
    p = cen["procs"]
    r = await _lote(admin_engine, cen, LoteRequest(
        acao="arquivar", ids=[p["na_mesa"], p["arquivado"]],
        arquivar=ArquivarRequest(motivo="Demanda atendida")), su=True)

    res = _por_rotulo(cen, r)
    assert res["na_mesa"] == (True, None)
    assert res["arquivado"][0] is False and "já está arquivado" in res["arquivado"][1]
    async with _sm(admin_engine)() as s:
        caixas = await contar_caixas(
            s, tenant_id=cen["tenant"].id,
            id_usuario_contexto=cen["operador"], id_unidade_contexto=cen["a"])
    assert caixas.arquivados == 2


@pytest.mark.asyncio
async def test_atribuir_responsavel_em_lote(admin_engine, cen):
    from app.schemas.processo import AtribuirResponsavelRequest

    p = cen["procs"]
    r = await _lote(admin_engine, cen, LoteRequest(
        acao="atribuir_responsavel", ids=[p["na_mesa"], p["externo"]],
        responsavel=AtribuirResponsavelRequest(id_usuario=cen["operador"])))

    assert (r.concluidos, r.falhas) == (2, 0)
    async with _sm(admin_engine)() as s:
        responsaveis = (await s.execute(text(
            "SELECT id_usuario_responsavel FROM protocolos.processo WHERE id = ANY(:ids)"),
            {"ids": [p["na_mesa"], p["externo"]]})).scalars().all()
    assert responsaveis == [cen["operador"], cen["operador"]]


@pytest.mark.asyncio
async def test_processo_acima_da_credencial_vira_nao_encontrado(admin_engine, cen):
    """`sigiloso` é secreto; o operador comum não alcança. O erro não pode
    dizer que o processo existe."""
    from app.schemas.processo import AtribuirResponsavelRequest

    p = cen["procs"]
    async with _sm(admin_engine)() as s:
        await s.execute(text(
            "UPDATE utils.usuario SET nivel_acesso_sigilo=:n WHERE id=:u"),
            {"n": "interno", "u": cen["operador"]})
        await s.commit()
    r = await _lote(admin_engine, cen, LoteRequest(
        acao="atribuir_responsavel", ids=[p["sigiloso"], p["na_mesa"]],
        responsavel=AtribuirResponsavelRequest(id_usuario=cen["operador"])))

    res = _por_rotulo(cen, r)
    assert res["sigiloso"] == (False, "Processo não encontrado")
    assert res["na_mesa"] == (True, None)
    async with _sm(admin_engine)() as s:
        responsavel = (await s.execute(text(
            "SELECT id_usuario_responsavel FROM protocolos.processo WHERE id=:p"),
            {"p": p["sigiloso"]})).scalar_one()
    assert responsavel is None


def test_cada_acao_exige_o_seu_corpo_e_a_selecao_e_limitada():
    with pytest.raises(ValidationError, match="exige o campo 'encaminhar'"):
        LoteRequest(acao="encaminhar", ids=[1])
    with pytest.raises(ValidationError, match="exige o campo 'responsavel'"):
        LoteRequest(acao="atribuir_responsavel", ids=[1])
    with pytest.raises(ValidationError, match="repetidos"):
        LoteRequest(acao="receber", ids=[1, 1])
    with pytest.raises(ValidationError):
        LoteRequest(acao="receber", ids=[])
    with pytest.raises(ValidationError):
        LoteRequest(acao="receber", ids=list(range(1, 102)))
    assert LoteRequest(acao="receber", ids=[1, 2]).acao == "receber"


@pytest.mark.asyncio
async def test_http_usuario_comum_recebe_em_lote(admin_engine, cen):
    """Pela borda, com operador não-SU; falha parcial é 200 com o detalhe."""
    t = cen["tenant"]
    p = cen["procs"]
    app.dependency_overrides[get_current_user] = _como(admin_engine, cen["operador"])
    arreio_tenant_http(t.id, t.slug)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v2/processos/lote", json={
            "acao": "receber", "ids": [p["chegando"], p["saindo"]]})
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert (corpo["concluidos"], corpo["falhas"]) == (1, 1)

        invalido = await client.post("/api/v2/processos/lote", json={
            "acao": "arquivar", "ids": [p["na_mesa"]]})
        assert invalido.status_code == 422, invalido.text
