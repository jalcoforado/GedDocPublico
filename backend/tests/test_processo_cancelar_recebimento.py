"""Cancelar recebimento feito por engano — SI-61, RF-02 do documento "GEDPub –
Requisitos de evolução v1.0" (18/11/2026).

O cenário é o de `test_processo_caixas.py`. O processo `chegando` vem de B
para A e ainda não foi recebido; cada teste o RECEBE pelo serviço real antes
de cancelar — o `recebido` do cenário foi montado sem a movimentação de
recebimento e não serve. `operador` é usuário comum (não-SU) lotado em A, a
unidade que recebe; `colega_b` é de B.

O que mais importa aqui são os BLOQUEIOS: o RF-02 só permite desfazer o
recebimento se nada aconteceu depois dele, e "nada" mora em quatro lugares
diferentes (movimentação, despacho/anexo, trilha de auditoria, workflow). Um
teste por lugar, para que esquecer um deles fique vermelho.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select, text

from app.auth.deps import get_current_user
from app.main import app
from app.models import Anexo, AnexoProcesso, Despacho, Encaminhamento, Movimentacao
from app.models.workflow import WorkflowDefinition, WorkflowInstance, WorkflowTransicaoLog
from app.schemas.processo import (
    CaixaProcesso,
    CancelarRecebimentoRequest,
    EncaminharRequest,
    RecusarEncaminhamentoRequest,
)
from app.services.acoes_processo import (
    AcaoError,
    NaoLotadoNoDestinoError,
    atribuir_responsavel,
    cancelar_recebimento,
    encaminhar,
    receber,
    recusar_encaminhamento,
)
from app.services.processos import get_processo_detail
from tests.conftest import arreio_tenant_http
from tests.test_processo_caixas import _como, _ids, _sm, cen  # noqa: F401 — fixture

JUSTIFICATIVA = "Recebido por engano, era da Educação"


async def _recebe(engine, cen, rotulo: str = "chegando") -> Movimentacao:
    async with _sm(engine)() as s:
        await receber(s, cen["procs"][rotulo], tenant_id=cen["tenant"].id,
                      usuario_id=cen["operador"])
    async with _sm(engine)() as s:
        return (await s.execute(
            select(Movimentacao)
            .where(Movimentacao.id_processo == cen["procs"][rotulo])
            .order_by(Movimentacao.id.desc()).limit(1)
        )).scalar_one()


async def _cancela(engine, cen, rotulo: str = "chegando", *, por: str = "operador"):
    async with _sm(engine)() as s:
        return await cancelar_recebimento(
            s, cen["procs"][rotulo], CancelarRecebimentoRequest(justificativa=JUSTIFICATIVA),
            tenant_id=cen["tenant"].id, usuario_id=cen[por],
        )


async def _detalhe(engine, cen, rotulo: str = "chegando", *, por: str = "operador"):
    async with _sm(engine)() as s:
        d = await get_processo_detail(
            s, cen["procs"][rotulo], tenant_id=cen["tenant"].id, usuario_id=cen[por])
    assert d is not None
    return d


async def _concede(engine, usuario_id: int, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        await s.execute(text("""
            INSERT INTO utils.grupo_transacao
                (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
            SELECT :t, ug.id_grupo, tr.id, true, true, true, false
              FROM utils.usuario_grupo ug, utils.transacao tr
             WHERE ug.id_usuario = :u AND ug.excluido = false
               AND tr.codigo = 'processo_cancelar_recebimento' AND tr.excluido = false
        """), {"t": tenant_id, "u": usuario_id})
        await s.commit()


# --------------------------------------------------------------------------
# Catálogo
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_garante_acao_e_transacao(admin_engine):
    async with _sm(admin_engine)() as s:
        acao = (await s.execute(text(
            "SELECT status_movimentacao FROM protocolos.acao "
            "WHERE flag='CANCELAMENTO_RECEBIMENTO' AND ativo AND NOT excluido"
        ))).scalar_one_or_none()
        transacao = (await s.execute(text(
            "SELECT 1 FROM utils.transacao WHERE codigo='processo_cancelar_recebimento' "
            "AND NOT excluido"
        ))).scalar_one_or_none()
    assert acao == "encaminhado", "ação ausente — rode o seed_bootstrap"
    assert transacao is not None, "transação ausente — rode `alembic upgrade head`"


# --------------------------------------------------------------------------
# O processo volta a aguardar recebimento — e o histórico guarda tudo
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_volta_a_aguardar_recebimento_na_unidade(admin_engine, cen):
    await _recebe(admin_engine, cen)
    assert "chegando" in await _ids(admin_engine, cen, CaixaProcesso.analise)
    assert "chegando" not in await _ids(admin_engine, cen, CaixaProcesso.entrada)

    await _cancela(admin_engine, cen)

    assert "chegando" in await _ids(admin_engine, cen, CaixaProcesso.entrada)
    assert "chegando" not in await _ids(admin_engine, cen, CaixaProcesso.analise)
    d = await _detalhe(admin_engine, cen)
    assert d.local_atual == "B"  # onde estava antes de ser recebido
    assert d.pode_receber_encaminhamento is True


@pytest.mark.asyncio
async def test_historico_guarda_o_recebimento_e_mostra_o_cancelamento(admin_engine, cen):
    receb = await _recebe(admin_engine, cen)
    await _cancela(admin_engine, cen)

    d = await _detalhe(admin_engine, cen)
    flags = [m.acao_flag for m in d.movimentacoes]
    assert "RECEBIMENTO" in flags and "CANCELAMENTO_RECEBIMENTO" in flags
    canc = next(m for m in d.movimentacoes if m.acao_flag == "CANCELAMENTO_RECEBIMENTO")
    assert canc.despacho is not None and canc.despacho.despacho == JUSTIFICATIVA

    async with _sm(admin_engine)() as s:
        mov = (await s.execute(select(Movimentacao).where(
            Movimentacao.id == receb.id))).scalar_one()
        enc = (await s.execute(select(Encaminhamento).where(
            Encaminhamento.id == receb.id_encaminhamento))).scalar_one()
        trilha = (await s.execute(text(
            "SELECT id_usuario, payload->>'justificativa', payload->>'recebido_em' "
            "FROM aprimora_py.audit_log "
            "WHERE tenant_id=:t AND acao='processo.recebimento_cancelado'"
        ), {"t": cen["tenant"].id})).one()
    assert mov.ativo is False and mov.excluido is False
    assert enc.recebido is False and enc.cancelado is False
    assert enc.data_hora_recebimento is None
    assert trilha[0] == cen["operador"] and trilha[1] == JUSTIFICATIVA
    assert trilha[2] is not None  # a data original do recebimento fica na trilha


@pytest.mark.asyncio
async def test_depois_de_cancelar_a_unidade_pode_recusar(admin_engine, cen):
    """O caminho do exemplo do RF-02: a Saúde recebeu o que era da Educação,
    cancela o recebimento, recusa, e o processo volta para quem enviou."""
    await _recebe(admin_engine, cen)
    await _cancela(admin_engine, cen)
    async with _sm(admin_engine)() as s:
        await recusar_encaminhamento(
            s, cen["procs"]["chegando"], RecusarEncaminhamentoRequest(motivo="Não é daqui"),
            tenant_id=cen["tenant"].id, usuario_id=cen["operador"],
        )
    assert "chegando" not in await _ids(admin_engine, cen, CaixaProcesso.entrada)
    assert "chegando" in await _ids(
        admin_engine, cen, CaixaProcesso.recusados,
        id_usuario_contexto=cen["colega_b"], id_unidade_contexto=cen["b"],
    )


# --------------------------------------------------------------------------
# Bloqueios: qualquer ato depois do recebimento
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_movimentacao_depois_bloqueia(admin_engine, cen):
    await _recebe(admin_engine, cen)
    async with _sm(admin_engine)() as s:
        await encaminhar(
            s, cen["procs"]["chegando"],
            EncaminharRequest(id_unidade_destino=cen["b"], id_prioridade=cen["prioridade"]),
            tenant_id=cen["tenant"].id, usuario_id=cen["operador"],
        )
    # O encaminhamento novo ainda nem foi recebido: o "último recebido" é o
    # de antes, e ele já não é o último ato.
    with pytest.raises(AcaoError, match="outra movimentação"):
        await _cancela(admin_engine, cen)


@pytest.mark.asyncio
async def test_despacho_depois_bloqueia(admin_engine, cen):
    receb = await _recebe(admin_engine, cen)
    async with _sm(admin_engine)() as s:
        s.add(Despacho(
            tenant_id=cen["tenant"].id, id_processo=cen["procs"]["chegando"],
            despacho="Analisado", id_usuario=cen["operador"], id_movimentacao=receb.id,
            ativo=True, excluido=False,
        ))
        await s.commit()
    with pytest.raises(AcaoError, match="despacho"):
        await _cancela(admin_engine, cen)


@pytest.mark.asyncio
async def test_documento_anexado_depois_bloqueia(admin_engine, cen):
    """O upload liga o anexo a `id_ultima_movimentacao`, que depois de receber
    é a do recebimento."""
    receb = await _recebe(admin_engine, cen)
    async with _sm(admin_engine)() as s:
        anexo = Anexo(tenant_id=cen["tenant"].id, publico=False, ativo=True,
                      excluido=False, descricao="Parecer")
        s.add(anexo)
        await s.flush()
        s.add(AnexoProcesso(
            tenant_id=cen["tenant"].id, id_processo=cen["procs"]["chegando"],
            id_anexo=anexo.id, id_movimentacao=receb.id, id_usuario=cen["operador"],
            ativo=True, excluido=False, anexo_herdado=False,
        ))
        await s.commit()
        id_anexo = anexo.id
    try:
        with pytest.raises(AcaoError, match="documento"):
            await _cancela(admin_engine, cen)
    finally:
        # A limpeza do cenário não conhece `anexo_processo`, e ela segura a
        # movimentação por FK.
        async with _sm(admin_engine)() as s:
            await s.execute(text(
                "DELETE FROM protocolos.anexo_processo WHERE id_anexo=:a"), {"a": id_anexo})
            await s.execute(text("DELETE FROM protocolos.anexo WHERE id=:a"), {"a": id_anexo})
            await s.commit()


@pytest.mark.asyncio
async def test_ato_na_trilha_depois_bloqueia(admin_engine, cen):
    """Designar responsável não é movimentação: só a trilha o registra."""
    await _recebe(admin_engine, cen)
    async with _sm(admin_engine)() as s:
        await atribuir_responsavel(
            s, cen["procs"]["chegando"], tenant_id=cen["tenant"].id,
            id_usuario=cen["operador"], usuario_id=cen["operador"],
        )
    with pytest.raises(AcaoError, match="designação de responsável"):
        await _cancela(admin_engine, cen)
    d = await _detalhe(admin_engine, cen)
    assert d.pode_cancelar_recebimento is False
    assert "designação de responsável" in (d.motivo_cancelar_recebimento or "")


@pytest.mark.asyncio
async def test_fluxo_que_avancou_com_o_recebimento_bloqueia(admin_engine, cen):
    await _recebe(admin_engine, cen)
    t = cen["tenant"].id
    async with _sm(admin_engine)() as s:
        wf = WorkflowDefinition(
            tenant_id=t, slug="fluxo", nome="Fluxo", versao=1, ativo=True,
            dsl={"estados": [{"slug": "a"}, {"slug": "b"}], "transicoes": []},
            criado_em=datetime.now(),
        )
        s.add(wf)
        await s.flush()
        inst = WorkflowInstance(
            tenant_id=t, id_workflow_definition=wf.id, id_processo=cen["procs"]["chegando"],
            entidade_tipo="processo", entidade_id=cen["procs"]["chegando"],
            estado_atual="b", ativa=True, iniciada_em=datetime.now(),
        )
        s.add(inst)
        await s.flush()
        s.add(WorkflowTransicaoLog(
            tenant_id=t, id_workflow_instance=inst.id, estado_de="a", estado_para="b",
            transicao_label="recebimento", executada_em=datetime.now(),
        ))
        await s.commit()
    try:
        with pytest.raises(AcaoError, match="fluxo do processo já avançou"):
            await _cancela(admin_engine, cen)
    finally:
        async with _sm(admin_engine)() as s:
            for tabela in ("workflow_transicao_log", "workflow_instance", "workflow_definition"):
                await s.execute(text(
                    f"DELETE FROM aprimora_py.{tabela} WHERE tenant_id=:t"), {"t": t})
            await s.commit()


# --------------------------------------------------------------------------
# Quem pode, e o que não tem o que cancelar
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_so_quem_e_da_unidade_que_recebeu_cancela(admin_engine, cen):
    await _recebe(admin_engine, cen)
    with pytest.raises(NaoLotadoNoDestinoError, match="unidade que recebeu"):
        await _cancela(admin_engine, cen, por="colega_b")
    # E a tela não oferece o botão a quem é de fora.
    assert (await _detalhe(admin_engine, cen, por="colega_b")).pode_cancelar_recebimento is None
    assert (await _detalhe(admin_engine, cen)).pode_cancelar_recebimento is True


@pytest.mark.asyncio
async def test_sem_recebimento_nao_ha_o_que_cancelar(admin_engine, cen):
    with pytest.raises(AcaoError, match="não tem recebimento"):
        await _cancela(admin_engine, cen, "na_mesa")
    with pytest.raises(AcaoError, match="não tem recebimento"):
        await _cancela(admin_engine, cen)  # `chegando` ainda não recebido
    assert (await _detalhe(admin_engine, cen)).pode_cancelar_recebimento is None


@pytest.mark.asyncio
async def test_segundo_clique_nao_cancela_duas_vezes(admin_engine, cen):
    await _recebe(admin_engine, cen)
    await _cancela(admin_engine, cen)
    with pytest.raises(AcaoError, match="não tem recebimento"):
        await _cancela(admin_engine, cen)


def test_justificativa_e_obrigatoria_e_espaco_nao_conta():
    for ruim in ("", "    ", "abc"):
        with pytest.raises(ValidationError):
            CancelarRecebimentoRequest(justificativa=ruim)
    assert CancelarRecebimentoRequest(justificativa="  Engano  ").justificativa == "Engano"


# --------------------------------------------------------------------------
# A borda HTTP, com usuário comum
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_usuario_comum_sem_a_transacao_leva_403(admin_engine, cen):
    await _recebe(admin_engine, cen)
    t = cen["tenant"]
    app.dependency_overrides[get_current_user] = _como(admin_engine, cen["operador"])
    arreio_tenant_http(t.id, t.slug)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            f"/api/v2/processos/{cen['procs']['chegando']}/cancelar-recebimento",
            json={"justificativa": JUSTIFICATIVA},
        )
    assert r.status_code == 403, r.text
    assert "chegando" in await _ids(admin_engine, cen, CaixaProcesso.analise)


@pytest.mark.asyncio
async def test_http_usuario_comum_cancela_e_quem_enviou_e_avisado(admin_engine, cen):
    receb = await _recebe(admin_engine, cen)
    t = cen["tenant"]
    # Quem enviou de B foi `colega_b` (o cenário assina tudo como `operador`).
    async with _sm(admin_engine)() as s:
        await s.execute(text("UPDATE protocolos.encaminhamento SET id_usuario=:u WHERE id=:e"),
                        {"u": cen["colega_b"], "e": receb.id_encaminhamento})
        await s.commit()
    await _concede(admin_engine, cen["operador"], t.id)
    app.dependency_overrides[get_current_user] = _como(admin_engine, cen["operador"])
    arreio_tenant_http(t.id, t.slug)
    pid = cen["procs"]["chegando"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        sem = await client.post(f"/api/v2/processos/{pid}/cancelar-recebimento",
                                json={"justificativa": " "})
        assert sem.status_code == 422, sem.text

        r = await client.post(f"/api/v2/processos/{pid}/cancelar-recebimento",
                              json={"justificativa": JUSTIFICATIVA})
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert corpo["local_atual"] == "B"
        assert any(m["acao_flag"] == "CANCELAMENTO_RECEBIMENTO" for m in corpo["movimentacoes"])

        de_novo = await client.post(f"/api/v2/processos/{pid}/cancelar-recebimento",
                                    json={"justificativa": JUSTIFICATIVA})
        assert de_novo.status_code == 400, de_novo.text

    async with _sm(admin_engine)() as s:
        avisos = (await s.execute(text(
            "SELECT id_usuario, link_url FROM aprimora_py.notificacao "
            "WHERE tenant_id=:t AND tipo='recebimento_cancelado'"), {"t": t.id})).all()
        await s.execute(
            text("DELETE FROM aprimora_py.notificacao WHERE tenant_id=:t"), {"t": t.id})
        await s.commit()
    assert avisos == [(cen["colega_b"], f"/m/protocolo/processos/{pid}")]


@pytest.mark.asyncio
async def test_http_de_outra_prefeitura_e_404(admin_engine, cen, two_tenants):
    """Servidor da prefeitura B, com o módulo e a transação, tenta cancelar o
    recebimento de um processo da A: 404, e nada muda."""
    from tests.test_permissoes_modulo import _cria_usuario_comum as _usuario_com

    await _recebe(admin_engine, cen)
    outro, _ = two_tenants
    async with _sm(admin_engine)() as s:
        await s.execute(text(
            "INSERT INTO aprimora_py.tenant_modulo (tenant_id, id_modulo) "
            "SELECT :t, id FROM aprimora_py.modulo WHERE slug='protocolo'"), {"t": outro})
        alheio = await _usuario_com(s, outro, codigo_transacao="processo_cancelar_recebimento")
        await s.commit()
    app.dependency_overrides[get_current_user] = _como(admin_engine, alheio)
    arreio_tenant_http(outro)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/api/v2/processos/{cen['procs']['chegando']}/cancelar-recebimento",
                json={"justificativa": JUSTIFICATIVA},
            )
    finally:
        async with _sm(admin_engine)() as s:
            for tabela in ("utils.grupo_transacao", "utils.usuario_grupo", "utils.grupo",
                           "aprimora_py.audit_log", "utils.usuario",
                           "aprimora_py.tenant_modulo"):
                await s.execute(text(f"DELETE FROM {tabela} WHERE tenant_id=:t"), {"t": outro})
            await s.commit()
    assert r.status_code == 404, r.text
    assert "chegando" in await _ids(admin_engine, cen, CaixaProcesso.analise)
