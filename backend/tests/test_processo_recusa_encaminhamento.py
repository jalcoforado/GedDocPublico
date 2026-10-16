"""Recusa de encaminhamento e a caixa "Recusados" (migration 0135).

Um encaminhamento pendente tinha duas saídas: o destino recebe, ou a origem
cancela. Quem recebia processo que não era seu não tinha como devolver. A
recusa é a terceira saída, e a caixa "Recusados" é onde a origem a enxerga.

O que este arquivo existe para pegar:

- **Recusa que deixa o processo no limbo.** Recusado tem de sair da Entrada do
  destino e da Saída da origem e voltar para a mesa da origem — sem isso ele
  some das três caixas.
- **Caixa que não esvazia.** Reencaminhar tira o processo de "Recusados"; se a
  caixa olhasse "algum encaminhamento recusado" em vez de "o último", ela só
  cresceria.
- **Contador que não bate com a lista**, como nas demais caixas.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.auth.deps import get_current_user
from app.main import app
from app.schemas.processo import (
    CaixaProcesso, EncaminharRequest, RecusarEncaminhamentoRequest,
)
from app.services.acoes_processo import (
    AcaoError, encaminhar, recusar_encaminhamento,
)
from app.services.processos import contar_caixas, get_processo_detail, list_processos
from tests.conftest import arreio_tenant_http
from tests.test_processo_caixas import _como, _ids, _sm, cen  # noqa: F401 — fixture

MOTIVO = "Assunto não é da competência desta unidade."


async def _recusa(engine, cen, rotulo: str, *, por: str = "operador"):
    async with _sm(engine)() as s:
        return await recusar_encaminhamento(
            s, cen["procs"][rotulo], RecusarEncaminhamentoRequest(motivo=MOTIVO),
            tenant_id=cen["tenant"].id, usuario_id=cen[por],
        )


async def _caixas_de(engine, cen, unidade: str, usuario: str):
    async with _sm(engine)() as s:
        return await contar_caixas(
            s, tenant_id=cen["tenant"].id,
            id_usuario_contexto=cen[usuario], id_unidade_contexto=cen[unidade],
        )


@pytest.mark.asyncio
async def test_recusado_sai_do_transito_e_volta_para_a_mesa_da_origem(admin_engine, cen):
    """`saindo` foi de A para B. B recusa: sai da Saída de A e da Entrada de B,
    volta à Análise de A e aparece em Recusados de A — e só de A."""
    antes_a = await _caixas_de(admin_engine, cen, "a", "operador")
    antes_b = await _caixas_de(admin_engine, cen, "b", "colega_b")
    enc = await _recusa(admin_engine, cen, "saindo", por="colega_b")

    assert (enc.recusado, enc.cancelado, enc.recebido) == (True, True, False)
    assert enc.motivo_recusa == MOTIVO
    assert enc.id_usuario_recusa == cen["colega_b"]
    assert enc.data_hora_recusa is not None

    a = await _caixas_de(admin_engine, cen, "a", "operador")
    b = await _caixas_de(admin_engine, cen, "b", "colega_b")
    assert (a.saida, a.analise, a.recusados) == (
        antes_a.saida - 1, antes_a.analise + 1, 1)
    # A Entrada de B perde só este (o cenário tem outro pendente para B).
    assert (b.entrada, b.recusados) == (antes_b.entrada - 1, 0)

    assert await _ids(admin_engine, cen, CaixaProcesso.recusados) == {"saindo"}


@pytest.mark.asyncio
async def test_reencaminhar_esvazia_a_caixa_de_recusados(admin_engine, cen):
    await _recusa(admin_engine, cen, "saindo", por="colega_b")
    assert (await _caixas_de(admin_engine, cen, "a", "operador")).recusados == 1

    async with _sm(admin_engine)() as s:
        await encaminhar(
            s, cen["procs"]["saindo"],
            EncaminharRequest(id_unidade_destino=cen["b"], id_prioridade=cen["prioridade"]),
            tenant_id=cen["tenant"].id, usuario_id=cen["operador"], is_super_usuario=True,
        )

    a = await _caixas_de(admin_engine, cen, "a", "operador")
    # O encaminhamento recusado continua no banco; a caixa olha o ÚLTIMO.
    assert (a.recusados, a.saida) == (0, 1)


@pytest.mark.asyncio
async def test_contador_de_recusados_e_o_total_da_lista(admin_engine, cen):
    await _recusa(admin_engine, cen, "saindo", por="colega_b")
    async with _sm(admin_engine)() as s:
        contexto = {"id_usuario_contexto": cen["operador"], "id_unidade_contexto": cen["a"]}
        _, total = await list_processos(
            s, tenant_id=cen["tenant"].id, page=1, page_size=50,
            caixa=CaixaProcesso.recusados, **contexto)
        contagem = await contar_caixas(s, tenant_id=cen["tenant"].id, **contexto)
    assert total == contagem.recusados == 1


@pytest.mark.asyncio
async def test_so_se_recusa_encaminhamento_pendente(admin_engine, cen):
    """`recebido` já foi recebido, `cancelado` foi cancelado pela origem e
    `na_mesa` nunca foi encaminhado: nenhum tem o que recusar."""
    for rotulo in ("recebido", "cancelado", "na_mesa"):
        with pytest.raises(AcaoError, match="Nenhum encaminhamento pendente"):
            await _recusa(admin_engine, cen, rotulo)
    # E recusar duas vezes: a segunda não acha pendente.
    await _recusa(admin_engine, cen, "saindo", por="colega_b")
    with pytest.raises(AcaoError, match="Nenhum encaminhamento pendente"):
        await _recusa(admin_engine, cen, "saindo", por="colega_b")


@pytest.mark.asyncio
async def test_o_motivo_aparece_no_detalhe_e_na_trilha(admin_engine, cen):
    """Encaminha pelo serviço (o cenário monta encaminhamentos sem
    movimentação, e é pela movimentação que o detalhe os mostra) e recusa."""
    pid = cen["procs"]["na_mesa"]
    async with _sm(admin_engine)() as s:
        await encaminhar(
            s, pid,
            EncaminharRequest(id_unidade_destino=cen["b"], id_prioridade=cen["prioridade"]),
            tenant_id=cen["tenant"].id, usuario_id=cen["operador"], is_super_usuario=True,
        )
    await _recusa(admin_engine, cen, "na_mesa", por="colega_b")
    async with _sm(admin_engine)() as s:
        detalhe = await get_processo_detail(
            s, pid, tenant_id=cen["tenant"].id, usuario_id=cen["operador"])
        trilha = (await s.execute(text(
            "SELECT id_usuario, payload FROM aprimora_py.audit_log WHERE tenant_id=:t "
            "AND acao='processo.encaminhamento_recusado' AND id_entidade=:p"),
            {"t": cen["tenant"].id, "p": pid})).all()

    encaminhamentos = [m.encaminhamento for m in detalhe.movimentacoes if m.encaminhamento]
    assert [(e.recusado, e.motivo_recusa) for e in encaminhamentos] == [(True, MOTIVO)]
    despachos = [m.despacho.despacho for m in detalhe.movimentacoes if m.despacho]
    assert despachos == [f"[Recusa de encaminhamento] {MOTIVO}"]
    assert [(u, p["motivo"]) for u, p in trilha] == [(cen["colega_b"], MOTIVO)]


def test_motivo_e_obrigatorio_e_espaco_nao_conta():
    from pydantic import ValidationError

    for ruim in ("", "    ", "ok", "  a   "):
        with pytest.raises(ValidationError):
            RecusarEncaminhamentoRequest(motivo=ruim)
    assert RecusarEncaminhamentoRequest(motivo="  Não é daqui.  ").motivo == "Não é daqui."


@pytest.mark.asyncio
async def test_http_usuario_comum_recusa_e_quem_enviou_e_avisado(admin_engine, cen):
    """Pela borda, com operador não-SU. `saindo` foi de A para B, enviado por
    `operador` (quem assina os encaminhamentos do cenário); quem recusa é
    `colega_b`, lotado em B."""
    t = cen["tenant"]
    pid = cen["procs"]["saindo"]
    app.dependency_overrides[get_current_user] = _como(admin_engine, cen["colega_b"])
    arreio_tenant_http(t.id, t.slug)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        sem_motivo = await client.post(
            f"/api/v2/processos/{pid}/recusar-encaminhamento", json={"motivo": "  "})
        assert sem_motivo.status_code == 422, sem_motivo.text

        r = await client.post(
            f"/api/v2/processos/{pid}/recusar-encaminhamento", json={"motivo": MOTIVO})
        assert r.status_code == 200, r.text

        de_novo = await client.post(
            f"/api/v2/processos/{pid}/recusar-encaminhamento", json={"motivo": MOTIVO})
        assert de_novo.status_code == 400, de_novo.text

        caixas = await client.get("/api/v2/processos/caixas")
        assert caixas.status_code == 200 and "recusados" in caixas.json()

    async with _sm(admin_engine)() as s:
        avisos = (await s.execute(text(
            "SELECT id_usuario, tipo, link_url FROM aprimora_py.notificacao "
            "WHERE tenant_id=:t AND tipo='encaminhamento_recusado'"), {"t": t.id})).all()
        await s.execute(
            text("DELETE FROM aprimora_py.notificacao WHERE tenant_id=:t"), {"t": t.id})
        await s.commit()
    assert avisos == [(cen["operador"], "encaminhamento_recusado", f"/m/protocolo/processos/{pid}")]


@pytest.mark.asyncio
async def test_http_sem_a_transacao_processo_nao_recusa(admin_engine, cen):
    t = cen["tenant"]
    app.dependency_overrides[get_current_user] = _como(admin_engine, cen["sem_lotacao"])
    arreio_tenant_http(t.id, t.slug)
    async with _sm(admin_engine)() as s:
        await s.execute(text("DELETE FROM utils.usuario_grupo WHERE id_usuario=:u"),
                        {"u": cen["sem_lotacao"]})
        await s.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            f"/api/v2/processos/{cen['procs']['saindo']}/recusar-encaminhamento",
            json={"motivo": MOTIVO})
    assert r.status_code == 403, r.text
    async with _sm(admin_engine)() as s:
        recusado = (await s.execute(text(
            "SELECT recusado FROM protocolos.encaminhamento WHERE id_processo=:p"),
            {"p": cen["procs"]["saindo"]})).scalar_one()
    assert recusado is False


# ---------------------------------------------------------------------------
# Receber e recusar são da unidade de DESTINO
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_so_quem_e_do_destino_recebe_ou_recusa(admin_engine, cen):
    """`saindo` vai de A para B. `operador` é de A: não recebe nem recusa. O
    encaminhamento continua pendente depois das duas tentativas."""
    from app.services.acoes_processo import NaoLotadoNoDestinoError, receber

    pid = cen["procs"]["saindo"]
    async with _sm(admin_engine)() as s:
        with pytest.raises(NaoLotadoNoDestinoError, match="lotado na unidade de destino"):
            await receber(s, pid, tenant_id=cen["tenant"].id, usuario_id=cen["operador"])
    with pytest.raises(NaoLotadoNoDestinoError):
        await _recusa(admin_engine, cen, "saindo", por="operador")

    async with _sm(admin_engine)() as s:
        recebido, recusado = (await s.execute(text(
            "SELECT recebido, recusado FROM protocolos.encaminhamento WHERE id_processo=:p"),
            {"p": pid})).one()
    assert (recebido, recusado) == (False, False)


@pytest.mark.asyncio
async def test_lotacao_secundaria_no_destino_vale(admin_engine, cen):
    """Quem atua em dois setores tem a lotação extra em
    `utils.usuario_unidade_trabalho`. Ela basta para receber."""
    from app.services.acoes_processo import receber

    async with _sm(admin_engine)() as s:
        await s.execute(text(
            "INSERT INTO utils.usuario_unidade_trabalho (tenant_id, id_usuario, "
            "id_unidade_trabalho, excluido) VALUES (:t, :u, :b, false)"),
            {"t": cen["tenant"].id, "u": cen["operador"], "b": cen["b"]})
        await s.commit()
    try:
        async with _sm(admin_engine)() as s:
            enc = await receber(
                s, cen["procs"]["saindo"], tenant_id=cen["tenant"].id,
                usuario_id=cen["operador"])
        assert enc.recebido is True
    finally:
        async with _sm(admin_engine)() as s:
            await s.execute(text(
                "DELETE FROM utils.usuario_unidade_trabalho WHERE id_usuario=:u"),
                {"u": cen["operador"]})
            await s.commit()


@pytest.mark.asyncio
async def test_super_usuario_continua_passando(admin_engine, cen):
    async with _sm(admin_engine)() as s:
        enc = await recusar_encaminhamento(
            s, cen["procs"]["saindo"], RecusarEncaminhamentoRequest(motivo=MOTIVO),
            tenant_id=cen["tenant"].id, usuario_id=cen["operador"], is_super_usuario=True)
    assert enc.recusado is True


@pytest.mark.asyncio
async def test_http_quem_nao_e_do_destino_leva_403(admin_engine, cen):
    """Pela borda, com usuário comum: 403 com a unidade na mensagem, e não 400 —
    é falta de competência para o ato, não estado inválido do processo."""
    t = cen["tenant"]
    pid = cen["procs"]["saindo"]
    app.dependency_overrides[get_current_user] = _como(admin_engine, cen["operador"])
    arreio_tenant_http(t.id, t.slug)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(f"/api/v2/processos/{pid}/receber")
        assert r.status_code == 403, r.text
        assert "unidade de destino" in r.json()["detail"]
        r = await client.post(
            f"/api/v2/processos/{pid}/recusar-encaminhamento", json={"motivo": MOTIVO})
        assert r.status_code == 403, r.text

    # Quem é de B recebe pela mesma porta.
    app.dependency_overrides[get_current_user] = _como(admin_engine, cen["colega_b"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(f"/api/v2/processos/{pid}/receber")
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Cancelar é da unidade de ORIGEM; o detalhe diz a cada um o que pode decidir
# ---------------------------------------------------------------------------


async def _enc_pendente(engine, cen, rotulo: str) -> int:
    async with _sm(engine)() as s:
        return (await s.execute(text(
            "SELECT id FROM protocolos.encaminhamento WHERE id_processo=:p "
            "AND recebido=false AND cancelado=false"),
            {"p": cen["procs"][rotulo]})).scalar_one()


@pytest.mark.asyncio
async def test_so_quem_e_da_origem_cancela(admin_engine, cen):
    """`saindo` vai de A para B. `colega_b` é do destino: não cancela; o
    `operador`, de A, cancela."""
    from app.schemas.processo import CancelarEncaminhamentoRequest
    from app.services.acoes_processo import NaoLotadoNaOrigemError, cancelar_encaminhamento

    enc_id = await _enc_pendente(admin_engine, cen, "saindo")
    pedido = CancelarEncaminhamentoRequest(despacho=None)
    async with _sm(admin_engine)() as s:
        with pytest.raises(NaoLotadoNaOrigemError, match="lotado na unidade de origem"):
            await cancelar_encaminhamento(
                s, enc_id, pedido, tenant_id=cen["tenant"].id, usuario_id=cen["colega_b"])
    async with _sm(admin_engine)() as s:
        enc = await cancelar_encaminhamento(
            s, enc_id, pedido, tenant_id=cen["tenant"].id, usuario_id=cen["operador"])
    assert enc.cancelado is True


@pytest.mark.asyncio
async def test_detalhe_diz_a_cada_um_o_que_pode_decidir(admin_engine, cen):
    pid = cen["procs"]["saindo"]
    async with _sm(admin_engine)() as s:
        da_origem = await get_processo_detail(
            s, pid, tenant_id=cen["tenant"].id, usuario_id=cen["operador"])
        do_destino = await get_processo_detail(
            s, pid, tenant_id=cen["tenant"].id, usuario_id=cen["colega_b"])
        sem_usuario = await get_processo_detail(s, pid, tenant_id=cen["tenant"].id)
        sem_pendente = await get_processo_detail(
            s, cen["procs"]["na_mesa"], tenant_id=cen["tenant"].id, usuario_id=cen["operador"])

    assert (da_origem.pode_receber_encaminhamento,
            da_origem.pode_cancelar_encaminhamento) == (False, True)
    assert (do_destino.pode_receber_encaminhamento,
            do_destino.pode_cancelar_encaminhamento) == (True, False)
    # Sem usuário ou sem pendente: não se afirma nada.
    assert (sem_usuario.pode_receber_encaminhamento,
            sem_usuario.pode_cancelar_encaminhamento) == (None, None)
    assert (sem_pendente.pode_receber_encaminhamento,
            sem_pendente.pode_cancelar_encaminhamento) == (None, None)


@pytest.mark.asyncio
async def test_http_cancelar_de_fora_da_origem_e_403(admin_engine, cen):
    t = cen["tenant"]
    enc_id = await _enc_pendente(admin_engine, cen, "saindo")
    app.dependency_overrides[get_current_user] = _como(admin_engine, cen["colega_b"])
    arreio_tenant_http(t.id, t.slug)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            f"/api/v2/processos/encaminhamentos/{enc_id}/cancelar", json={})
        assert r.status_code == 403, r.text
        assert "unidade de origem" in r.json()["detail"]
