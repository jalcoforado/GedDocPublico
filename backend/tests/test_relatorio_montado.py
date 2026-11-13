"""Relatório montado pela própria pessoa (SI-35).

O card pede três coisas; cada uma tem teste aqui:

1. escolher colunas e filtros e ver o resultado — e o resultado é o MESMO das
   telas de origem (documentação, atraso da tramitação, assinaturas);
2. salvar com um nome e abrir de novo — e só a própria pessoa abre o seu
   (o de outra pessoa ou de outra prefeitura é 404);
3. cada pessoa vê só o que já pode ver — o sigilo vale na tela, no CSV e no
   PDF, e vale NA HORA DE ABRIR: credencial rebaixada some com o processo do
   relatório salvo no mesmo dia.

E as travas do catálogo: coluna fora da lista é 422, e não há coluna de dado
pessoal além do nome do manifestante (decisão do PO, 2026-11-12).

HTTP de propósito, com usuário comum: a costura router↔service é onde o
filtro some, e o bypass de super-usuário esconde defeito (CLAUDE.md).
"""
from __future__ import annotations

import json
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.main import app
from app.schemas.relatorio_montado import PeriodoMontado
from app.services.relatorios_montado import CATALOGO, normalizar_definicao, resolver_periodo
from tests.test_relatorios_protocolo_acesso import _cenario, _cliente_como, _fechar, _ids, _sm
from tests.test_relatorios_protocolo_filtros import _documentacao
from tests.test_relatorios_protocolo_medidas import (  # noqa: F401
    _get,
    _monta_prazo,
    _solicitacoes,
    cen,
)

URL = "/api/v2/relatorios"
TODAS = list(CATALOGO)
OUTUBRO = {"tipo": "fixo", "desde": "2026-10-01", "ate": "2026-10-31"}


def _d(colunas=None, **kw) -> str:
    return json.dumps({"colunas": colunas or ["situacao"], **kw})


async def _montado(c: AsyncClient | None = None, fmt: str = "json", **params):
    if c is None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cli:
            return await cli.get(f"{URL}/montado.{fmt}", params=params)
    return await c.get(f"{URL}/montado.{fmt}", params=params)


def _ids_linhas(r) -> set[int]:
    return {ln["id"] for ln in r.json()["linhas"]}


# ------------------------------------------------------------------ sigilo


@pytest.mark.asyncio
async def test_sigilo_de_quem_consulta_na_tela_no_csv_e_no_pdf(admin_engine):
    cen_ = await _cenario(admin_engine, "monsig")
    try:
        async with await _cliente_como(admin_engine, cen_, "comum") as c:
            r = await _montado(c, d=_d(TODAS))
            csv = await _montado(c, "csv", d=_d(TODAS))
            pdf = await _montado(c, "pdf", d=_d(TODAS))
        assert r.status_code == 200, r.text
        # rascunho de outra pessoa também fica de fora
        assert _ids_linhas(r) == _ids(cen_, "ostensivo", "interno")
        assert r.json()["totais"]["total"] == 2
        assert csv.status_code == 200, csv.text
        assert cen_["processos"]["reservado"][1] not in csv.text
        assert cen_["processos"]["ostensivo"][1] in csv.text
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_relatorio_salvo_segue_a_credencial_de_hoje(admin_engine):
    """Salva vendo o processo `interno`; perde a credencial; reabre — sumiu.
    O salvo guarda a definição, não os dados."""
    cen_ = await _cenario(admin_engine, "moncred")
    try:
        async with await _cliente_como(admin_engine, cen_, "comum") as c:
            criado = await c.post(f"{URL}/salvos", json={
                "nome": "Meus processos", "definicao": {"colunas": ["situacao", "assunto"]},
            })
            assert criado.status_code == 201, criado.text
            antes = await _montado(c, d=json.dumps(criado.json()["definicao"]))
            assert _ids_linhas(antes) == _ids(cen_, "ostensivo", "interno")

            async with _sm(admin_engine)() as s:
                await s.execute(text(
                    "UPDATE utils.usuario SET nivel_acesso_sigilo='ostensivo' WHERE id=:u"
                ), {"u": cen_["comum"]})
                await s.commit()

            salvo = await c.get(f"{URL}/salvos/{criado.json()['id']}")
            depois = await _montado(c, d=json.dumps(salvo.json()["definicao"]))
        assert _ids_linhas(depois) == _ids(cen_, "ostensivo")
    finally:
        await _fechar()


# ------------------------------------------------------- dono do relatório


@pytest.mark.asyncio
async def test_relatorio_de_outra_pessoa_e_404_e_nao_aparece_na_lista(admin_engine):
    cen_ = await _cenario(admin_engine, "mondono")
    try:
        async with await _cliente_como(admin_engine, cen_, "admin") as c:
            do_admin = await c.post(f"{URL}/salvos", json={
                "nome": "Do admin", "definicao": {"colunas": ["situacao"]},
            })
            assert do_admin.status_code == 201, do_admin.text
        id_ = do_admin.json()["id"]
        async with await _cliente_como(admin_engine, cen_, "comum") as c:
            lista = await c.get(f"{URL}/salvos")
            ver = await c.get(f"{URL}/salvos/{id_}")
            mudar = await c.put(f"{URL}/salvos/{id_}", json={"nome": "Meu agora"})
            apagar = await c.delete(f"{URL}/salvos/{id_}")
        assert lista.status_code == 200 and lista.json() == []
        assert (ver.status_code, mudar.status_code, apagar.status_code) == (404, 404, 404)
        # e continua lá, intacto, para o dono
        async with await _cliente_como(admin_engine, cen_, "admin") as c:
            dono = await c.get(f"{URL}/salvos/{id_}")
        assert dono.status_code == 200 and dono.json()["nome"] == "Do admin"
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_relatorio_de_outra_prefeitura_e_404(admin_engine):
    a = await _cenario(admin_engine, "monpa")
    b = await _cenario(admin_engine, "monpb")
    try:
        async with await _cliente_como(admin_engine, a, "admin") as c:
            id_ = (await c.post(f"{URL}/salvos", json={
                "nome": "Da prefeitura A", "definicao": {"colunas": ["situacao"]},
            })).json()["id"]
        async with await _cliente_como(admin_engine, b, "admin") as c:
            r = await c.get(f"{URL}/salvos/{id_}")
        assert r.status_code == 404
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_salvar_renomear_e_excluir(admin_engine):
    cen_ = await _cenario(admin_engine, "moncrud")
    try:
        async with await _cliente_como(admin_engine, cen_, "comum") as c:
            um = await c.post(f"{URL}/salvos", json={
                "nome": "  Alvarás   do mês ", "definicao": {
                    "colunas": ["assunto"], "periodo": {"tipo": "mes_atual"}, "agrupar_por": "assunto",
                },
            })
            assert um.status_code == 201, um.text
            assert um.json()["nome"] == "Alvarás do mês"
            assert um.json()["definicao"]["periodo"]["tipo"] == "mes_atual"
            # mesmo nome, outra caixa: 409
            dup = await c.post(f"{URL}/salvos", json={
                "nome": "ALVARÁS DO MÊS", "definicao": {"colunas": ["assunto"]},
            })
            assert dup.status_code == 409
            ren = await c.put(f"{URL}/salvos/{um.json()['id']}", json={"nome": "Alvarás"})
            assert ren.status_code == 200 and ren.json()["nome"] == "Alvarás"
            assert [x["nome"] for x in (await c.get(f"{URL}/salvos")).json()] == ["Alvarás"]
            assert (await c.delete(f"{URL}/salvos/{um.json()['id']}")).status_code == 204
            assert (await c.get(f"{URL}/salvos")).json() == []
    finally:
        await _fechar()


# ---------------------------------------------------------------- catálogo


@pytest.mark.asyncio
async def test_coluna_ou_chave_fora_do_catalogo_e_recusada(admin_engine):
    cen_ = await _cenario(admin_engine, "moncat")
    try:
        async with await _cliente_como(admin_engine, cen_, "comum") as c:
            cpf = await _montado(c, d=_d(["cpf_cnpj"]))
            chave = await _montado(c, d=json.dumps({"colunas": ["situacao"], "sql": "1=1"}))
            filtro = await _montado(c, d=json.dumps({"colunas": ["situacao"], "filtros": {"email": "x"}}))
            salvo = await c.post(f"{URL}/salvos", json={
                "nome": "x", "definicao": {"colunas": ["telefone_celular"]},
            })
        assert (cpf.status_code, chave.status_code, filtro.status_code, salvo.status_code) == (
            422, 422, 422, 422
        )
    finally:
        await _fechar()


def test_catalogo_nao_tem_dado_pessoal_alem_do_nome():
    proibidos = ("cpf", "cnpj", "telefone", "email", "e_mail", "observacao", "corpo", "despacho",
                 "fundamento", "endereco")
    assert not [c for c in CATALOGO if any(p in c for p in proibidos)]


@pytest.mark.asyncio
async def test_csv_com_todas_as_colunas_nao_leva_cpf_nem_contato(admin_engine):
    cen_ = await _cenario(admin_engine, "monpii")
    try:
        async with _sm(admin_engine)() as s:
            await s.execute(text(
                "UPDATE protocolos.manifestante SET cpf_cnpj='52998224725', "
                "email='maria@exemplo.test', telefone_celular='85999990000' WHERE tenant_id=:t"
            ), {"t": cen_["tenant"].id})
            await s.commit()
        async with await _cliente_como(admin_engine, cen_, "admin") as c:
            csv = await _montado(c, "csv", d=_d(TODAS))
        assert csv.status_code == 200, csv.text
        assert "Maria Relatorio" in csv.text  # o nome entra
        for dado in ("52998224725", "529.982.247-25", "maria@exemplo.test", "85999990000"):
            assert dado not in csv.text
    finally:
        await _fechar()


def test_definicao_salva_com_coluna_que_saiu_abre_com_aviso():
    d, avisos = normalizar_definicao({"colunas": ["assunto", "coluna_antiga"], "ordem": "sumiu"})
    assert d is not None and d.colunas == ["assunto"] and d.ordem is None
    assert any("coluna_antiga" in a for a in avisos)
    ilegivel, avisos = normalizar_definicao({"colunas": ["assunto"], "periodo": {"tipo": "fixo"}})
    assert ilegivel is None and avisos


@pytest.mark.parametrize("periodo,esperado", [
    ({"tipo": "sem"}, (None, None)),
    ({"tipo": "fixo", "desde": "2026-10-01", "ate": "2026-10-31"}, (date(2026, 10, 1), date(2026, 10, 31))),
    ({"tipo": "ultimos_dias", "dias": 30}, (date(2026, 10, 14), date(2026, 11, 12))),
    ({"tipo": "mes_atual"}, (date(2026, 11, 1), date(2026, 11, 12))),
    ({"tipo": "mes_anterior"}, (date(2026, 10, 1), date(2026, 10, 31))),
    ({"tipo": "ano_atual"}, (date(2026, 1, 1), date(2026, 11, 12))),
])
def test_periodo_relativo_e_resolvido_no_dia_em_que_abre(periodo, esperado):
    assert resolver_periodo(PeriodoMontado(**periodo), date(2026, 11, 12)) == esperado


def test_mes_anterior_em_janeiro_e_dezembro_do_ano_passado():
    assert resolver_periodo(PeriodoMontado(tipo="mes_anterior"), date(2027, 1, 5)) == (
        date(2026, 12, 1), date(2026, 12, 31)
    )


# ---------------------------------- mesmos números das telas de origem


@pytest.mark.asyncio
async def test_todas_as_colunas_saem_e_contas_fecham(cen):
    r = await _montado(d=_d(TODAS, periodo=OUTUBRO, agrupar_por="unidade_dona"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert all(set(ln["valores"]) == set(TODAS) for ln in body["linhas"])
    t = body["totais"]
    assert t["total"] == t["em_andamento"] + t["em_transito"] + t["arquivados"]
    assert sum(g["count"] for g in body["agrupamento"]) == t["total"]
    # o mesmo recorte da lista de processos, com o mesmo filtro
    lista = await _get("processos.json", desde="2026-10-01", ate="2026-10-31")
    assert _ids_linhas(r) == {p["id"] for p in lista.json()["processos"]}


@pytest.mark.asyncio
async def test_atraso_e_o_mesmo_da_tela_de_tramitacao(cen, admin_engine):
    await _monta_prazo(cen, admin_engine)
    r = await _montado(d=_d(["tram_atrasos", "tram_envios"], filtros={"com_atraso": True}))
    assert r.status_code == 200, r.text
    tram = await _get("tramitacao.json", com_atraso="true")
    assert _ids_linhas(r) == {p["id"] for p in tram.json()["processos"]} == {
        cen["procs"]["depois_do_prazo"]
    }
    (linha,) = r.json()["linhas"]
    assert linha["valores"] == {"tram_atrasos": 1, "tram_envios": 2}


@pytest.mark.asyncio
async def test_assinaturas_colunas_e_filtro_pendente(cen, admin_engine):
    await _solicitacoes(cen, admin_engine)
    r = await _montado(
        d=_d(["ass_pedidas", "ass_concluidas", "ass_pendentes"], filtros={"assinatura_pendente": True})
    )
    assert r.status_code == 200, r.text
    # `noite` pendente; `sem_fim` (realizada sem data de fim) também é pendente
    assert _ids_linhas(r) == {cen["procs"]["noite_10"], cen["procs"]["dia_11"]}
    por_id = {ln["id"]: ln["valores"] for ln in r.json()["linhas"]}
    assert por_id[cen["procs"]["dia_11"]] == {"ass_pedidas": 2, "ass_concluidas": 1, "ass_pendentes": 1}


@pytest.mark.asyncio
async def test_documentacao_igual_a_lista_de_documentacao(cen, admin_engine):
    await _documentacao(cen, admin_engine)
    for status, visao in (("pendente", "doc_pendente"), ("parcial", "doc_parcial"), ("completo", "doc_completo")):
        r = await _montado(d=_d(["doc_situacao", "doc_obrigatorios"], filtros={"documentacao": status}))
        doc = await _get("documentacao.json", visao=visao)
        assert r.status_code == 200, r.text
        assert _ids_linhas(r) == {p["id"] for p in doc.json()["processos"]}, status
    aguardando = await _montado(d=_d(["complementacao"], filtros={"complementacao_aberta": True}))
    doc = await _get("documentacao.json", visao="compl_aberta")
    assert _ids_linhas(aguardando) == {p["id"] for p in doc.json()["processos"]}
    assert {ln["valores"]["complementacao"] for ln in aguardando.json()["linhas"]} == {"Aguardando o cidadão"}


@pytest.mark.asyncio
async def test_csv_acima_do_teto_e_recusado(cen):
    r = await _montado(fmt="csv", d=_d(), max_rows=1)
    assert r.status_code == 422 and "CSV vai até 1" in r.json()["detail"]
