"""Notificações do rito de pagamentos (`services/pagamentos_notificacoes.py`).

O rito andava em silêncio. O que se trava aqui:

- cada etapa avisa quem passa a ter a vez — e só quem tem a transação da etapa
  por um grupo NÃO super-usuário;
- quem praticou o ato e o próprio solicitante não são avisados de "chegou para
  você decidir" (segregação);
- o solicitante é avisado quando a solicitação volta, é autorizada ou é paga;
- o link nasce com `/m/pagamentos/…`;
- o aviso passa pela porta HTTP — é ali que ele é disparado, não no service.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.schemas.pagamentos import AlcadaCreate
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as svc
from app.services import pagamentos_estados as est
from app.services import pagamentos_notificacoes as notif
from tests.test_pagamentos_f3_elegibilidade import (
    _base, _debito_ate_autoridade, _novo_usuario, _payload_debito, _provisionar, _sm,
)
from tests.test_pagamentos_f4_retencao import _cleanup, _post, _usuario_com


async def _limpar(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        await s.execute(text("DELETE FROM pagamentos.alcada WHERE tenant_id=:t"), {"t": tenant_id})
        await s.commit()
    await _cleanup(engine, tenant_id)


async def _avisos(engine, tenant_id: int) -> list[tuple[int, str, str, str, str]]:
    """(id_usuario, tipo, canal, titulo, link_url), na ordem de criação."""
    async with _sm(engine)() as s:
        rows = (await s.execute(text(
            "SELECT id_usuario, tipo, canal, titulo, link_url FROM aprimora_py.notificacao "
            "WHERE tenant_id=:t AND tipo LIKE 'pagamento_%' ORDER BY id"), {"t": tenant_id})).all()
    return [tuple(r) for r in rows]


@pytest.mark.asyncio
async def test_usuarios_com_transacao_ignora_super_usuario_e_outra_transacao(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        gestor = await _usuario_com(admin_engine, t.id, ["pagamento_gerir"])
        _validador = await _usuario_com(admin_engine, t.id, ["pagamento_validar"])
        async with _sm(admin_engine)() as s:
            quem = await notif.usuarios_com_transacao(s, tenant_id=t.id, codigo="pagamento_gerir")
            # O admin do provisionamento é super-usuário: tem toda permissão,
            # e justamente por isso não entra.
            admin = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t ORDER BY id LIMIT 1"),
                {"t": t.id})).scalar_one()
        assert quem == {gestor}
        assert admin not in quem
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_enviar_ao_gestor_avisa_quem_decide_e_nao_o_solicitante(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta, unidade = await _base(admin_engine, t.id)
        # O solicitante TAMBÉM tem `pagamento_gerir`: mesmo assim não é avisado
        # da própria solicitação.
        solicitante = await _usuario_com(
            admin_engine, t.id, ["pagamento_solicitar", "pagamento_gerir"])
        gestor = await _usuario_com(admin_engine, t.id, ["pagamento_gerir"])
        async with _sm(admin_engine)() as s:
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=solicitante,
                                       payload=_payload_debito(forn, nat, fonte, conta, unidade))
            await svc.confirmar_liquidacao(s, tenant_id=t.id, debito_id=d.id,
                                           usuario_id=solicitante)
            d = await svc.obter_debito(s, tenant_id=t.id, debito_id=d.id)

        resp = await _post(admin_engine, t.id, t.slug, solicitante,
                           f"/api/v2/pagamentos/debitos/{d.id}/enviar-gestor",
                           {"lock_version": d.lock_version})
        assert resp.status_code == 200, resp.text
        assert resp.json()["situacao_tramitacao"] == est.AGUARDANDO_GESTOR

        assert await _avisos(admin_engine, t.id) == [(
            gestor, "pagamento_pendente", "in_app", "Solicitação de pagamento na sua fila",
            f"/m/pagamentos/solicitacoes/{d.id}")]
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_ajuste_pedido_avisa_o_solicitante(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta, unidade = await _base(admin_engine, t.id)
        solicitante = await _novo_usuario(admin_engine, t.id, "solaviso")
        gestor = await _usuario_com(admin_engine, t.id, ["pagamento_gerir"])
        async with _sm(admin_engine)() as s:
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=solicitante,
                                       payload=_payload_debito(forn, nat, fonte, conta, unidade))
        async with _sm(admin_engine)() as s:
            d = await svc.enviar_para_gestor(s, tenant_id=t.id, debito_id=d.id,
                                             usuario_id=solicitante, lock_version=d.lock_version)

        resp = await _post(
            admin_engine, t.id, t.slug, gestor,
            f"/api/v2/pagamentos/debitos/{d.id}/solicitar-ajuste",
            {"lock_version": d.lock_version, "etapa": "GESTOR", "motivo": "NF ilegível",
             "descricao": "Reenviar a digitalização.",
             "transacao_responsavel": "pagamento_solicitar", "tipo": "NAO_MATERIAL"})
        assert resp.status_code == 200, resp.text

        avisos = await _avisos(admin_engine, t.id)
        assert [(a[0], a[1], a[3]) for a in avisos] == [
            (solicitante, "pagamento_devolvido", "Ajuste pedido pelo gestor")]
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_aprovar_avisa_o_solicitante_que_foi_autorizada(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta, unidade = await _base(admin_engine, t.id)
        d, _ = await _debito_ate_autoridade(admin_engine, t.id, forn, nat, fonte, conta, unidade)
        autoridade = await _usuario_com(admin_engine, t.id, ["pagamento_autorizar"])
        async with _sm(admin_engine)() as s:
            await cad.criar_alcada(s, tenant_id=t.id, payload=AlcadaCreate(
                id_usuario=autoridade, id_natureza=None, valor_maximo="999999.00"))

        resp = await _post(
            admin_engine, t.id, t.slug, autoridade,
            f"/api/v2/pagamentos/debitos/{d.id}/autoridade-aprovar",
            {"lock_version": d.lock_version, "id_conta_pagadora": conta.id})
        assert resp.status_code == 200, resp.text

        avisos = await _avisos(admin_engine, t.id)
        assert [(a[0], a[1], a[3]) for a in avisos] == [
            (d.id_usuario_solicitante, "pagamento_andamento", "Pagamento autorizado")]
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_preferencia_desligada_silencia_o_aviso(admin_engine):
    from app.services.notificacoes import set_preferencia_evento

    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta, unidade = await _base(admin_engine, t.id)
        solicitante = await _novo_usuario(admin_engine, t.id, "solpref")
        gestor = await _usuario_com(admin_engine, t.id, ["pagamento_gerir"])
        async with _sm(admin_engine)() as s:
            await set_preferencia_evento(
                s, tenant_id=t.id, id_usuario=gestor, evento="pagamento_pendente", in_app=False)
        async with _sm(admin_engine)() as s:
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=solicitante,
                                       payload=_payload_debito(forn, nat, fonte, conta, unidade))
        async with _sm(admin_engine)() as s:
            d = await svc.enviar_para_gestor(s, tenant_id=t.id, debito_id=d.id,
                                             usuario_id=solicitante, lock_version=d.lock_version)
        async with _sm(admin_engine)() as s:
            d = await svc.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            n = await notif.notificar_transicao(s, tenant_id=t.id, debito=d, ator_id=solicitante)
        assert n == 0
        assert await _avisos(admin_engine, t.id) == []
    finally:
        async with _sm(admin_engine)() as s:
            await s.execute(text(
                "DELETE FROM aprimora_py.notificacao_preferencia_evento WHERE tenant_id=:t"),
                {"t": t.id})
            await s.commit()
        await _limpar(admin_engine, t.id)
