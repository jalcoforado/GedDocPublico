"""Relatórios de protocolo — filtros e documentação (SI-34, rodada 2).

- serviço é filtro do recorte COMUM: vale igual na página, nas listas e no PDF;
- sigilo e origem filtram a lista de processos pelo mesmo critério dos
  cartões "Sigilosos" e "Externos" — o cartão é o total da lista filtrada;
- quebras por assunto e serviço somam o total;
- "só com atraso" da tramitação olha o recorte inteiro, não só os listados;
- documentação: a situação dos documentos em SQL é a da tela do processo, e
  cada número do grupo é o total da lista da sua visão.

Reaproveita o cenário de `test_relatorios_protocolo_medidas` (6 processos
abertos em outubro de 2026, sem serviço).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest
from sqlalchemy import select, text

from tests.test_relatorios_protocolo_medidas import _get, _monta_prazo, _sm, cen  # noqa: F401

OUTUBRO = {"desde": "2026-10-01", "ate": "2026-10-31"}
MENSAGEM_PRIVADA = "favor reenviar o RG da Sra. Fulana, CPF 000"


async def _documentacao(cen, admin_engine) -> dict:
    """Três serviços e seis processos abertos em 12/10/2026:

    serviço `alvara` exige RG e comprovante (obrigatórios) e foto (opcional);
    `opcional` só tem item opcional; `sem_lista` não exige nada.

    - `pendente`  (alvará): nenhum anexo — e um pedido de complementação ABERTO;
    - `parcial`   (alvará): RG enviado — pedido de 13/10 respondido em 15/10;
    - `completo`  (alvará): RG e comprovante — pedido CANCELADO em setembro;
    - `inativos`  (alvará): RG inativo e comprovante excluído → pendente;
    - `opcional`  (opcional): completo, como na tela do processo;
    - `sem_lista` (sem_lista): sem documento exigido; interno e externo.
    """
    t = cen["tenant"]
    out: dict = {"servico": {}, "proc": {}}
    async with _sm(admin_engine)() as s:
        async def q(sql, **p):
            return await s.execute(text(sql), {"t": t.id, **p})

        base = (await q(
            "SELECT id_assunto, id_manifestante, id_usuario, id_unidade_proprietaria "
            "FROM protocolos.processo WHERE id=:p", p=cen["procs"]["noite_10"],
        )).one()
        acao = (await q("SELECT id FROM protocolos.acao WHERE flag='ABERTURA'")).scalar_one()
        for chave, nome, docs in (
            ("alvara", "Alvará", [
                {"key": "rg", "nome": "RG", "obrigatorio": True},
                {"key": "comprovante", "nome": "Comprovante", "obrigatorio": True},
                {"key": "foto", "nome": "Foto", "obrigatorio": False},
            ]),
            ("opcional", "Só opcionais", [{"key": "extra", "nome": "Extra", "obrigatorio": False}]),
            ("sem_lista", "Sem lista", None),
        ):
            out["servico"][chave] = (await q(
                "INSERT INTO protocolos.servico (tenant_id, nome, slug, documentos_exigidos) "
                "VALUES (:t, :n, :sl, CAST(:d AS jsonb)) RETURNING id",
                n=nome, sl=f"{chave}-{uuid.uuid4().hex[:6]}", d=json.dumps(docs) if docs else None,
            )).scalar_one()

        async def processo(rotulo, servico, nivel="ostensivo", externo=False):
            out["proc"][rotulo] = (await q(
                """
                INSERT INTO protocolos.processo
                    (tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria,
                     id_local_atual, numero_processo, nivel_sigilo, situacao, id_usuario,
                     virtual, externo, ativo, excluido, migrado, data_hora_abertura, id_servico)
                VALUES (:t, :a, :m, :u, :u, :n, :nivel, 'protocolado', :usr,
                        true, :ext, true, false, false, '2026-10-12 13:00', :sv)
                RETURNING id
                """,
                a=base.id_assunto, m=base.id_manifestante, u=base.id_unidade_proprietaria,
                usr=base.id_usuario, n=f"doc-{rotulo}-{uuid.uuid4().hex[:4]}", nivel=nivel,
                ext=externo, sv=out["servico"][servico],
            )).scalar_one()

        async def anexo(rotulo, chave, ativo=True, excluido=False):
            mov = (await q(
                "INSERT INTO protocolos.movimentacao (tenant_id, id_processo, id_unidade_responsavel, "
                "id_acao, data_hora_movimentacao) VALUES (:t, :p, :u, :ac, '2026-10-12 13:00') RETURNING id",
                p=out["proc"][rotulo], u=base.id_unidade_proprietaria, ac=acao,
            )).scalar_one()
            aid = (await q(
                "INSERT INTO protocolos.anexo (tenant_id, documento_exigido_key, ativo, excluido) "
                "VALUES (:t, :k, :at, :ex) RETURNING id", k=chave, at=ativo, ex=excluido,
            )).scalar_one()
            await q(
                "INSERT INTO protocolos.anexo_processo (tenant_id, id_processo, id_anexo, id_movimentacao) "
                "VALUES (:t, :p, :a, :mv)", p=out["proc"][rotulo], a=aid, mv=mov,
            )

        async def pedido(rotulo, status, criado, respondido=None, cancelado=None):
            await q(
                "INSERT INTO protocolos.complementacao_documental (tenant_id, id_processo, "
                "id_usuario_solicitante, status, mensagem, documentos_solicitados, criado_em, "
                "respondido_em, cancelado_em) VALUES (:t, :p, :u, :st, :msg, '[]'::jsonb, :c, :r, :x)",
                p=out["proc"][rotulo], u=base.id_usuario, st=status, msg=MENSAGEM_PRIVADA,
                c=criado, r=respondido, x=cancelado,
            )

        for rotulo in ("pendente", "parcial", "completo", "inativos"):
            await processo(rotulo, "alvara")
        await processo("opcional", "opcional")
        await processo("sem_lista", "sem_lista", nivel="interno", externo=True)
        await anexo("parcial", "rg")
        await anexo("completo", "rg")
        await anexo("completo", "comprovante")
        await anexo("inativos", "rg", ativo=False)
        await anexo("inativos", "comprovante", excluido=True)
        await pedido("pendente", "aberta", datetime(2026, 10, 13, 12, 0))
        await pedido("parcial", "respondida", datetime(2026, 10, 13, 12, 0),
                     respondido=datetime(2026, 10, 15, 12, 0))
        await pedido("completo", "cancelada", datetime(2026, 9, 20, 12, 0),
                     cancelado=datetime(2026, 9, 21, 12, 0))
        await s.commit()
    return out


def _ids_lista(r) -> set[int]:
    return {p["id"] for p in r.json()["processos"]}


# ---------------------------------------------------------------- documentação


@pytest.mark.asyncio
async def test_status_documental_em_sql_igual_ao_checklist(cen, admin_engine):
    """A lista conta em SQL; a tela do processo calcula em Python. Os dois têm
    de dizer o mesmo de cada processo — senão a lista "pendentes" mostra
    processo que, aberto, aparece completo."""
    from app.models import Processo
    from app.services.checklist_documentos import calcular_checklist
    from app.services.relatorios_documentacao import _contagens_do_checklist, _status

    d = await _documentacao(cen, admin_engine)
    t = cen["tenant"]
    ids = list(d["proc"].values()) + [cen["procs"]["dia_11"]]  # + um sem serviço
    async with _sm(admin_engine)() as s:
        sql = dict((await s.execute(
            select(Processo.id, _status(*_contagens_do_checklist(t.id))).where(Processo.id.in_(ids))
        )).all())
        tela = {
            pid: (await calcular_checklist(s, processo_id=pid, tenant_id=t.id)).status_documental
            for pid in ids
        }
    assert sql == tela
    # o cenário cobre os quatro status — senão o teste passaria por vacuidade
    assert set(sql.values()) == {"sem_documentos_exigidos", "pendente", "parcial", "completo"}


@pytest.mark.asyncio
async def test_cada_numero_da_documentacao_e_o_total_da_sua_lista(cen, admin_engine):
    d = await _documentacao(cen, admin_engine)
    p = d["proc"]
    g = (await _get("gerencial.json", **OUTUBRO)).json()["documentacao"]

    async def lista(visao, **params):
        r = await _get("documentacao.json", visao=visao, **params)
        assert r.status_code == 200, r.text
        return r

    esperado = {
        "documentos": {p["pendente"], p["parcial"], p["completo"], p["inativos"], p["opcional"]},
        "doc_pendente": {p["pendente"], p["inativos"]},
        "doc_parcial": {p["parcial"]},
        "doc_completo": {p["completo"], p["opcional"]},
        "compl_pedida": {p["pendente"], p["parcial"]},  # o cancelado foi pedido em setembro
        "compl_respondida": {p["parcial"]},
    }
    for visao, ids in esperado.items():
        r = await lista(visao, **OUTUBRO)
        assert _ids_lista(r) == ids, visao
        assert r.json()["totais"]["total"] == len(ids)
    # aguardando o cidadão é situação de hoje: o período não entra
    assert _ids_lista(await lista("compl_aberta")) == {p["pendente"]}

    assert (g["pendentes"], g["parciais"], g["completos"]) == (2, 1, 2)
    assert (g["complementacao_pedida"], g["aguardando_cidadao"], g["complementacao_respondida"]) == (2, 1, 1)
    assert g["dias_medio_resposta"] == 2.0
    # 6 do cenário (sem serviço) + o `sem_lista`
    assert g["sem_documentos_exigidos"] == 7

    linha = {x["id"]: x for x in (await lista("documentos", **OUTUBRO)).json()["processos"]}
    assert (linha[p["parcial"]]["obrigatorios_enviados"], linha[p["parcial"]]["obrigatorios_total"]) == (1, 2)
    assert linha[p["parcial"]]["complementacao_status"] == "respondida"
    assert linha[p["completo"]]["complementacao_status"] == "cancelada"
    assert linha[p["parcial"]]["servico"] == "Alvará"


@pytest.mark.asyncio
async def test_documentacao_nao_expoe_a_mensagem_do_pedido(cen, admin_engine):
    """A mensagem do servidor ao cidadão é texto livre (pode ter dado pessoal);
    o relatório não precisa dela, nem na tela nem no CSV."""
    await _documentacao(cen, admin_engine)
    for path in ("documentacao.json", "documentacao.csv"):
        r = await _get(path, visao="compl_pedida", **OUTUBRO)
        assert r.status_code == 200
        assert MENSAGEM_PRIVADA not in r.text
        assert "Fulana" not in r.text


# ------------------------------------------------------------ serviço (comum)


@pytest.mark.asyncio
async def test_servico_filtra_igual_em_todos_os_relatorios(cen, admin_engine):
    d = await _documentacao(cen, admin_engine)
    alvara = d["servico"]["alvara"]
    do_alvara = {d["proc"][k] for k in ("pendente", "parcial", "completo", "inativos")}

    proc = await _get("processos.json", id_servico=alvara, **OUTUBRO)
    assert _ids_lista(proc) == do_alvara
    assert "Serviço: Alvará" in proc.json()["descricao_filtros"]

    g = (await _get("gerencial.json", id_servico=alvara, **OUTUBRO)).json()
    assert g["entrada"]["abertos"] == 4
    assert g["documentacao"]["sem_documentos_exigidos"] == 0
    assert "Serviço: Alvará" in g["descricao_filtros"]

    tram = await _get("tramitacao.json", id_servico=alvara, **OUTUBRO)
    assert _ids_lista(tram) == do_alvara
    ass = await _get("assinaturas.json", id_servico=alvara, **OUTUBRO)
    assert ass.json()["totais"]["total"] == 0  # nenhum pedido de assinatura nesses

    pdf = await _get("gerencial.pdf", id_servico=alvara, **OUTUBRO)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


# --------------------------------------------- lista de processos: sigilo/origem


@pytest.mark.asyncio
async def test_cartoes_sigilosos_e_externos_sao_o_total_da_lista_filtrada(cen, admin_engine):
    d = await _documentacao(cen, admin_engine)
    todos = (await _get("processos.json", **OUTUBRO)).json()
    assert todos["totais"]["sigilosos"] == 1 and todos["totais"]["externos"] == 1

    sigilosos = await _get("processos.json", sigilo="sigiloso", **OUTUBRO)
    assert _ids_lista(sigilosos) == {d["proc"]["sem_lista"]}
    assert sigilosos.json()["totais"]["total"] == todos["totais"]["sigilosos"]
    ostensivos = (await _get("processos.json", sigilo="ostensivo", **OUTUBRO)).json()
    assert ostensivos["totais"]["total"] == todos["totais"]["total"] - 1

    externos = await _get("processos.json", origem="externa", **OUTUBRO)
    assert _ids_lista(externos) == {d["proc"]["sem_lista"]}
    assert externos.json()["totais"]["total"] == todos["totais"]["externos"]
    assert "Origem: só externos" in externos.json()["descricao_filtros"]
    internos = (await _get("processos.json", origem="interna", **OUTUBRO)).json()
    assert internos["totais"]["total"] == todos["totais"]["total"] - 1


@pytest.mark.asyncio
async def test_quebras_por_assunto_e_servico_somam_o_total(cen, admin_engine):
    await _documentacao(cen, admin_engine)
    r = (await _get("processos.json", **OUTUBRO)).json()
    total = r["totais"]["total"]
    for chave in ("por_tipo_processo", "por_unidade_proprietaria", "por_assunto", "por_servico"):
        assert sum(x["count"] for x in r[chave]) == total, chave
    por_servico = {x["label"]: x["count"] for x in r["por_servico"]}
    # os 6 do cenário não têm serviço: aparecem como "—", não somem
    assert por_servico == {"Alvará": 4, "Só opcionais": 1, "Sem lista": 1, "—": 6}


# ----------------------------------------------------- tramitação: só com atraso


@pytest.mark.asyncio
async def test_so_com_atraso_olha_o_recorte_inteiro_e_nao_so_os_listados(cen, admin_engine):
    """O atraso sai das etapas, calculadas em Python. Filtrar depois do teto
    da lista acharia só atrasos entre os mais recentes."""
    await _monta_prazo(cen, admin_engine)
    procs = cen["procs"]
    # o atrasado fica o mais antigo do dia 10/10 (local), que tem três: com
    # teto 2, sem o filtro, ele nem é listado
    async with _sm(admin_engine)() as s:
        await s.execute(text(
            "UPDATE protocolos.processo SET data_hora_abertura='2026-10-10 12:00' WHERE id=:p"),
            {"p": procs["depois_do_prazo"]},
        )
        await s.commit()
    dia = {"desde": "2026-10-10", "ate": "2026-10-10"}

    sem_filtro = (await _get("tramitacao.json", max_processos=2, **dia)).json()
    assert sem_filtro["qtd_processos"] == 3
    assert procs["depois_do_prazo"] not in _ids_lista_json(sem_filtro)
    assert sem_filtro["qtd_processos_com_atraso"] == 0  # entre os listados

    so_atraso = (await _get("tramitacao.json", max_processos=1, com_atraso="true", **dia)).json()
    assert _ids_lista_json(so_atraso) == {procs["depois_do_prazo"]}
    assert so_atraso["qtd_processos"] == 1 and so_atraso["cortado"] is False
    assert so_atraso["qtd_processos_com_atraso"] == 1
    assert "Só processos com atraso na tramitação (prazo do envio)" in so_atraso["descricao_filtros"]


def _ids_lista_json(r: dict) -> set[int]:
    return {p["id"] for p in r["processos"]}
