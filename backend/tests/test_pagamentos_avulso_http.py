"""Pagamento avulso e "em processamento" pela porta HTTP, com usuário COMUM.

`POST /parcelas/{id}/pagar` e `POST /debitos/{id}/em-processamento` não tinham
chamador até o detalhe do débito ganhar os botões; só havia teste de service.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text

from app.models import Parcela
from app.schemas.pagamentos import NaturezaCreate
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as deb
from app.services import pagamentos_estados as est
from tests.fixtures.pagamentos import id_unidade_padrao
from tests.test_pagamentos_f4_lote import (
    _cleanup, _debito_liberado, _fonte_conta, _fornecedor2, _provisionar, _sm,
)
from tests.test_pagamentos_f4_retencao import _post, _usuario_com


async def _liberado(engine, tenant_id: int):
    async with _sm(engine)() as s:
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
    async with _sm(engine)() as s:
        unidade_id = await id_unidade_padrao(s, tenant_id)
    fonte, conta = await _fonte_conta(engine, tenant_id)
    forn = await _fornecedor2(engine, tenant_id, nome="Forn Avulso LTDA")
    return await _debito_liberado(engine, tenant_id, forn=forn, nat=nat, fonte=fonte,
                                  conta=conta, unidade_id=unidade_id)


@pytest.mark.asyncio
async def test_http_tesouraria_comum_paga_parcela_avulsa(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        d, p = await _liberado(admin_engine, tenant.id)
        tesouraria = await _usuario_com(admin_engine, tenant.id, ["pagamento_pagar"])

        resp = await _post(admin_engine, tenant.id, tenant.slug, tesouraria,
                           f"/api/v2/pagamentos/parcelas/{p}/pagar",
                           {"forma_pagamento": "BOLETO", "data_pagamento": "2026-10-09"})
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert (corpo["status"], corpo["forma_pagamento"], corpo["data_pagamento"]) == (
            "PAGA", "BOLETO", "2026-10-09")

        async with _sm(admin_engine)() as s:
            atual = await deb.obter_debito(s, tenant_id=tenant.id, debito_id=d.id)
            trilha = (await s.execute(text(
                "SELECT id_usuario FROM aprimora_py.audit_log WHERE tenant_id=:t "
                "AND acao='pagamento.parcela_paga' AND id_entidade=:p"),
                {"t": tenant.id, "p": p})).scalars().all()
        assert atual.situacao_pagamento == est.PAGA
        assert trilha == [tesouraria]
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_quem_so_autoriza_nao_paga(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        _d, p = await _liberado(admin_engine, tenant.id)
        autoridade = await _usuario_com(admin_engine, tenant.id, ["pagamento_autorizar"])

        resp = await _post(admin_engine, tenant.id, tenant.slug, autoridade,
                           f"/api/v2/pagamentos/parcelas/{p}/pagar", {"forma_pagamento": "PIX"})
        assert resp.status_code == 403, resp.text

        async with _sm(admin_engine)() as s:
            status = (await s.execute(select(Parcela.status).where(Parcela.id == p))).scalar_one()
        assert status == "LIBERADA"
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_em_processamento_so_a_partir_de_programada(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        d, _p = await _liberado(admin_engine, tenant.id)
        tesouraria = await _usuario_com(admin_engine, tenant.id, ["pagamento_pagar"])
        caminho = f"/api/v2/pagamentos/debitos/{d.id}/em-processamento"

        resp = await _post(admin_engine, tenant.id, tenant.slug, tesouraria, caminho, {})
        assert resp.status_code == 200, resp.text
        assert resp.json()["situacao_pagamento"] == est.EM_PROCESSAMENTO

        # Já saiu de "programada": a segunda chamada é transição ilegal.
        resp = await _post(admin_engine, tenant.id, tenant.slug, tesouraria, caminho, {})
        assert resp.status_code == 409, resp.text
    finally:
        await _cleanup(admin_engine, tenant.id)
