"""Pagamentos Onda C2 — fatia C2.1: export contábil neutro, lotes imutáveis.

Cobre `services/pagamentos_contabil.py` e as três rotas de
`routers/pagamentos_contabil.py`. Os helpers de cenário (fornecedor, natureza,
fonte, conta, o rito completo até AUTORIZADO) são importados de
`test_pagamentos_autorizacao` de propósito — montar esse cenário do zero é
~150 linhas de harness que já existem lá, e uma segunda cópia divergiria do
rito real no dia em que ele mudasse (mesma razão do `test_pagamentos_rn15_c13`).

O que cada teste procura, e por que não é o óbvio:

- **(a/b) Imutabilidade não é "não editou a linha"** — é "reconstruir do zero
  dá byte a byte o mesmo arquivo". O teste força isso comparando hash, não
  comparando objetos Python.
- **(c) Complementação** é o motivo de existir `id_origem` estável: sem ele,
  gerar um segundo lote reprocessaria (ou perderia) o que o primeiro já
  capturou.
- **(d) A unique é a rede, não decoração.** Sem provar a violação por
  inversão, ela poderia estar apontando para a coluna errada e nenhum teste
  notaria.
- **(g) Um teste HTTP com usuário comum.** A suíte inteira roda como
  super-usuário, que em `auth/perms.py` retorna ANTES de olhar a transação —
  gate errado passa despercebido (mesma lição da C1.3).
"""
from __future__ import annotations

import csv
import io
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import ExportContabilEvento, ExportContabilLote, Usuario
from app.schemas.pagamentos import GrupoAutorizacaoIn, ParcelaCreate
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_contabil as svc
from app.services import pagamentos_debitos as deb
from tests.conftest import arreio_tenant_http
from tests.test_pagamentos_autorizacao import (
    _autorizador_com_alcada,
    _base,
    _cleanup as _cleanup_autorizacao,
    _debito_aprovado,
    _debito_autorizado,
    _novo_usuario,
    _payload_debito,
    _provisionar,
    _sm,
)

APP = get_settings().app_name
SEP = ";"


def _linhas(conteudo: bytes) -> list[list[str]]:
    texto = conteudo.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(texto), delimiter=SEP))


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.export_contabil_evento WHERE tenant_id=:t",
            "DELETE FROM pagamentos.export_contabil_lote WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()
    await _cleanup_autorizacao(engine, tenant_id)


async def _tesoureiro(engine, tenant_id: int) -> int:
    return await _novo_usuario(engine, tenant_id, f"tes{uuid.uuid4().hex[:6]}")


async def _pagar(engine, tenant_id, *, autorizador, tesoureiro, parcela_id, forma="PIX"):
    async with _sm(engine)() as s:
        await aut.liberar_parcelas(s, tenant_id=tenant_id, usuario_id=autorizador,
                                   parcela_ids=[parcela_id])
    async with _sm(engine)() as s:
        return await aut.pagar_parcela(s, tenant_id=tenant_id, usuario_id=tesoureiro,
                                       parcela_id=parcela_id, forma_pagamento=forma)


async def _cenario_pago(engine, t):
    """Débito RASCUNHO→...→AUTORIZADO→pago integralmente. Retorna (debito,
    autorizador_id, tesoureiro_id)."""
    d, _sol, _apr, autorizador, fonte, conta = await _debito_autorizado(engine, t.id)
    tesoureiro = await _tesoureiro(engine, t.id)
    async with _sm(engine)() as s:
        parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
    await _pagar(engine, t.id, autorizador=autorizador, tesoureiro=tesoureiro,
                parcela_id=parcelas[0].id)
    return d, autorizador, tesoureiro


# ---------------------------------------------------------------- (a)

@pytest.mark.asyncio
async def test_a_debito_empenhado_liquidado_pago_gera_tres_eventos(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, autorizador, tesoureiro = await _cenario_pago(admin_engine, t)
        async with _sm(admin_engine)() as s:
            pendentes = await svc.coletar_eventos_pendentes(
                s, tenant_id=t.id, ate=svc.date.today())
        tipos = sorted(e.tipo_evento for e in pendentes)
        assert tipos == ["debito_empenhado", "liquidacao", "pagamento"], tipos

        async with _sm(admin_engine)() as s:
            lote = await svc.gerar_lote(s, tenant_id=t.id, ate=svc.date.today(), usuario_id=autorizador)
        assert lote.numero == 1
        assert lote.qtd_eventos == 3
        assert lote.hash_conteudo

        async with _sm(admin_engine)() as s:
            conteudo1 = await svc.reconstruir_csv(s, tenant_id=t.id, lote_id=lote.id)
        linhas = _linhas(conteudo1)
        assert linhas[0] == svc.COLUNAS
        assert len(linhas) == 4, linhas  # cabeçalho + 3

        # hash estável entre duas reconstruções.
        async with _sm(admin_engine)() as s:
            conteudo2 = await svc.reconstruir_csv(s, tenant_id=t.id, lote_id=lote.id)
        import hashlib
        assert hashlib.sha256(conteudo1).hexdigest() == hashlib.sha256(conteudo2).hexdigest()
    finally:
        await _cleanup(admin_engine, t.id)


# ---------------------------------------------------------------- (b)

@pytest.mark.asyncio
async def test_b_gerar_sem_evento_novo_da_409_e_download_e_estavel(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, autorizador, tesoureiro = await _cenario_pago(admin_engine, t)
        async with _sm(admin_engine)() as s:
            lote1 = await svc.gerar_lote(s, tenant_id=t.id, ate=svc.date.today(), usuario_id=autorizador)
        async with _sm(admin_engine)() as s:
            conteudo_a = await svc.reconstruir_csv(s, tenant_id=t.id, lote_id=lote1.id)

        with pytest.raises(svc.ExportContabilError) as exc:
            async with _sm(admin_engine)() as s:
                await svc.gerar_lote(s, tenant_id=t.id, ate=svc.date.today(), usuario_id=autorizador)
        assert exc.value.status_code == 409

        async with _sm(admin_engine)() as s:
            conteudo_b = await svc.reconstruir_csv(s, tenant_id=t.id, lote_id=lote1.id)
        assert conteudo_a == conteudo_b, "reemissão tem de devolver o MESMO conteúdo"
    finally:
        await _cleanup(admin_engine, t.id)


# ---------------------------------------------------------------- (c)

@pytest.mark.asyncio
async def test_c_novo_pagamento_apos_lote_1_gera_lote_2_so_com_o_evento_novo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, autorizador, fonte, conta = await _debito_autorizado(
            admin_engine, t.id, valor="1000.00",
            parcelas=[ParcelaCreate(numero=1, valor="600.00", vencimento="2026-08-01"),
                      ParcelaCreate(numero=2, valor="400.00", vencimento="2026-09-01")])
        tesoureiro = await _tesoureiro(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
        await _pagar(admin_engine, t.id, autorizador=autorizador, tesoureiro=tesoureiro,
                    parcela_id=parcelas[0].id)

        async with _sm(admin_engine)() as s:
            lote1 = await svc.gerar_lote(s, tenant_id=t.id, ate=svc.date.today(), usuario_id=autorizador)
        assert lote1.qtd_eventos == 3  # empenhado + liquidacao + 1º pagamento

        await _pagar(admin_engine, t.id, autorizador=autorizador, tesoureiro=tesoureiro,
                    parcela_id=parcelas[1].id)

        async with _sm(admin_engine)() as s:
            lote2 = await svc.gerar_lote(s, tenant_id=t.id, ate=svc.date.today(), usuario_id=autorizador)
        assert lote2.numero == 2
        assert lote2.qtd_eventos == 1, "só o 2º pagamento — o resto já foi capturado pelo lote 1"

        async with _sm(admin_engine)() as s:
            conteudo2 = await svc.reconstruir_csv(s, tenant_id=t.id, lote_id=lote2.id)
        linhas = _linhas(conteudo2)
        assert len(linhas) == 2, linhas
        assert linhas[1][1] == "pagamento", linhas
    finally:
        await _cleanup(admin_engine, t.id)


# ---------------------------------------------------------------- (d)

@pytest.mark.asyncio
async def test_d_mesmo_par_tipo_origem_em_dois_lotes_da_integrity_error(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, autorizador, tesoureiro = await _cenario_pago(admin_engine, t)
        async with _sm(admin_engine)() as s:
            lote1 = await svc.gerar_lote(s, tenant_id=t.id, ate=svc.date.today(), usuario_id=autorizador)
        async with _sm(admin_engine)() as s:
            row = (await s.execute(select(ExportContabilEvento).where(
                ExportContabilEvento.tenant_id == t.id,
                ExportContabilEvento.id_lote == lote1.id))).scalars().first()

        async with _sm(admin_engine)() as s:
            lote2 = ExportContabilLote(
                tenant_id=t.id, numero=999, formato_versao="neutro-csv-v1",
                qtd_eventos=1, id_usuario=autorizador, gerado_em=svc._utcnow())
            s.add(lote2); await s.flush()
            s.add(ExportContabilEvento(
                tenant_id=t.id, id_lote=lote2.id, tipo_evento=row.tipo_evento,
                id_origem=row.id_origem, ocorrido_em=row.ocorrido_em))
            with pytest.raises(IntegrityError):
                await s.commit()
    finally:
        await _cleanup(admin_engine, t.id)


# ---------------------------------------------------------------- (e)

@pytest.mark.asyncio
async def test_e_estorno_e_cancelamento_aparecem_com_os_tipos_certos(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        # débito pago e depois estornado.
        d, autorizador, tesoureiro = await _cenario_pago(admin_engine, t)
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
        async with _sm(admin_engine)() as s:
            await aut.estornar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                       parcela_id=parcelas[0].id, justificativa="Erro de digitação")

        # débito cancelado antes de autorizado (mesmo tenant, novo débito).
        forn, nat, fonte, conta, unidade_id = await _base(admin_engine, t.id)
        solicitante = await _novo_usuario(admin_engine, t.id, f"sol{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            d2 = await deb.criar_debito(s, tenant_id=t.id, usuario_id=solicitante,
                                        payload=_payload_debito(forn, nat, fonte, conta,
                                                                unidade_id=unidade_id))
        async with _sm(admin_engine)() as s:
            await deb.cancelar(s, tenant_id=t.id, debito_id=d2.id, usuario_id=solicitante,
                               lock_version=d2.lock_version, justificativa="Pedido duplicado")

        async with _sm(admin_engine)() as s:
            pendentes = await svc.coletar_eventos_pendentes(
                s, tenant_id=t.id, ate=svc.date.today())
        tipos = {e.tipo_evento for e in pendentes}
        assert "estorno_parcela" in tipos, tipos
        assert "cancelamento_debito" in tipos, tipos

        ev_cancel = next(e for e in pendentes if e.tipo_evento == "cancelamento_debito")
        assert ev_cancel.motivo == "Pedido duplicado"
        assert ev_cancel.id_debito == d2.id
    finally:
        await _cleanup(admin_engine, t.id)


# ---------------------------------------------------------------- (f)

@pytest.mark.asyncio
async def test_f_pagamento_com_excecao_rn15_traz_justificativa_no_csv(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, fonte, conta = await _debito_aprovado(
            admin_engine, t.id, valor="5000.00", saldo_inicial="100.00")
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        justificativa = "Folha atrasada; prefeito autorizou por ofício 12/2026."
        async with _sm(admin_engine)() as s:
            await aut.autorizar_lote(
                s, tenant_id=t.id, usuario_id=autorizador,
                grupos=[GrupoAutorizacaoIn(
                    id_fonte=fonte.id, id_conta_pagadora=conta.id, debito_ids=[d.id],
                    permitir_saldo_insuficiente=True, justificativa_excecao=justificativa)])
        tesoureiro = await _tesoureiro(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
        await _pagar(admin_engine, t.id, autorizador=autorizador, tesoureiro=tesoureiro,
                    parcela_id=parcelas[0].id)

        async with _sm(admin_engine)() as s:
            lote = await svc.gerar_lote(s, tenant_id=t.id, ate=svc.date.today(), usuario_id=autorizador)
            conteudo = await svc.reconstruir_csv(s, tenant_id=t.id, lote_id=lote.id)
        linhas = _linhas(conteudo)
        cab = linhas[0]
        linha_pagto = next(dict(zip(cab, l)) for l in linhas[1:] if l[cab.index("tipo_evento")] == "pagamento")
        assert linha_pagto["excecao_saldo"] == "sim", linha_pagto
        assert justificativa in linha_pagto["justificativa"], linha_pagto
    finally:
        await _cleanup(admin_engine, t.id)


# ---------------------------------------------------------------- (g)/(h) HTTP

async def _usuario_com(engine, tenant_id: int, codigos: list[str]) -> int:
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
            VALUES (:t, 'Contabil C2.1', :e, '', :cpf, true, false, :a, 'interno')
            RETURNING id"""), {"t": tenant_id, "e": f"c21-{uuid.uuid4().hex[:8]}@exp.test",
                               "cpf": uuid.uuid4().hex[:11], "a": APP})).scalar_one())
        gid = int((await s.execute(text("""
            INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
            VALUES (:t, :n, :s, :g, false) RETURNING id"""),
            {"t": tenant_id, "n": nivel_id, "s": sistema_id,
             "g": f"Contabilidade {uuid.uuid4().hex[:6]}"})).scalar_one())
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
                VALUES (:t, :g, :tr, true, false, false, false)"""),
                {"t": tenant_id, "g": gid, "tr": int(tr)})
        await s.commit()
    return uid


async def _http(engine, tenant_id, slug, usuario_id, metodo, caminho, **kw):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(
                select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, slug)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.request(metodo, caminho, **kw)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


@pytest.mark.asyncio
async def test_g_http_usuario_comum_gera_e_baixa(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, autorizador, tesoureiro = await _cenario_pago(admin_engine, t)
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])

        r = await _http(admin_engine, t.id, t.slug, uid, "POST",
                        "/api/v2/pagamentos/contabil/lotes", json={"ate": str(svc.date.today())})
        assert r.status_code == 201, r.text[:300]
        lote_id = r.json()["id"]

        r2 = await _http(admin_engine, t.id, t.slug, uid, "GET", "/api/v2/pagamentos/contabil/lotes")
        assert r2.status_code == 200
        assert any(l["id"] == lote_id for l in r2.json())

        r3 = await _http(admin_engine, t.id, t.slug, uid, "GET",
                         f"/api/v2/pagamentos/contabil/lotes/{lote_id}/arquivo")
        assert r3.status_code == 200
        assert "text/csv" in r3.headers["content-type"]
        assert "attachment" in r3.headers.get("content-disposition", "")
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_h_cross_tenant_404(admin_engine):
    t1 = await _provisionar(admin_engine)
    t2 = await _provisionar(admin_engine)
    try:
        d, autorizador, tesoureiro = await _cenario_pago(admin_engine, t1)
        async with _sm(admin_engine)() as s:
            lote = await svc.gerar_lote(s, tenant_id=t1.id, ate=svc.date.today(), usuario_id=autorizador)

        uid_t2 = await _usuario_com(admin_engine, t2.id, ["pagamento_cadastro"])
        r = await _http(admin_engine, t2.id, t2.slug, uid_t2, "GET",
                        f"/api/v2/pagamentos/contabil/lotes/{lote.id}/arquivo")
        assert r.status_code == 404, r.text[:200]
    finally:
        await _cleanup(admin_engine, t1.id)
        await _cleanup(admin_engine, t2.id)
