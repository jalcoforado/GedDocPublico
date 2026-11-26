"""Uma porta só para autorizar pagamento — `POST /debitos/{id}/autoridade-aprovar`.

Até 2026-10-10 esse endpoint levava o débito a AUTORIZADA sem conta pagadora,
sem ordem de pagamento e sem conferir alçada ou saldo. O débito ficava
autorizado e impagável, e a autorização em lote já não o aceitava. Hoje ele é
um lote de um (`pagamentos_autorizacao.autorizar_debito`).

Os testes passam pela porta HTTP com usuário COMUM: o defeito morava na costura
tela↔endpoint, e teste de service com super-usuário não a exercita.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.models import OrdemPagamento, OrdemPagamentoDebito
from app.schemas.pagamentos import AlcadaCreate
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as svc
from app.services import pagamentos_estados as est
from tests.test_pagamentos_f3_elegibilidade import (
    _base, _debito_ate_autoridade, _provisionar, _sm,
)
from tests.test_pagamentos_f4_retencao import _cleanup, _post, _usuario_com


async def _limpar(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        await s.execute(text("DELETE FROM pagamentos.alcada WHERE tenant_id=:t"), {"t": tenant_id})
        await s.commit()
    await _cleanup(engine, tenant_id)


async def _cenario(engine, *, valor="1000.00", saldo_inicial="10000.00", alcada="999999.00"):
    """Débito em AGUARDANDO_AUTORIDADE + autoridade comum (só `pagamento_autorizar`)."""
    t = await _provisionar(engine)
    forn, nat, fonte, conta, unidade = await _base(engine, t.id, saldo_inicial=saldo_inicial)
    d, _ = await _debito_ate_autoridade(engine, t.id, forn, nat, fonte, conta, unidade, valor=valor)
    autoridade = await _usuario_com(engine, t.id, ["pagamento_autorizar"])
    if alcada is not None:
        async with _sm(engine)() as s:
            await cad.criar_alcada(s, tenant_id=t.id, payload=AlcadaCreate(
                id_usuario=autoridade, id_natureza=None, valor_maximo=alcada))
    return t, d, conta, autoridade


async def _estado(engine, tenant_id: int, debito_id: int):
    async with _sm(engine)() as s:
        d = await svc.obter_debito(s, tenant_id=tenant_id, debito_id=debito_id)
        ops = (await s.execute(
            select(OrdemPagamento).join(
                OrdemPagamentoDebito, OrdemPagamentoDebito.id_ordem == OrdemPagamento.id,
            ).where(OrdemPagamentoDebito.id_debito == debito_id,
                    OrdemPagamento.tenant_id == tenant_id))).scalars().all()
    return d, list(ops)


@pytest.mark.asyncio
async def test_http_aprovar_grava_conta_pagadora_e_gera_ordem_de_pagamento(admin_engine):
    t, d, conta, autoridade = await _cenario(admin_engine)
    try:
        resp = await _post(
            admin_engine, t.id, t.slug, autoridade,
            f"/api/v2/pagamentos/debitos/{d.id}/autoridade-aprovar",
            {"lock_version": d.lock_version, "id_conta_pagadora": conta.id})
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert corpo["situacao_tramitacao"] == est.AUTORIZADA
        assert corpo["id_conta_pagadora"] == conta.id

        atual, ops = await _estado(admin_engine, t.id, d.id)
        assert atual.id_conta_pagadora == conta.id
        # É a ordem de pagamento que torna o débito pagável.
        assert len(ops) == 1
        assert ops[0].id_conta_pagadora == conta.id
        assert str(ops[0].valor_total) == "1000.00"
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_aprovar_sem_conta_pagadora_e_422_e_nada_muda(admin_engine):
    """O payload antigo (só `lock_version`) deixa de autorizar."""
    t, d, _conta, autoridade = await _cenario(admin_engine)
    try:
        resp = await _post(
            admin_engine, t.id, t.slug, autoridade,
            f"/api/v2/pagamentos/debitos/{d.id}/autoridade-aprovar",
            {"lock_version": d.lock_version})
        assert resp.status_code == 422, resp.text

        atual, ops = await _estado(admin_engine, t.id, d.id)
        assert atual.situacao_tramitacao == est.AGUARDANDO_AUTORIDADE
        assert ops == []
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_aprovar_respeita_a_alcada(admin_engine):
    """A porta antiga não conferia alçada; esta confere, como o lote."""
    t, d, conta, autoridade = await _cenario(admin_engine, alcada="500.00")
    try:
        resp = await _post(
            admin_engine, t.id, t.slug, autoridade,
            f"/api/v2/pagamentos/debitos/{d.id}/autoridade-aprovar",
            {"lock_version": d.lock_version, "id_conta_pagadora": conta.id})
        assert resp.status_code == 403, resp.text
        assert "alçada" in resp.json()["detail"]

        atual, ops = await _estado(admin_engine, t.id, d.id)
        assert atual.situacao_tramitacao == est.AGUARDANDO_AUTORIDADE
        assert atual.id_conta_pagadora is None
        assert ops == []
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_aprovar_sem_saldo_exige_excecao_justificada(admin_engine):
    t, d, conta, autoridade = await _cenario(admin_engine, valor="9000.00", saldo_inicial="100.00")
    try:
        caminho = f"/api/v2/pagamentos/debitos/{d.id}/autoridade-aprovar"
        resp = await _post(admin_engine, t.id, t.slug, autoridade, caminho,
                           {"lock_version": d.lock_version, "id_conta_pagadora": conta.id})
        assert resp.status_code == 422, resp.text
        assert "insuficiente" in resp.json()["detail"]

        resp = await _post(admin_engine, t.id, t.slug, autoridade, caminho, {
            "lock_version": d.lock_version, "id_conta_pagadora": conta.id,
            "permitir_saldo_insuficiente": True,
            "justificativa_excecao": "Decisão judicial com prazo."})
        assert resp.status_code == 200, resp.text

        _atual, ops = await _estado(admin_engine, t.id, d.id)
        assert len(ops) == 1
        assert ops[0].excecao_saldo is True
    finally:
        await _limpar(admin_engine, t.id)
