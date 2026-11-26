"""Recolhimento de retenção pela porta HTTP, com usuário COMUM.

`POST /pagamentos/retencoes/{id}/recolher` não tinha chamador até o detalhe do
débito ganhar o botão "Recolher"; só havia teste de service.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text

from app.schemas.pagamentos import RetencaoCreate
from app.services import pagamentos_retencoes as ret
from tests.test_pagamentos_f4_retencao import (
    _cleanup, _post, _provisionar, _setup_debito, _sm, _usuario_com,
)


async def _retencao_pendente(engine):
    tenant, solicitante_id = await _provisionar(engine)
    debito, _conta = await _setup_debito(engine, tenant.id, solicitante_id)
    async with _sm(engine)() as s:
        r = await ret.criar_retencao(
            s, tenant_id=tenant.id, debito_id=debito.id,
            payload=RetencaoCreate(tipo="INSS", base_calculo=Decimal("1000.00"),
                                   valor=Decimal("110.00")))
    return tenant, r


@pytest.mark.asyncio
async def test_http_tesouraria_comum_registra_o_recolhimento(admin_engine):
    tenant, r = await _retencao_pendente(admin_engine)
    try:
        tesouraria = await _usuario_com(admin_engine, tenant.id, ["pagamento_pagar"])
        resp = await _post(
            admin_engine, tenant.id, tenant.slug, tesouraria,
            f"/api/v2/pagamentos/retencoes/{r.id}/recolher",
            {"data_recolhimento": "2026-10-10", "documento_recolhimento": "GPS-123"})
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert corpo["recolhido"] is True
        assert corpo["data_recolhimento"] == "2026-10-10"
        assert corpo["documento_recolhimento"] == "GPS-123"

        async with _sm(admin_engine)() as s:
            pendentes = await ret.listar_pendentes_recolhimento(s, tenant_id=tenant.id)
            # Quem recolheu fica na trilha de auditoria, como nos demais atos.
            autores = (await s.execute(text(
                "SELECT id_usuario FROM aprimora_py.audit_log WHERE tenant_id=:t "
                "AND acao='pagamento.retencao_recolhida' AND id_entidade=:r"),
                {"t": tenant.id, "r": r.id})).scalars().all()
        assert r.id not in [p.id for p in pendentes]
        assert autores == [tesouraria]
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_quem_so_solicita_nao_registra_recolhimento(admin_engine):
    tenant, r = await _retencao_pendente(admin_engine)
    try:
        solicitante = await _usuario_com(admin_engine, tenant.id, ["pagamento_solicitar"])
        resp = await _post(
            admin_engine, tenant.id, tenant.slug, solicitante,
            f"/api/v2/pagamentos/retencoes/{r.id}/recolher",
            {"data_recolhimento": "2026-10-10", "documento_recolhimento": "GPS-123"})
        assert resp.status_code == 403, resp.text

        async with _sm(admin_engine)() as s:
            pendentes = await ret.listar_pendentes_recolhimento(s, tenant_id=tenant.id)
        assert r.id in [p.id for p in pendentes]
    finally:
        await _cleanup(admin_engine, tenant.id)
