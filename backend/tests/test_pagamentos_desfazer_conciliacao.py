"""Desfazer conciliação — o inverso de `conciliar`, que não existia.

Lançamento casado com a movimentação errada ficava assim para sempre, e o
débito seguia CONCILIADO sobre um casamento falso. O que se trava aqui:

- desfazer devolve o lançamento a pendente e o débito de CONCILIADA a PAGA;
- o saldo conciliado da conta volta a não contar aquele pagamento;
- a linha desfeita NÃO é apagada: fica marcada, com quem desfez e por quê;
- dá para conciliar DE NOVO, porque as unicidades da tabela passaram a valer
  só para conciliação vigente (migration 0133);
- fica trilha de quem desfez e por quê;
- sem justificativa, ou sobre lançamento pendente, nada muda.

Segue o arreio de `test_pagamentos_conciliacao_v2.py`.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.schemas.pagamentos import ImportarExtratoIn
from app.services import pagamentos_caixa as caixa
from app.services import pagamentos_conciliacao as conc
from app.services import pagamentos_debitos as deb
from app.services import pagamentos_estados as est
from tests.test_pagamentos_conciliacao_v2 import (
    _base, _csv, _debito_pago, _novo_usuario, _provisionar, _sm,
)
from tests.test_pagamentos_f4_retencao import _post, _usuario_com


async def _conciliado(engine):
    """Débito pago + extrato importado + baixa automática: débito CONCILIADO."""
    t = await _provisionar(engine)
    forn, nat, fonte, conta = await _base(engine, t.id)
    d, _p = await _debito_pago(engine, t.id, forn, nat, fonte, conta, valor="1000.00")
    uid = await _novo_usuario(engine, t.id, f"c{uuid.uuid4().hex[:6]}")
    async with _sm(engine)() as s:
        ex = (await conc.importar_extrato(s, tenant_id=t.id, usuario_id=uid, payload=ImportarExtratoIn(
            id_conta=conta.id, nome_arquivo="ext.csv", conteudo=_csv()))).extrato
    async with _sm(engine)() as s:
        assert await conc.baixa_automatica(s, tenant_id=t.id, id_extrato=ex.id, usuario_id=uid) == 1
    async with _sm(engine)() as s:
        lanc = (await conc.listar_lancamentos(s, tenant_id=t.id, id_extrato=ex.id))[0]
    return t, d, conta, ex, lanc, uid


async def _estado(engine, tenant_id, debito_id, conta_id, extrato_id):
    async with _sm(engine)() as s:
        d = await deb.obter_debito(s, tenant_id=tenant_id, debito_id=debito_id)
        saldo = await caixa.saldo_conta(s, tenant_id=tenant_id, conta_id=conta_id)
        lanc = (await conc.listar_lancamentos(s, tenant_id=tenant_id, id_extrato=extrato_id))[0]
        n = (await s.execute(text(
            "SELECT count(*) FROM pagamentos.conciliacao "
            "WHERE tenant_id=:t AND excluido = false"),
            {"t": tenant_id})).scalar_one()
    return d.situacao_pagamento, saldo.saldo_conciliado, lanc.conciliado, n


async def _desfeitas(engine, tenant_id):
    async with _sm(engine)() as s:
        return (await s.execute(text(
            "SELECT id_lancamento, id_usuario_desfez, motivo_desfeita, desfeita_em IS NOT NULL "
            "FROM pagamentos.conciliacao WHERE tenant_id=:t AND excluido = true ORDER BY id"),
            {"t": tenant_id})).all()


async def test_desfazer_devolve_lancamento_debito_e_saldo_e_permite_conciliar_de_novo(admin_engine):
    t, d, conta, ex, lanc, uid = await _conciliado(admin_engine)
    assert await _estado(admin_engine, t.id, d.id, conta.id, ex.id) == (
        est.CONCILIADA, Decimal("9000.00"), True, 1)

    async with _sm(admin_engine)() as s:
        l = await conc.desfazer_conciliacao(
            s, tenant_id=t.id, id_lancamento=lanc.id, usuario_id=uid,
            justificativa="Casado com a movimentação errada")
    assert l.conciliado is False
    # O pagamento continua feito; só deixou de estar conferido contra o extrato.
    assert await _estado(admin_engine, t.id, d.id, conta.id, ex.id) == (
        est.PAGA, Decimal("10000.00"), False, 0)
    # A linha não some: fica marcada, com autor, momento e motivo.
    assert [tuple(r) for r in await _desfeitas(admin_engine, t.id)] == [
        (lanc.id, uid, "Casado com a movimentação errada", True)]

    async with _sm(admin_engine)() as s:
        trilha = (await s.execute(text(
            "SELECT id_usuario, id_entidade, payload FROM aprimora_py.audit_log "
            "WHERE tenant_id=:t AND acao='pagamento.conciliacao_desfeita'"), {"t": t.id})).all()
        acoes = (await s.execute(text(
            "SELECT acao FROM pagamentos.debito_historico WHERE tenant_id=:t AND id_debito=:d "
            "ORDER BY id DESC LIMIT 1"), {"t": t.id, "d": d.id})).scalar_one()
    assert len(trilha) == 1
    assert (trilha[0][0], trilha[0][1]) == (uid, lanc.id)
    assert trilha[0][2]["justificativa"] == "Casado com a movimentação errada"
    assert trilha[0][2]["id_debito"] == d.id
    assert acoes == "CONCILIACAO_DESFEITA"

    # A sugestão reaparece e a baixa volta a funcionar.
    async with _sm(admin_engine)() as s:
        sug = await conc.sugerir_baixas(s, tenant_id=t.id, id_extrato=ex.id)
    assert len(sug) == 1
    async with _sm(admin_engine)() as s:
        assert await conc.baixa_automatica(s, tenant_id=t.id, id_extrato=ex.id, usuario_id=uid) == 1
    assert await _estado(admin_engine, t.id, d.id, conta.id, ex.id) == (
        est.CONCILIADA, Decimal("9000.00"), True, 1)
    # A desfeita e a nova convivem: uma vigente, uma no registro.
    assert len(await _desfeitas(admin_engine, t.id)) == 1


async def test_duas_conciliacoes_vigentes_do_mesmo_lancamento_o_banco_recusa(admin_engine):
    """RN-14 continua valendo no banco para a conciliação VIGENTE — a troca
    das unicidades por índices parciais não pode ter afrouxado isso."""
    from sqlalchemy.exc import IntegrityError

    t, _d, _conta, _ex, lanc, _uid = await _conciliado(admin_engine)
    async with _sm(admin_engine)() as s:
        with pytest.raises(IntegrityError):
            await s.execute(text(
                "INSERT INTO pagamentos.conciliacao "
                "(tenant_id, id_lancamento, tipo_correspondencia, criado_em) "
                "VALUES (:t, :l, 'PROVAVEL', NOW())"), {"t": t.id, "l": lanc.id})
            await s.commit()


async def test_desfazer_sem_justificativa_ou_sobre_pendente_nao_muda_nada(admin_engine):
    t, d, conta, ex, lanc, uid = await _conciliado(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await conc.desfazer_conciliacao(s, tenant_id=t.id, id_lancamento=lanc.id,
                                            usuario_id=uid, justificativa="   ")
        assert exc.value.status_code == 422
    assert await _estado(admin_engine, t.id, d.id, conta.id, ex.id) == (
        est.CONCILIADA, Decimal("9000.00"), True, 1)

    async with _sm(admin_engine)() as s:
        await conc.desfazer_conciliacao(s, tenant_id=t.id, id_lancamento=lanc.id,
                                        usuario_id=uid, justificativa="erro de casamento")
    # Segunda vez: o lançamento já está pendente.
    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await conc.desfazer_conciliacao(s, tenant_id=t.id, id_lancamento=lanc.id,
                                            usuario_id=uid, justificativa="de novo")
        assert exc.value.status_code == 409


async def test_desfazer_lancamento_de_outro_tenant_e_404(admin_engine):
    _t, _d, _conta, _ex, lanc, _uid = await _conciliado(admin_engine)
    outro = await _provisionar(admin_engine)
    intruso = await _novo_usuario(admin_engine, outro.id, f"x{uuid.uuid4().hex[:6]}")
    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await conc.desfazer_conciliacao(s, tenant_id=outro.id, id_lancamento=lanc.id,
                                            usuario_id=intruso, justificativa="tentativa")
        assert exc.value.status_code == 404


async def test_http_usuario_comum_desfaz_e_quem_so_audita_nao(admin_engine):
    t, d, conta, ex, lanc, _uid = await _conciliado(admin_engine)
    caminho = f"/api/v2/pagamentos/lancamentos/{lanc.id}/desfazer-conciliacao"

    auditor = await _usuario_com(admin_engine, t.id, ["pagamento_auditar"])
    resp = await _post(admin_engine, t.id, t.slug, auditor, caminho, {"justificativa": "não posso"})
    assert resp.status_code == 403, resp.text
    assert (await _estado(admin_engine, t.id, d.id, conta.id, ex.id))[2] is True

    tesouraria = await _usuario_com(admin_engine, t.id, ["pagamento_pagar"])
    resp = await _post(admin_engine, t.id, t.slug, tesouraria, caminho,
                       {"justificativa": "Casado com a movimentação errada"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["conciliado"] is False
    assert await _estado(admin_engine, t.id, d.id, conta.id, ex.id) == (
        est.PAGA, Decimal("10000.00"), False, 0)
