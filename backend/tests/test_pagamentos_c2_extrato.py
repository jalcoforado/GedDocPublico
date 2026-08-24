"""C2.2 — parser OFX (1.x SGML e 2.x XML) + dedupe de lançamento por
`(id_conta, id_externo)` na importação de extrato.

Cobre: parse_ofx isolado (SGML, XML, malformado), importação criando
lançamentos com id_externo, reimportação com sobreposição de FITID (dedupe),
mesmo FITID em contas diferentes (não deve colidir) e regressão do CSV.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import ContaCreate, FonteCreate, ImportarExtratoIn
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_conciliacao as conc
from app.services.pagamentos_extrato_parsers import Cnab240ParseError, OfxParseError, parse_cnab240, parse_ofx
from app.services.provisioning_tenant import provisionar_tenant

_FIXTURES = Path(__file__).parent / "fixtures"


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _provisionar(engine):
    slug = f"pagofx{uuid.uuid4().hex[:8]}"
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref OFX", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico")
    return tenant


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.conciliacao WHERE tenant_id=:t",
            "DELETE FROM pagamentos.lancamento_extrato WHERE tenant_id=:t",
            "DELETE FROM pagamentos.extrato WHERE tenant_id=:t",
            "DELETE FROM pagamentos.conta_bancaria WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fonte_recursos WHERE tenant_id=:t",
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


async def _novo_usuario(engine, tenant_id, sufixo):
    async with _sm(engine)() as s:
        r = await s.execute(text(
            """INSERT INTO utils.usuario (tenant_id, nome, email, cpf, senha, ativo, excluido, data_criacao)
               VALUES (:t, :n, :e, :c, 'x', true, false, NOW()) RETURNING id"""),
            {"t": tenant_id, "n": f"U {sufixo}", "e": f"{sufixo}@t.local", "c": uuid.uuid4().hex[:11]})
        uid = r.scalar_one(); await s.commit()
    return uid


async def _conta(engine, tenant_id, *, sufixo="a"):
    async with _sm(engine)() as s:
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome=f"Conta {sufixo}", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO", saldo_inicial="10000.00"))
    return conta


def _ofx_sgml(transacoes: list[dict]) -> str:
    linhas = [
        "OFXHEADER:100", "DATA:OFXSGML", "VERSION:102", "SECURITY:NONE",
        "ENCODING:USASCII", "CHARSET:1252", "COMPRESSION:NONE",
        "OLDFILEUID:NONE", "NEWFILEUID:NONE", "",
        "<OFX>", "<BANKMSGSRSV1>", "<STMTTRNRS>", "<STMTRS>", "<BANKTRANLIST>",
    ]
    for t in transacoes:
        linhas.append("<STMTTRN>")
        linhas.append(f"<TRNTYPE>{t.get('trntype', 'DEBIT')}")
        linhas.append(f"<DTPOSTED>{t['dtposted']}")
        linhas.append(f"<TRNAMT>{t['trnamt']}")
        if t.get("fitid") is not None:
            linhas.append(f"<FITID>{t['fitid']}")
        if t.get("checknum"):
            linhas.append(f"<CHECKNUM>{t['checknum']}")
        if t.get("name"):
            linhas.append(f"<NAME>{t['name']}")
        if t.get("memo"):
            linhas.append(f"<MEMO>{t['memo']}")
        linhas.append("</STMTTRN>")
    linhas += ["</BANKTRANLIST>", "</STMTRS>", "</STMTTRNRS>", "</BANKMSGSRSV1>", "</OFX>"]
    return "\n".join(linhas)


# ---------- (a)/(b)/(c) parse_ofx isolado ----------

def test_parse_ofx_sgml_1x():
    conteudo = (_FIXTURES / "extrato_exemplo.ofx").read_text(encoding="utf-8")
    lancs = parse_ofx(conteudo)
    assert len(lancs) == 3
    c = lancs[0]
    assert c.data == date(2026, 8, 1)
    assert c.tipo == "CREDITO"
    assert c.valor == Decimal("1500.00")
    assert c.id_externo == "F001"
    assert c.documento == "1001"
    assert c.favorecido == "Prefeitura"

    d = lancs[1]
    assert d.tipo == "DEBITO"
    assert d.valor == Decimal("150.75")  # sempre positivo
    assert d.id_externo == "F002"

    e = lancs[2]
    assert e.tipo == "DEBITO"
    assert e.valor == Decimal("89.90")
    assert e.id_externo == "F003"
    assert e.documento == "REF-77"  # REFNUM quando não há CHECKNUM


def test_parse_ofx_xml_2x():
    conteudo = (_FIXTURES / "extrato_exemplo_xml.ofx").read_text(encoding="utf-8")
    lancs = parse_ofx(conteudo)
    assert len(lancs) == 3
    assert [l.id_externo for l in lancs] == ["F001", "F002", "F003"]
    assert lancs[0].tipo == "CREDITO" and lancs[0].valor == Decimal("1500.00")
    assert lancs[1].tipo == "DEBITO" and lancs[1].valor == Decimal("150.75")


def test_parse_ofx_malformado_levanta_erro_claro():
    with pytest.raises(OfxParseError):
        parse_ofx("isto nao e um ofx nem xml valido")


async def test_parse_ofx_malformado_importar_extrato_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        conta = await _conta(admin_engine, t.id)
        uid = await _novo_usuario(admin_engine, t.id, f"c{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await conc.importar_extrato(
                    s, tenant_id=t.id, usuario_id=uid,
                    payload=ImportarExtratoIn(
                        id_conta=conta.id, nome_arquivo="ruim.ofx", formato="OFX",
                        conteudo="isto nao e um ofx"))
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


# ---------- (d) importar OFX cria extrato + lançamentos com id_externo ----------

async def test_importar_ofx_cria_lancamentos_com_id_externo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        conta = await _conta(admin_engine, t.id)
        uid = await _novo_usuario(admin_engine, t.id, f"c{uuid.uuid4().hex[:6]}")
        conteudo = (_FIXTURES / "extrato_exemplo.ofx").read_text(encoding="utf-8")
        async with _sm(admin_engine)() as s:
            ex = await conc.importar_extrato(
                s, tenant_id=t.id, usuario_id=uid,
                payload=ImportarExtratoIn(
                    id_conta=conta.id, nome_arquivo="ext.ofx", formato="OFX", conteudo=conteudo))
        assert ex.qtd_lancamentos == 3
        async with _sm(admin_engine)() as s:
            lancs = await conc.listar_lancamentos(s, tenant_id=t.id, id_extrato=ex.id)
        assert {l.id_externo for l in lancs} == {"F001", "F002", "F003"}
        assert all(l.id_conta == conta.id for l in lancs)
    finally:
        await _cleanup(admin_engine, t.id)


# ---------- (e) reimportação com sobreposição de FITID ----------

async def test_importar_ofx_segundo_arquivo_com_fitid_repetido_dedupe(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        conta = await _conta(admin_engine, t.id)
        uid = await _novo_usuario(admin_engine, t.id, f"c{uuid.uuid4().hex[:6]}")
        conteudo1 = _ofx_sgml([
            dict(dtposted="20260801120000", trnamt="1500.00", fitid="F001", trntype="CREDIT"),
            dict(dtposted="20260805090000", trnamt="-150.75", fitid="F002"),
        ])
        conteudo2 = _ofx_sgml([
            dict(dtposted="20260801120000", trnamt="1500.00", fitid="F001", trntype="CREDIT"),
            dict(dtposted="20260805090000", trnamt="-150.75", fitid="F002"),
            dict(dtposted="20260809100000", trnamt="-42.00", fitid="F004"),
        ])
        async with _sm(admin_engine)() as s:
            ex1 = await conc.importar_extrato(
                s, tenant_id=t.id, usuario_id=uid,
                payload=ImportarExtratoIn(
                    id_conta=conta.id, nome_arquivo="ext1.ofx", formato="OFX", conteudo=conteudo1))
        assert ex1.qtd_lancamentos == 2
        async with _sm(admin_engine)() as s:
            ex2 = await conc.importar_extrato(
                s, tenant_id=t.id, usuario_id=uid,
                payload=ImportarExtratoIn(
                    id_conta=conta.id, nome_arquivo="ext2.ofx", formato="OFX", conteudo=conteudo2))
        # só o F004 é lançamento novo
        assert ex2.qtd_lancamentos == 1
        async with _sm(admin_engine)() as s:
            lancs = await conc.listar_lancamentos(s, tenant_id=t.id, id_extrato=ex2.id)
        assert [l.id_externo for l in lancs] == ["F004"]
        # o total de lançamentos da conta continua 3 (2 do primeiro + 1 novo)
        async with _sm(admin_engine)() as s:
            total = (await s.execute(text(
                "SELECT count(*) FROM pagamentos.lancamento_extrato WHERE tenant_id=:t AND id_conta=:c"),
                {"t": t.id, "c": conta.id})).scalar_one()
        assert total == 3
    finally:
        await _cleanup(admin_engine, t.id)


# ---------- (f) mesmo FITID em contas diferentes não colide ----------

async def test_mesmo_fitid_em_contas_diferentes_nao_colide(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        conta1 = await _conta(admin_engine, t.id, sufixo="1")
        conta2 = await _conta(admin_engine, t.id, sufixo="2")
        uid = await _novo_usuario(admin_engine, t.id, f"c{uuid.uuid4().hex[:6]}")
        conteudo = _ofx_sgml([
            dict(dtposted="20260801120000", trnamt="500.00", fitid="DUP-1", trntype="CREDIT"),
        ])
        async with _sm(admin_engine)() as s:
            ex1 = await conc.importar_extrato(
                s, tenant_id=t.id, usuario_id=uid,
                payload=ImportarExtratoIn(
                    id_conta=conta1.id, nome_arquivo="c1.ofx", formato="OFX", conteudo=conteudo))
        assert ex1.qtd_lancamentos == 1
        async with _sm(admin_engine)() as s:
            ex2 = await conc.importar_extrato(
                s, tenant_id=t.id, usuario_id=uid,
                payload=ImportarExtratoIn(
                    id_conta=conta2.id, nome_arquivo="c2.ofx", formato="OFX", conteudo=conteudo))
        assert ex2.qtd_lancamentos == 1  # a conta é diferente, então F001 entra normalmente
    finally:
        await _cleanup(admin_engine, t.id)


# ---------- (g) CSV continua funcionando (regressão) ----------

def _csv(valor="1000.00", data="2026-08-01", tipo="DEBITO"):
    return (f"data;historico;documento;favorecido;valor;tipo\n"
            f"{data};Pagamento fornecedor;DOC1;Forn;{valor};{tipo}\n")


async def test_importar_csv_regressao_id_externo_none(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        conta = await _conta(admin_engine, t.id)
        uid = await _novo_usuario(admin_engine, t.id, f"c{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            ex = await conc.importar_extrato(
                s, tenant_id=t.id, usuario_id=uid,
                payload=ImportarExtratoIn(id_conta=conta.id, nome_arquivo="ext.csv", conteudo=_csv()))
        assert ex.qtd_lancamentos == 1
        async with _sm(admin_engine)() as s:
            lancs = await conc.listar_lancamentos(s, tenant_id=t.id, id_extrato=ex.id)
        assert lancs[0].id_externo is None
        assert lancs[0].id_conta == conta.id
    finally:
        await _cleanup(admin_engine, t.id)


# ---------- CNAB240 (C2.2 Task 2) ----------
#
# Fixture `fixtures/extrato_exemplo.cnab240.txt` — layout FEBRABAN de extrato
# construído à mão (spec executável até chegar arquivo real do banco do
# piloto). 7 linhas de 240 posições (1-based), terminadas em \r\n:
#
#   1  header de arquivo   (tipo de registro '0', pulada)
#   2  header de lote      (tipo de registro '1', pulada)
#   3  detalhe segmento E  CREDITO 1500.00, data 01/08/2026, doc "1001"
#   4  detalhe segmento E  DEBITO   150.75, data 05/08/2026, doc zerado -> None
#   5  detalhe segmento E  DEBITO    89.90, data 09/08/2026, doc "77"
#   6  trailer de lote     (tipo de registro '5', pulada)
#   7  trailer de arquivo  (tipo de registro '9', pulada)
#
# Posições do registro detalhe (tipo 3, segmento E), 1-based:
#   1-3   código do banco            "001"
#   4-7   lote de serviço            "0001"
#   8     tipo de registro           "3"
#   9-13  nº sequencial no lote      (não usado)
#   14    código de segmento         "E"
#   15-20 filler                     (não usado)
#   21-28 data do lançamento         DDMMAAAA
#   29-43 valor, 15 dígitos          inteiro em centavos, sem sinal
#   44    sinal do valor             'D' débito | 'C' crédito
#   45-49 nº do documento            5 dígitos zero-padded; zerado -> None
#   50-89 histórico                  40 chars
#   90-240 filler                    (não usado)

def test_parse_cnab240_fixture_tres_lancamentos():
    conteudo = (_FIXTURES / "extrato_exemplo.cnab240.txt").read_text(encoding="utf-8")
    lancs = parse_cnab240(conteudo)
    assert len(lancs) == 3

    a = lancs[0]
    assert a.data == date(2026, 8, 1)
    assert a.tipo == "CREDITO"
    assert a.valor == Decimal("1500.00")
    assert a.documento == "1001"
    assert a.id_externo == "1001"
    assert a.historico.strip() == "Repasse FPM"

    b = lancs[1]
    assert b.data == date(2026, 8, 5)
    assert b.tipo == "DEBITO"
    assert b.valor == Decimal("150.75")
    assert b.documento is None
    assert b.id_externo is None

    c = lancs[2]
    assert c.data == date(2026, 8, 9)
    assert c.tipo == "DEBITO"
    assert c.valor == Decimal("89.90")
    assert c.documento == "77"
    assert c.id_externo == "77"


def test_parse_cnab240_linha_tamanho_errado_levanta_erro_com_numero_da_linha():
    linha_boa = "0" * 240
    linha_ruim = "0" * 239  # 239 chars: violação
    conteudo = "\r\n".join([linha_boa, linha_ruim, linha_boa])
    with pytest.raises(Cnab240ParseError) as exc:
        parse_cnab240(conteudo)
    assert "2" in str(exc.value)  # linha 2 (1-based) é a culpada


async def test_parse_cnab240_malformado_importar_extrato_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        conta = await _conta(admin_engine, t.id)
        uid = await _novo_usuario(admin_engine, t.id, f"c{uuid.uuid4().hex[:6]}")
        conteudo = "0" * 239
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await conc.importar_extrato(
                    s, tenant_id=t.id, usuario_id=uid,
                    payload=ImportarExtratoIn(
                        id_conta=conta.id, nome_arquivo="ruim.cnab240.txt", formato="CNAB240",
                        conteudo=conteudo))
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


async def test_importar_cnab240_cria_extrato_e_lancamentos(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        conta = await _conta(admin_engine, t.id)
        uid = await _novo_usuario(admin_engine, t.id, f"c{uuid.uuid4().hex[:6]}")
        conteudo = (_FIXTURES / "extrato_exemplo.cnab240.txt").read_text(encoding="utf-8")
        async with _sm(admin_engine)() as s:
            ex = await conc.importar_extrato(
                s, tenant_id=t.id, usuario_id=uid,
                payload=ImportarExtratoIn(
                    id_conta=conta.id, nome_arquivo="ext.cnab240.txt", formato="CNAB240",
                    conteudo=conteudo))
        assert ex.qtd_lancamentos == 3
        async with _sm(admin_engine)() as s:
            lancs = await conc.listar_lancamentos(s, tenant_id=t.id, id_extrato=ex.id)
        assert {l.id_externo for l in lancs} == {"1001", "77", None}
        assert all(l.id_conta == conta.id for l in lancs)
    finally:
        await _cleanup(admin_engine, t.id)


async def test_importar_cnab240_reimportacao_mesmo_arquivo_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        conta = await _conta(admin_engine, t.id)
        uid = await _novo_usuario(admin_engine, t.id, f"c{uuid.uuid4().hex[:6]}")
        conteudo = (_FIXTURES / "extrato_exemplo.cnab240.txt").read_text(encoding="utf-8")
        async with _sm(admin_engine)() as s:
            await conc.importar_extrato(
                s, tenant_id=t.id, usuario_id=uid,
                payload=ImportarExtratoIn(
                    id_conta=conta.id, nome_arquivo="ext.cnab240.txt", formato="CNAB240",
                    conteudo=conteudo))
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await conc.importar_extrato(
                    s, tenant_id=t.id, usuario_id=uid,
                    payload=ImportarExtratoIn(
                        id_conta=conta.id, nome_arquivo="ext2.cnab240.txt", formato="CNAB240",
                        conteudo=conteudo))
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)
