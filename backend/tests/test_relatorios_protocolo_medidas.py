"""Relatórios de protocolo — o que cada número mede (SI-34).

Cada teste aqui fixa uma decisão de medida que, errada, produz número
plausível e falso — o tipo de defeito que ninguém percebe olhando a tela:

- período em DIA LOCAL: aberto às 23:30 de 10/10 em Brasília é 02:30 de 11/10
  em UTC, e pertence ao dia 10;
- situação real (em andamento / em trânsito / arquivado), não `Processo.ativo`,
  que nenhum caminho escreve;
- unidade em quatro sentidos; "passou" conta quem RECEBEU, não quem só foi
  destino de envio pendente ou recusado;
- período pela data de arquivamento;
- lista com teto avisa que cortou; CSV recusa em vez de cortar;
- atraso na tramitação = saiu da unidade depois do FIM do dia do prazo.

Horários gravados em UTC ingênuo, como o sistema grava.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from tests.conftest import admin_id_do_tenant, as_user_dependency, provisionar_tenant_de_teste

URL = "/api/v2/relatorios"


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def cen(admin_engine):
    t = await provisionar_tenant_de_teste(admin_engine, "relmed")
    async with _sm(admin_engine)() as s:

        async def q(sql, **p):
            return await s.execute(text(sql), {"t": t.id, **p})

        unid = {"A": (await q(
            "SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t ORDER BY id LIMIT 1"
        )).scalar_one()}
        tipo_unid = (await q(
            "SELECT id_tipo_unidade_trabalho FROM utils.unidade_trabalho WHERE id=:u", u=unid["A"]
        )).scalar_one()
        for nome in ("B", "C"):
            unid[nome] = (await q(
                "INSERT INTO utils.unidade_trabalho (tenant_id, unidade_trabalho, excluido, "
                "id_tipo_unidade_trabalho) VALUES (:t, :n, false, :tu) RETURNING id",
                n=f"Unidade {nome}", tu=tipo_unid,
            )).scalar_one()
        tipo_manif = (await q(
            "SELECT id FROM protocolos.tipo_manifestante WHERE tenant_id=:t ORDER BY id LIMIT 1"
        )).scalar_one()
        manif = (await q(
            "INSERT INTO protocolos.manifestante (tenant_id, id_tipo_manifestante, nome, ativo, "
            "excluido) VALUES (:t, :tm, 'Maria', true, false) RETURNING id", tm=tipo_manif,
        )).scalar_one()
        tipo_proc = (await q(
            "INSERT INTO protocolos.tipo_processo (tenant_id, tipo_processo, ativo, excluido) "
            "VALUES (:t, 'Geral', true, false) RETURNING id"
        )).scalar_one()
        assunto = (await q(
            "INSERT INTO protocolos.assunto (tenant_id, assunto, id_tipo_processo, ativo, excluido) "
            "VALUES (:t, 'Pedido', :tp, true, false) RETURNING id", tp=tipo_proc,
        )).scalar_one()
        admin = await admin_id_do_tenant(admin_engine, t.id)
        # Prioridade é catálogo GLOBAL: cria a própria e apaga no fim.
        prio = (await q(
            "INSERT INTO protocolos.prioridade (prioridade, fator, cor, ativo, excluido) "
            "VALUES (:n, 1, '#999999', true, false) RETURNING id", n=f"rel-{uuid.uuid4().hex[:6]}",
        )).scalar_one()
        acao = {f: (await q("SELECT id FROM protocolos.acao WHERE flag=:f", f=f)).scalar_one()
                for f in ("ENCAMINHAMENTO", "ARQUIVAMENTO")}
        status_arq = (await q(
            "SELECT id FROM protocolos.status_arquivamento WHERE excluido = false ORDER BY id LIMIT 1"
        )).scalar_one()

        procs: dict[str, int] = {}

        async def processo(rotulo, abertura, dona, local, ativo=True):
            procs[rotulo] = (await q(
                """
                INSERT INTO protocolos.processo
                    (tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria,
                     id_local_atual, numero_processo, nivel_sigilo, situacao, id_usuario,
                     virtual, externo, ativo, excluido, migrado, data_hora_abertura)
                VALUES (:t, :a, :m, :d, :l, :n, 'ostensivo', 'protocolado', :u,
                        true, false, :ativo, false, false, :ab)
                RETURNING id
                """,
                a=assunto, m=manif, d=unid[dona], l=unid[local], u=admin, ativo=ativo, ab=abertura,
                n=f"{rotulo}-{uuid.uuid4().hex[:4]}",
            )).scalar_one()

        async def envio(rotulo, origem, destino, enviado, recebido=None, prazo=None, recusado=False):
            mov = (await q(
                "INSERT INTO protocolos.movimentacao (tenant_id, id_processo, id_unidade_responsavel, "
                "id_acao, data_hora_movimentacao) VALUES (:t, :p, :o, :ac, :em) RETURNING id",
                p=procs[rotulo], o=unid[origem], ac=acao["ENCAMINHAMENTO"], em=enviado,
            )).scalar_one()
            await q(
                """
                INSERT INTO protocolos.encaminhamento
                    (tenant_id, id_processo, id_unidade_origem, id_unidade_destino, id_prioridade,
                     id_usuario, id_movimentacao, data_prazo, recebido, data_hora_recebimento,
                     cancelado, recusado, motivo_recusa, data_hora_recusa)
                VALUES (:t, :p, :o, :d, :pr, :u, :mv, :prazo, :rec, :drec,
                        :rcs, :rcs, :mot, :drcs)
                """,
                p=procs[rotulo], o=unid[origem], d=unid[destino], pr=prio, u=admin, mv=mov,
                prazo=prazo, rec=recebido is not None, drec=recebido, rcs=recusado,
                mot="não é nosso" if recusado else None, drcs=enviado if recusado else None,
            )

        # Período em dia local
        await processo("noite_10", datetime(2026, 10, 11, 2, 30), "A", "A", ativo=False)
        await processo("dia_11", datetime(2026, 10, 11, 15, 0), "A", "A")
        # Unidade: A → B (recebido) → C (recebido)
        await processo("passou", datetime(2026, 10, 1, 13, 0), "A", "C")
        await envio("passou", "A", "B", datetime(2026, 10, 2, 13, 0), recebido=datetime(2026, 10, 2, 14, 0))
        await envio("passou", "B", "C", datetime(2026, 10, 3, 13, 0), recebido=datetime(2026, 10, 3, 14, 0))
        # Envio pendente e envio recusado para B: B nunca esteve com eles
        await processo("pendente", datetime(2026, 10, 1, 13, 0), "A", "A")
        await envio("pendente", "A", "B", datetime(2026, 10, 2, 13, 0))
        await processo("recusado", datetime(2026, 10, 1, 13, 0), "A", "A")
        await envio("recusado", "A", "B", datetime(2026, 10, 2, 13, 0), recusado=True)
        # Arquivado (em B), em 20/10 local
        await processo("arquivado", datetime(2026, 10, 1, 13, 0), "B", "B")
        arq = (await q(
            "INSERT INTO protocolos.arquivamento (tenant_id, id_status_arquivamento, id_usuario) "
            "VALUES (:t, :s, :u) RETURNING id", s=status_arq, u=admin,
        )).scalar_one()
        await q(
            "INSERT INTO protocolos.movimentacao (tenant_id, id_processo, id_unidade_responsavel, "
            "id_acao, id_arquivamento, data_hora_movimentacao) VALUES (:t, :p, :o, :ac, :arq, :em)",
            p=procs["arquivado"], o=unid["B"], ac=acao["ARQUIVAMENTO"], arq=arq,
            em=datetime(2026, 10, 20, 15, 0),
        )
        await s.commit()

    as_user_dependency(admin_engine, admin, t.id, t.slug)()
    yield {"tenant": t, "unid": unid, "procs": procs, "prio": prio}
    app.dependency_overrides.clear()
    from app.database import engine

    await engine.dispose()
    async with _sm(admin_engine)() as s:
        await s.execute(text("DELETE FROM protocolos.encaminhamento WHERE id_prioridade=:p"), {"p": prio})
        await s.execute(text("DELETE FROM protocolos.prioridade WHERE id=:p"), {"p": prio})
        await s.commit()


async def _get(path: str, **params):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        return await c.get(f"{URL}/{path}", params=params)


def _ids(r) -> set[int]:
    return {p["id"] for p in r.json()["processos"]}


@pytest.mark.asyncio
async def test_periodo_conta_o_dia_local_de_brasilia(cen):
    p = cen["procs"]
    dia10 = await _get("processos.json", desde="2026-10-10", ate="2026-10-10")
    dia11 = await _get("processos.json", desde="2026-10-11", ate="2026-10-11")
    assert _ids(dia10) == {p["noite_10"]}, "23:30 de 10/10 em Brasília é do dia 10"
    assert _ids(dia11) == {p["dia_11"]}
    # e a hora sai em Brasília, não em UTC
    linha = next(x for x in dia10.json()["processos"] if x["id"] == p["noite_10"])
    assert linha["data_hora_abertura"].startswith("2026-10-10T23:30")


@pytest.mark.asyncio
async def test_periodo_invertido_e_recusado(cen):
    r = await _get("processos.json", desde="2026-10-11", ate="2026-10-10")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_totais_pela_situacao_real_e_nao_pelo_campo_ativo(cen):
    r = (await _get("processos.json")).json()
    # `noite_10` tem ativo=false no banco e NÃO está arquivado: conta em andamento
    assert r["totais"] == {
        "total": 6, "em_andamento": 4, "em_transito": 1, "arquivados": 1,
        "sigilosos": 0, "externos": 0,
    }
    situacoes = {x["id"]: x["situacao"] for x in r["processos"]}
    assert situacoes[cen["procs"]["noite_10"]] == "em_andamento"
    assert situacoes[cen["procs"]["pendente"]] == "em_transito"
    assert situacoes[cen["procs"]["arquivado"]] == "arquivado"


@pytest.mark.asyncio
@pytest.mark.parametrize("modo,unidade,esperado", [
    ("dona", "B", {"arquivado"}),
    ("atual", "B", {"arquivado"}),
    ("envolvida", "B", {"arquivado"}),
    # passou: recebeu `passou`; pendente e recusado nunca estiveram em B
    ("passou", "B", {"arquivado", "passou"}),
    ("atual", "C", {"passou"}),
    ("envolvida", "A", {"noite_10", "dia_11", "passou", "pendente", "recusado"}),
])
async def test_unidade_nos_quatro_sentidos(cen, modo, unidade, esperado):
    r = await _get("processos.json", id_unidade=cen["unid"][unidade], modo_unidade=modo)
    assert _ids(r) == {cen["procs"][x] for x in esperado}
    assert r.json()["totais"]["total"] == len(esperado)


@pytest.mark.asyncio
async def test_periodo_pela_data_de_arquivamento(cen):
    no_dia = await _get("processos.json", desde="2026-10-20", ate="2026-10-20", data_base="arquivamento")
    vespera = await _get("processos.json", desde="2026-10-19", ate="2026-10-19", data_base="arquivamento")
    assert _ids(no_dia) == {cen["procs"]["arquivado"]}
    assert _ids(vespera) == set()
    assert no_dia.json()["processos"][0]["data_hora_arquivamento"].startswith("2026-10-20T12:00")
    # "chegada" é da tramitação; aqui não existe
    assert (await _get("processos.json", data_base="chegada")).status_code == 422


@pytest.mark.asyncio
async def test_lista_cortada_avisa_e_csv_recusa_em_vez_de_cortar(cen):
    r = (await _get("processos.json", max_rows=2)).json()
    assert len(r["processos"]) == 2 and r["totais"]["total"] == 6 and r["cortado"] is True
    csv = await _get("processos.csv", max_rows=2)
    assert csv.status_code == 422
    assert "6 processos" in csv.json()["detail"]
    inteiro = await _get("processos.csv")
    assert inteiro.status_code == 200
    assert "Período: todo o histórico" in inteiro.text
    assert "Em trânsito" in inteiro.text


@pytest.mark.asyncio
async def test_descricao_do_recorte_nao_vaza_nome_de_outra_prefeitura(cen, admin_engine):
    outra = await provisionar_tenant_de_teste(admin_engine, "relout")
    async with _sm(admin_engine)() as s:
        unidade_alheia = (await s.execute(text(
            "SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t LIMIT 1"
        ), {"t": outra.id})).scalar_one()
        nome_alheio = (await s.execute(text(
            "SELECT unidade_trabalho FROM utils.unidade_trabalho WHERE id=:u"
        ), {"u": unidade_alheia})).scalar_one()
    r = (await _get("processos.json", id_unidade=unidade_alheia)).json()
    assert r["processos"] == []
    assert not any(nome_alheio in linha for linha in r["descricao_filtros"])


# ---------------------------------------------------------------- tramitação


@pytest.mark.asyncio
async def test_atraso_e_sair_da_unidade_depois_do_fim_do_dia_do_prazo(cen, admin_engine):
    await _monta_prazo(cen, admin_engine)
    r = (await _get("tramitacao.json", desde="2026-10-10", ate="2026-10-10")).json()
    por_numero = {p["id"]: p for p in r["processos"]}
    ultimo_dia = por_numero[cen["procs"]["no_ultimo_dia"]]
    atrasado = por_numero[cen["procs"]["depois_do_prazo"]]
    etapa_b = lambda proc: next(e for e in proc["etapas"] if e["unidade"] == "Unidade B")  # noqa: E731
    assert etapa_b(ultimo_dia)["atrasou"] is False
    assert etapa_b(atrasado)["atrasou"] is True
    assert r["qtd_processos_com_atraso"] == 1
    # prazo exibido: último segundo do dia 15, em Brasília
    assert etapa_b(atrasado)["prazo_estipulado"].startswith("2026-10-15T23:59:59")


@pytest.mark.asyncio
async def test_tramitacao_pela_chegada_na_unidade(cen, admin_engine):
    await _monta_prazo(cen, admin_engine)
    r = await _get(
        "tramitacao.json", desde="2026-10-15", ate="2026-10-15", data_base="chegada",
        id_unidade=cen["unid"]["B"], modo_unidade="passou",
    )
    # chegou a B em 15/10 (local) só o `no_ultimo_dia`
    assert {p["id"] for p in r.json()["processos"]} == {cen["procs"]["no_ultimo_dia"]}


async def _monta_prazo(cen, admin_engine):
    """Dois processos enviados A→B com prazo 15/10 e repassados de B a C.

    - `no_ultimo_dia`: chega a B às 10h de 15/10 (local) e sai às 20h do mesmo
      dia — dentro do prazo. A regra antiga (chegada > meia-noite do prazo)
      dizia atrasado.
    - `depois_do_prazo`: chega a B em 14/10 e sai à 01h de 16/10 — atrasado.
      A regra antiga (só a chegada) dizia em dia.
    """
    t = cen["tenant"]
    unid, procs, prio = cen["unid"], cen["procs"], cen["prio"]
    async with _sm(admin_engine)() as s:
        async def q(sql, **p):
            return await s.execute(text(sql), {"t": t.id, **p})

        base = (await q(
            "SELECT id_assunto, id_manifestante, id_usuario FROM protocolos.processo WHERE id=:p",
            p=procs["noite_10"],
        )).one()
        acao_enc = (await q("SELECT id FROM protocolos.acao WHERE flag='ENCAMINHAMENTO'")).scalar_one()
        for rotulo, chegada_b, saida_b in (
            ("no_ultimo_dia", datetime(2026, 10, 15, 13, 0), datetime(2026, 10, 15, 23, 0)),
            ("depois_do_prazo", datetime(2026, 10, 14, 13, 0), datetime(2026, 10, 16, 4, 0)),
        ):
            procs[rotulo] = (await q(
                """
                INSERT INTO protocolos.processo
                    (tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria,
                     id_local_atual, numero_processo, nivel_sigilo, situacao, id_usuario,
                     virtual, externo, ativo, excluido, migrado, data_hora_abertura)
                VALUES (:t, :a, :m, :ua, :uc, :n, 'ostensivo', 'protocolado', :u,
                        true, false, true, false, false, :ab)
                RETURNING id
                """,
                a=base.id_assunto, m=base.id_manifestante, u=base.id_usuario, ua=unid["A"],
                uc=unid["C"], n=f"{rotulo}-{uuid.uuid4().hex[:4]}", ab=datetime(2026, 10, 10, 13, 0),
            )).scalar_one()
            for origem, destino, enviado, recebido, prazo in (
                ("A", "B", chegada_b.replace(hour=chegada_b.hour - 1), chegada_b, date(2026, 10, 15)),
                ("B", "C", saida_b, saida_b.replace(minute=30), None),
            ):
                mov = (await q(
                    "INSERT INTO protocolos.movimentacao (tenant_id, id_processo, "
                    "id_unidade_responsavel, id_acao, data_hora_movimentacao) "
                    "VALUES (:t, :p, :o, :ac, :em) RETURNING id",
                    p=procs[rotulo], o=unid[origem], ac=acao_enc, em=enviado,
                )).scalar_one()
                await q(
                    "INSERT INTO protocolos.encaminhamento (tenant_id, id_processo, "
                    "id_unidade_origem, id_unidade_destino, id_prioridade, id_usuario, "
                    "id_movimentacao, data_prazo, recebido, data_hora_recebimento) "
                    "VALUES (:t, :p, :o, :d, :pr, :u, :mv, :prazo, true, :rec)",
                    p=procs[rotulo], o=unid[origem], d=unid[destino], pr=prio, u=base.id_usuario,
                    mv=mov, prazo=prazo, rec=recebido,
                )
        await s.commit()
