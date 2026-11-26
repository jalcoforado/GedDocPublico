"""Os dois avisos que faltaram no rito (ver `test_pagamentos_notificacoes_rito.py`):

- liberar parcelas avisa a tesouraria — UMA vez por liberação, não por parcela;
- o pagamento confirmado por retorno de lote avisa o solicitante, como o
  pagamento avulso já avisava.

Pela porta HTTP, que é onde o aviso é disparado.
"""
from __future__ import annotations


import pytest
from sqlalchemy import select, text

from app.models import Parcela
from app.schemas.pagamentos import AlcadaCreate, GrupoAutorizacaoIn
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_cadastros as cad
from tests.test_pagamentos_f3_elegibilidade import _base, _debito_ate_autoridade
from tests.test_pagamentos_f4_lote import (
    _cleanup, _lote_ate_enviado, _provisionar, _sm,
)
from tests.test_pagamentos_f4_retencao import _post, _usuario_com


async def _avisos(engine, tenant_id: int) -> list[tuple[int, str, str, str]]:
    async with _sm(engine)() as s:
        rows = (await s.execute(text(
            "SELECT id_usuario, tipo, titulo, link_url FROM aprimora_py.notificacao "
            "WHERE tenant_id=:t AND tipo LIKE 'pagamento_%' ORDER BY id"), {"t": tenant_id})).all()
    return [tuple(r) for r in rows]


@pytest.mark.asyncio
async def test_http_liberar_avisa_a_tesouraria_uma_vez_por_liberacao(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta, unidade = await _base(admin_engine, tenant.id)
        d, _ = await _debito_ate_autoridade(admin_engine, tenant.id, forn, nat, fonte, conta, unidade)
        autoridade = await _usuario_com(admin_engine, tenant.id, ["pagamento_autorizar"])
        tesoureiro = await _usuario_com(admin_engine, tenant.id, ["pagamento_pagar"])
        async with _sm(admin_engine)() as s:
            await cad.criar_alcada(s, tenant_id=tenant.id, payload=AlcadaCreate(
                id_usuario=autoridade, id_natureza=None, valor_maximo="999999.00"))
        async with _sm(admin_engine)() as s:
            await aut.autorizar_lote(s, tenant_id=tenant.id, usuario_id=autoridade, grupos=[
                GrupoAutorizacaoIn(id_fonte=fonte.id, id_conta_pagadora=conta.id,
                                   debito_ids=[d.id])])
        async with _sm(admin_engine)() as s:
            parcelas = (await s.execute(
                select(Parcela.id).where(Parcela.id_debito == d.id))).scalars().all()

        resp = await _post(admin_engine, tenant.id, tenant.slug, autoridade,
                           "/api/v2/pagamentos/parcelas/liberar",
                           {"parcela_ids": list(parcelas)})
        assert resp.status_code == 200, resp.text

        avisos = [a for a in await _avisos(admin_engine, tenant.id) if a[0] == tesoureiro]
        assert avisos == [(tesoureiro, "pagamento_pendente",
                           "Parcelas liberadas para pagamento", "/m/pagamentos/tesouraria")]
        # Quem liberou não é avisado da própria liberação.
        assert not [a for a in await _avisos(admin_engine, tenant.id)
                    if a[0] == autoridade and a[1] == "pagamento_pendente"]
    finally:
        async with _sm(admin_engine)() as s:
            await s.execute(text("DELETE FROM pagamentos.alcada WHERE tenant_id=:t"),
                            {"t": tenant.id})
            await s.commit()
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_retorno_de_lote_pago_avisa_o_solicitante_e_falha_nao(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        lote, d1, p1, _conta = await _lote_ate_enviado(admin_engine, tenant.id)
        tesoureiro = await _usuario_com(admin_engine, tenant.id, ["pagamento_pagar"])
        caminho = f"/api/v2/pagamentos/lotes/{lote.id}/retorno"

        # Falhou: nada foi pago, ninguém é avisado de pagamento.
        resp = await _post(admin_engine, tenant.id, tenant.slug, tesoureiro, caminho, {
            "retornos": [{"parcela_id": p1, "resultado": "FALHOU",
                          "motivo_falha": "conta encerrada"}]})
        assert resp.status_code == 200, resp.text
        assert not [a for a in await _avisos(admin_engine, tenant.id)
                    if a[2] == "Pagamento realizado"]
    finally:
        await _cleanup(admin_engine, tenant.id)

    tenant, _sol = await _provisionar(admin_engine)
    try:
        lote, d1, p1, _conta = await _lote_ate_enviado(admin_engine, tenant.id)
        tesoureiro = await _usuario_com(admin_engine, tenant.id, ["pagamento_pagar"])
        resp = await _post(admin_engine, tenant.id, tenant.slug, tesoureiro,
                           f"/api/v2/pagamentos/lotes/{lote.id}/retorno", {
                               "retornos": [{"parcela_id": p1, "resultado": "PAGA",
                                             "forma_pagamento": "PIX"}]})
        assert resp.status_code == 200, resp.text
        pagos = [a for a in await _avisos(admin_engine, tenant.id)
                 if a[2] == "Pagamento realizado"]
        assert pagos == [(d1.id_usuario_solicitante, "pagamento_andamento", "Pagamento realizado",
                          f"/m/pagamentos/solicitacoes/{d1.id}")]
    finally:
        await _cleanup(admin_engine, tenant.id)
