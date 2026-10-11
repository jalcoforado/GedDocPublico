"""Atos financeiros de pagamentos gravam trilha em `aprimora_py.audit_log`.

Até 2026-10-11 só o cadastro bancário do fornecedor, os anexos e os ajustes
deixavam trilha ali. Autorizar, liberar, pagar, estornar, revogar e o ciclo do
lote só apareciam em `debito_historico` — que conta a história de UM débito e
não responde "o que esta pessoa ordenou neste período".

A trilha entra na mesma transação do ato: se o ato não acontece, a linha não
existe (o segundo teste trava isso).
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.schemas.pagamentos import NaturezaCreate, RetornoParcelaIn
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_lotes as lot
from tests.fixtures.pagamentos import id_unidade_padrao
from tests.test_pagamentos_f4_lote import (
    _cleanup, _criar_usuario, _debito_liberado, _fonte_conta, _fornecedor2,
    _lote_ate_enviado, _provisionar, _sm,
)


async def _trilha(engine, tenant_id: int) -> list[tuple[str, str, int | None, int | None, dict]]:
    async with _sm(engine)() as s:
        rows = (await s.execute(text(
            "SELECT acao, entidade, id_entidade, id_usuario, payload "
            "FROM aprimora_py.audit_log WHERE tenant_id=:t AND acao LIKE 'pagamento.%' "
            "ORDER BY id"), {"t": tenant_id})).all()
    return [(r[0], r[1], r[2], r[3], r[4] or {}) for r in rows]


@pytest.mark.asyncio
async def test_ciclo_do_lote_deixa_trilha_com_autor_em_cada_ato(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        lote, d1, p1, conta = await _lote_ate_enviado(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            await lot.processar_retorno(
                s, tenant_id=tenant.id, lote_id=lote.id, usuario_id=d1.id_usuario_solicitante,
                retornos=[RetornoParcelaIn(parcela_id=p1, resultado="PAGA", forma_pagamento="PIX")])

        trilha = await _trilha(admin_engine, tenant.id)
        assert [t[0] for t in trilha] == [
            "pagamento.autorizado", "pagamento.parcelas_liberadas",
            "pagamento.lote_enviado", "pagamento.lote_retorno",
        ]
        # Todo ato tem autor: é para isso que a trilha existe.
        assert all(t[3] is not None for t in trilha)

        autorizado, liberadas, enviado, retorno = trilha
        assert autorizado[1] == "ordem_pagamento" and autorizado[2] is not None
        assert autorizado[4]["debito_ids"] == [d1.id]
        assert autorizado[4]["id_conta_pagadora"] == conta.id
        assert autorizado[4]["excecao_saldo"] is False
        assert liberadas[4]["parcela_ids"] == [p1]
        assert enviado[1] == "lote_pagamento" and enviado[2] == lote.id
        assert enviado[4]["parcela_ids"] == [p1]
        assert retorno[4]["retornos"] == [{
            "parcela_id": p1, "resultado": "PAGA", "forma_pagamento": "PIX", "motivo_falha": None}]
        assert retorno[4]["situacao_lote"] == "PROCESSADO"
    finally:
        await _cleanup(admin_engine, tenant.id)


async def _liberado(engine, tenant_id: int):
    async with _sm(engine)() as s:
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
    async with _sm(engine)() as s:
        unidade_id = await id_unidade_padrao(s, tenant_id)
    fonte, conta = await _fonte_conta(engine, tenant_id)
    forn = await _fornecedor2(engine, tenant_id, nome="Forn Trilha LTDA")
    return await _debito_liberado(engine, tenant_id, forn=forn, nat=nat, fonte=fonte,
                                  conta=conta, unidade_id=unidade_id)


@pytest.mark.asyncio
async def test_pagar_estornar_e_revogar_deixam_trilha_e_ato_recusado_nao_deixa(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        d, p = await _liberado(admin_engine, tenant.id)
        tesoureiro = await _criar_usuario(admin_engine, tenant.id, "Tesoureiro Trilha")
        autoridade = await _criar_usuario(admin_engine, tenant.id, "Autoridade Trilha")

        # Ato recusado (parcela liberada não se estorna): 409, e nenhuma linha.
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.estornar_parcela(s, tenant_id=tenant.id, usuario_id=tesoureiro,
                                           parcela_id=p, justificativa="não deveria passar")
            assert exc.value.status_code == 409
        assert "pagamento.parcela_estornada" not in [
            t[0] for t in await _trilha(admin_engine, tenant.id)]

        async with _sm(admin_engine)() as s:
            await aut.pagar_parcela(s, tenant_id=tenant.id, usuario_id=tesoureiro, parcela_id=p,
                                    forma_pagamento="PIX", data_pagamento=date(2026, 10, 9))
        async with _sm(admin_engine)() as s:
            await aut.estornar_parcela(s, tenant_id=tenant.id, usuario_id=tesoureiro,
                                       parcela_id=p, justificativa="Pago em duplicidade")
        # Depois do estorno a parcela volta a A_PAGAR: libera de novo e revoga.
        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=tenant.id, usuario_id=autoridade,
                                       parcela_ids=[p])
        async with _sm(admin_engine)() as s:
            await aut.revogar_liberacao(s, tenant_id=tenant.id, usuario_id=autoridade,
                                        parcela_id=p, justificativa="Liberada por engano")

        trilha = {t[0]: t for t in await _trilha(admin_engine, tenant.id)}
        paga = trilha["pagamento.parcela_paga"]
        assert (paga[1], paga[2], paga[3]) == ("parcela", p, tesoureiro)
        assert paga[4]["forma_pagamento"] == "PIX"
        assert paga[4]["data_pagamento"] == "2026-10-09"
        assert paga[4]["id_debito"] == d.id

        estornada = trilha["pagamento.parcela_estornada"]
        assert (estornada[2], estornada[3]) == (p, tesoureiro)
        assert estornada[4]["justificativa"] == "Pago em duplicidade"

        revogada = trilha["pagamento.liberacao_revogada"]
        assert (revogada[2], revogada[3]) == (p, autoridade)
        assert revogada[4]["justificativa"] == "Liberada por engano"
    finally:
        await _cleanup(admin_engine, tenant.id)
