"""Pagamentos Onda C — fatia C1.3: as quatro listagens restantes.

A C1.1 exportou débitos e parou. Estas são extrato da conta, painel de caixa,
ordens de pagamento e lançamentos de conciliação — mais PDF nos dois que viram
documento.

O que cada teste procura, e por que não é o óbvio:

- **Vazio é cabeçalho sozinho, não arquivo vazio.** Uma planilha sem cabeçalho
  não diz ao usuário que a consulta não achou nada; diz que o sistema falhou.
- **Moeda com vírgula.** Sem isso o Excel pt-BR lê a coluna como texto e
  ninguém soma nada — o export existe justamente para somar.
- **PDF é conferido pelo CONTEÚDO extraído**, não por "gerou bytes". Um PDF de
  uma página em branco também tem bytes.
- **Um teste HTTP com usuário comum por endpoint.** A suíte inteira roda como
  super-usuário, que em `auth/perms.py` retorna ANTES de olhar a transação —
  gate errado passa despercebido.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import Usuario
from app.schemas.pagamentos import (
    ContaCreate, FonteCreate, ImportarExtratoIn, MovimentacaoCreate,
)
from app.services import pagamentos_cadastros as cad_svc
from app.services import pagamentos_caixa as caixa_svc
from app.services import pagamentos_conciliacao as conc_svc
from app.services import pagamentos_export as export
from app.services.modulos import contratar
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name
SEP = ";"


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _linhas(conteudo: str) -> list[list[str]]:
    """Cabeçalho + dados, já sem BOM."""
    return list(csv.reader(io.StringIO(conteudo.lstrip("﻿")), delimiter=SEP))


async def _cenario(engine):
    """Tenant com conta, uma entrada e uma saída, e um extrato importado."""
    slug = f"expc13{uuid.uuid4().hex[:8]}"
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Export C13", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    tid = tenant.id

    async with _sm(engine)() as s:
        await contratar(s, tid, ["pagamentos"])
        await s.commit()

    async with _sm(engine)() as db:
        fonte = await cad_svc.criar_fonte(
            db, tenant_id=tid,
            payload=FonteCreate(codigo="C13-1500", descricao="Recursos Ordinários",
                                grupos_despesa_permitidos=["CUSTEIO"]))
        conta = await cad_svc.criar_conta(
            db, tenant_id=tid,
            payload=ContaCreate(nome="Conta C13", banco="BB", agencia="1", conta="9",
                                id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO",
                                saldo_inicial=Decimal("1000.00")))
        usuario_id = int((await db.execute(text(
            "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": tid})).scalar_one())

    async with _sm(engine)() as db:
        await caixa_svc.lancar_movimentacao(
            db, tenant_id=tid, usuario_id=usuario_id,
            payload=MovimentacaoCreate(id_conta=conta.id, tipo="ENTRADA",
                                       origem="RECEITA",
                                       valor=Decimal("1234.56"), data=date.today(),
                                       descricao="Repasse do Tesouro"))
        await db.commit()

    async with _sm(engine)() as db:
        extrato = (await conc_svc.importar_extrato(
            db, tenant_id=tid, usuario_id=usuario_id,
            payload=ImportarExtratoIn(
                id_conta=conta.id, formato="CSV", nome_arquivo="extrato.csv",
                conteudo="data;historico;documento;favorecido;valor;tipo\n"
                         f"{date.today().isoformat()};TED recebida;DOC1;Fulano;1234,56;CREDITO\n",
            ))).extrato
        await db.commit()

    return tid, conta.id, extrato.id, tenant.slug


async def _limpar(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.lancamento_extrato WHERE tenant_id=:t",
            "DELETE FROM pagamentos.extrato WHERE tenant_id=:t",
            "DELETE FROM pagamentos.movimentacao_conta WHERE tenant_id=:t",
            "DELETE FROM pagamentos.conta_bancaria WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fonte_recursos WHERE tenant_id=:t",
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


# ---------------------------------------------------------------- CSV


@pytest.mark.asyncio
async def test_extrato_da_conta_traz_a_movimentacao(admin_engine) -> None:
    tid, conta_id, _ext, _slug = await _cenario(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            conteudo = await export.csv_extrato_conta(db, tenant_id=tid, conta_id=conta_id)
        linhas = _linhas(conteudo)
        assert linhas[0] == export.COLUNAS_EXTRATO
        assert len(linhas) == 2, linhas
        linha = dict(zip(export.COLUNAS_EXTRATO, linhas[1]))
        assert linha["tipo"] == "ENTRADA"
        assert linha["valor"] == "1234,56", "vírgula decimal, senão o Excel lê como texto"
        assert linha["descricao"] == "Repasse do Tesouro"
    finally:
        await _limpar(admin_engine, tid)


@pytest.mark.asyncio
async def test_painel_de_caixa_traz_os_saldos(admin_engine) -> None:
    tid, _conta, _ext, _slug = await _cenario(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            conteudo = await export.csv_painel_caixa(db, tenant_id=tid)
        linhas = _linhas(conteudo)
        assert linhas[0] == export.COLUNAS_PAINEL
        linha = dict(zip(export.COLUNAS_PAINEL, linhas[1]))
        assert linha["conta"] == "Conta C13"
        # 1000 inicial + 1234,56 de entrada.
        assert linha["saldo_atual"] == "2234,56", linha
        assert linha["abaixo_minimo"] in ("sim", "não")
    finally:
        await _limpar(admin_engine, tid)


@pytest.mark.asyncio
async def test_lancamentos_da_conciliacao(admin_engine) -> None:
    tid, _conta, extrato_id, _slug = await _cenario(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            conteudo = await export.csv_lancamentos(db, tenant_id=tid, id_extrato=extrato_id)
        linhas = _linhas(conteudo)
        assert linhas[0] == export.COLUNAS_LANCAMENTOS
        linha = dict(zip(export.COLUNAS_LANCAMENTOS, linhas[1]))
        assert linha["favorecido"] == "Fulano"
        assert linha["valor"] == "1234,56"
        assert linha["conciliado"] == "não"
    finally:
        await _limpar(admin_engine, tid)


@pytest.mark.asyncio
async def test_sem_dado_vem_cabecalho_e_nao_arquivo_vazio(admin_engine) -> None:
    """Planilha sem cabeçalho não diz "não achei nada" — diz "quebrou"."""
    tid, conta_id, _ext, _slug = await _cenario(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            # Nenhuma ordem de pagamento foi criada neste cenário.
            conteudo = await export.csv_ordens(db, tenant_id=tid)
        linhas = _linhas(conteudo)
        assert linhas == [export.COLUNAS_ORDENS], linhas
        assert conteudo.startswith("﻿"), "o BOM some e o Excel estraga os acentos"
    finally:
        await _limpar(admin_engine, tid)


# ---------------------------------------------------------------- PDF


@pytest.mark.asyncio
async def test_pdf_do_painel_tem_o_conteudo_e_nao_so_bytes(admin_engine) -> None:
    """`len(pdf) > 0` passaria com uma página em branco.

    A afirmação é sobre o texto extraído: se a tabela não foi para dentro do
    documento, o usuário imprime uma folha vazia e só descobre no papel.
    """
    pypdf = pytest.importorskip("pypdf", reason="leitura de PDF exige pypdf")
    tid, _conta, _ext, _slug = await _cenario(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            pdf = await export.pdf_painel_caixa(db, tenant_id=tid)
        assert pdf[:4] == b"%PDF"
        # Espaços normalizados antes de comparar: a extração quebra a célula
        # entre linhas quando a coluna é estreita — "Conta C13" saiu como
        # "...2976 Conta" + quebra + "C13 BB...". Afirmar sobre isso seria
        # afirmar sobre LAYOUT e não sobre conteúdo: o teste ficaria vermelho
        # no dia em que a largura mudasse, sem nada ter quebrado para quem lê
        # o relatório.
        texto = " ".join(
            "".join(
                p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(pdf)).pages
            ).split()
        )
        assert "Painel de caixa" in texto
        assert "Conta C13" in texto, texto[:400]
    finally:
        await _limpar(admin_engine, tid)


@pytest.mark.asyncio
async def test_pdf_e_csv_contam_a_mesma_historia(admin_engine) -> None:
    """O PDF é montado A PARTIR do CSV, e este teste é o que trava isso.

    Duas montagens independentes divergiriam, e a divergência entre o PDF e a
    planilha do MESMO relatório só apareceria numa auditoria — depois que os
    dois documentos já saíram da prefeitura.
    """
    pypdf = pytest.importorskip("pypdf", reason="leitura de PDF exige pypdf")
    tid, _conta, _ext, _slug = await _cenario(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            csv_txt = await export.csv_painel_caixa(db, tenant_id=tid)
            pdf = await export.pdf_painel_caixa(db, tenant_id=tid)
        linha_csv = dict(zip(export.COLUNAS_PAINEL, _linhas(csv_txt)[1]))
        texto = "".join(
            p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(pdf)).pages
        )
        assert linha_csv["saldo_atual"] in texto, (linha_csv["saldo_atual"], texto[:400])
    finally:
        await _limpar(admin_engine, tid)


# ---------------------------------------------------------------- HTTP


async def _usuario_com(engine, tenant_id: int, codigos: list[str]) -> int:
    """Usuário NÃO super-usuário, com exatamente as transações pedidas."""
    async with _sm(engine)() as s:
        sistema_id = int((await s.execute(text(
            "SELECT id FROM utils.sistema WHERE app=:a AND excluido=false LIMIT 1"
        ), {"a": APP})).scalar_one())
        nivel_id = (await s.execute(text(
            "SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1"
        ))).scalar_one_or_none()
        if nivel_id is None:
            nivel_id = (await s.execute(text(
                "INSERT INTO utils.nivel (nivel, valor, excluido) "
                "VALUES ('Operacional', 1, false) RETURNING id"))).scalar_one()
        uid = int((await s.execute(text("""
            INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                       excluido, app, nivel_acesso_sigilo)
            VALUES (:t, 'Tesoureiro C13', :e, '', :cpf, true, false, :a, 'interno')
            RETURNING id"""), {"t": tenant_id, "e": f"c13-{uuid.uuid4().hex[:8]}@exp.test",
                               "cpf": uuid.uuid4().hex[:11], "a": APP})).scalar_one())
        gid = int((await s.execute(text("""
            INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
            VALUES (:t, :n, :s, :g, false) RETURNING id"""),
            {"t": tenant_id, "n": nivel_id, "s": sistema_id,
             "g": f"Tesouraria {uuid.uuid4().hex[:6]}"})).scalar_one())
        await s.execute(text("""
            INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
            VALUES (:t, :u, :g, true, false, :a)"""),
            {"t": tenant_id, "u": uid, "g": gid, "a": APP})
        for codigo in codigos:
            tr = (await s.execute(text(
                "SELECT id FROM utils.transacao WHERE codigo=:c AND excluido=false LIMIT 1"
            ), {"c": codigo})).scalar_one()
            await s.execute(text("""
                INSERT INTO utils.grupo_transacao
                    (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
                VALUES (:t, :g, :tr, false, false, false, false)"""),
                {"t": tenant_id, "g": gid, "tr": int(tr)})
        await s.commit()
    return uid


async def _get(engine, tenant_id, slug, usuario_id, caminho):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(
                select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, slug)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.get(caminho)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


@pytest.mark.asyncio
async def test_http_usuario_comum_com_a_transacao_baixa(admin_engine) -> None:
    """As quatro rotas novas, por HTTP, com usuário COMUM.

    Sem isto, um gate com o código errado passaria: o super-usuário devolve
    antes de olhar a transação, e a suíte inteira é super-usuário.
    """
    tid, conta_id, extrato_id, slug = await _cenario(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, tid, ["pagamento_cadastro", "pagamento_pagar"])
        for caminho, tipo in (
            ("/api/v2/pagamentos/caixa/painel.csv", "text/csv"),
            (f"/api/v2/pagamentos/contas/{conta_id}/extrato.csv", "text/csv"),
            (f"/api/v2/pagamentos/extratos/{extrato_id}/lancamentos.csv", "text/csv"),
            ("/api/v2/pagamentos/ordens-pagamento/exportar.csv", "text/csv"),
        ):
            r = await _get(admin_engine, tid, slug, uid, caminho)
            assert r.status_code == 200, (caminho, r.status_code, r.text[:200])
            assert tipo in r.headers["content-type"], caminho
            assert "attachment" in r.headers.get("content-disposition", ""), caminho
    finally:
        await _limpar(admin_engine, tid)


@pytest.mark.asyncio
async def test_http_usuario_sem_transacao_leva_403(admin_engine) -> None:
    """O par: sem as transações, nada baixa. Prova que o gate decide."""
    tid, conta_id, _ext, slug = await _cenario(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, tid, [])
        for caminho in (
            "/api/v2/pagamentos/caixa/painel.csv",
            f"/api/v2/pagamentos/contas/{conta_id}/extrato.csv",
            "/api/v2/pagamentos/ordens-pagamento/exportar.csv",
        ):
            r = await _get(admin_engine, tid, slug, uid, caminho)
            assert r.status_code == 403, (caminho, r.status_code)
    finally:
        await _limpar(admin_engine, tid)


@pytest.mark.asyncio
async def test_http_a_rota_literal_nao_e_engolida_pela_parametrica(admin_engine) -> None:
    """`exportar.csv` vs `/{ordem_id}` — o defeito que ocorreu 3× no transporte.

    Se a paramétrica vier primeiro na ordem de declaração, o FastAPI tenta
    converter "exportar.csv" em int e devolve **422** sem chegar ao handler.
    422 aqui não é "requisição inválida": é rota mal ordenada.
    """
    tid, _conta, _ext, slug = await _cenario(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, tid, ["pagamento_cadastro", "pagamento_pagar"])
        for caminho in ("/api/v2/pagamentos/ordens-pagamento/exportar.csv",
                        "/api/v2/pagamentos/ordens-pagamento/exportar.pdf"):
            r = await _get(admin_engine, tid, slug, uid, caminho)
            assert r.status_code != 422, (
                f"{caminho} caiu na rota paramétrica — declare a literal ANTES"
            )
    finally:
        await _limpar(admin_engine, tid)
