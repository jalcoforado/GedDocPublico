"""Edição do débito pela porta HTTP, com usuário COMUM.

`PUT /pagamentos/debitos/{id}` não tinha chamador até a tela de edição existir,
e só era exercitado por teste de service. A tela depende de três coisas daqui:
a categoria ser gravada E devolvida (é ela que posiciona na fila cronológica o
débito sem contrato), a edição valer só em rascunho/ajuste, e o gate pedir a
ação `atualizar` — que o bypass de super-usuário nunca avalia.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.auth.deps import get_current_user
from app.main import app
from app.models import Usuario
from app.services import pagamentos_debitos as svc
from tests.conftest import arreio_tenant_http
from tests.test_pagamentos_f3_elegibilidade import (
    _base, _novo_usuario, _payload_debito, _provisionar, _sm,
)
from tests.test_pagamentos_f4_retencao import _cleanup, _usuario_com


async def _put(engine, tenant_id, slug, usuario_id, caminho, body):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(
                select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, slug)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await c.put(caminho, json=body)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


async def _rascunho(engine):
    t = await _provisionar(engine)
    forn, nat, fonte, conta, unidade = await _base(engine, t.id)
    autor = await _novo_usuario(engine, t.id, f"sol{uuid.uuid4().hex[:6]}")
    async with _sm(engine)() as s:
        d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=autor,
                                   payload=_payload_debito(forn, nat, fonte, conta, unidade))
    return t, d, autor


async def _somente_leitura_de_solicitar(engine, tenant_id: int) -> int:
    """Usuário com a transação `pagamento_solicitar`, mas SEM a ação `atualizar`."""
    uid = await _usuario_com(engine, tenant_id, ["pagamento_solicitar"])
    async with _sm(engine)() as s:
        await s.execute(text(
            "UPDATE utils.grupo_transacao SET atualizar = false WHERE tenant_id = :t "
            "AND id_grupo IN (SELECT id_grupo FROM utils.usuario_grupo WHERE id_usuario = :u)"),
            {"t": tenant_id, "u": uid})
        await s.commit()
    return uid


@pytest.mark.asyncio
async def test_http_usuario_comum_edita_rascunho_e_a_categoria_volta_na_resposta(admin_engine):
    t, d, _autor = await _rascunho(admin_engine)
    try:
        editor = await _usuario_com(admin_engine, t.id, ["pagamento_solicitar"])
        resp = await _put(admin_engine, t.id, t.slug, editor,
                          f"/api/v2/pagamentos/debitos/{d.id}",
                          {"descricao": "Descrição corrigida", "categoria": "OBRAS"})
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert corpo["descricao"] == "Descrição corrigida"
        assert corpo["categoria"] == "OBRAS"

        async with _sm(admin_engine)() as s:
            atual = await svc.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert atual.categoria == "OBRAS"
        assert atual.situacao_tramitacao == "RASCUNHO"
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_editar_fora_de_rascunho_ou_ajuste_e_409(admin_engine):
    t, d, autor = await _rascunho(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            d = await svc.enviar_para_gestor(s, tenant_id=t.id, debito_id=d.id,
                                             usuario_id=autor, lock_version=d.lock_version)
        editor = await _usuario_com(admin_engine, t.id, ["pagamento_solicitar"])
        resp = await _put(admin_engine, t.id, t.slug, editor,
                          f"/api/v2/pagamentos/debitos/{d.id}", {"descricao": "Tarde demais"})
        assert resp.status_code == 409, resp.text

        async with _sm(admin_engine)() as s:
            atual = await svc.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert atual.descricao != "Tarde demais"
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_sem_a_acao_atualizar_e_403(admin_engine):
    t, d, _autor = await _rascunho(admin_engine)
    try:
        leitor = await _somente_leitura_de_solicitar(admin_engine, t.id)
        resp = await _put(admin_engine, t.id, t.slug, leitor,
                          f"/api/v2/pagamentos/debitos/{d.id}", {"descricao": "Sem permissão"})
        assert resp.status_code == 403, resp.text

        async with _sm(admin_engine)() as s:
            atual = await svc.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert atual.descricao != "Sem permissão"
    finally:
        await _cleanup(admin_engine, t.id)
