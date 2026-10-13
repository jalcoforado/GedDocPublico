"""A trilha guarda o IP e o `request_id` também quando o ato é auditado de
dentro de um service.

Os atos financeiros de pagamentos chamam `audit.log` no service, na mesma
transação do ato, e o service não recebe o `Request`. Até 2026-10-13 essas
linhas nasciam com `ip` e `request_id` nulos: sabia-se quem pagou, não de
onde. O `RequestLoggingMiddleware` passa a deixar os dois em context vars e o
`audit.log` os lê quando não recebe `request`.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.auth.deps import get_current_user
from app.main import app
from app.models import Usuario
from app.schemas.pagamentos import NaturezaCreate
from app.services import audit
from app.services import pagamentos_cadastros as cad
from tests.fixtures.pagamentos import id_unidade_padrao
from tests.test_pagamentos_f4_lote import (
    _cleanup, _debito_liberado, _fonte_conta, _fornecedor2, _provisionar, _sm,
)
from tests.conftest import arreio_tenant_http
from tests.test_pagamentos_f4_retencao import _usuario_com


async def _parcela_liberada(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
    async with _sm(engine)() as s:
        unidade_id = await id_unidade_padrao(s, tenant_id)
    fonte, conta = await _fonte_conta(engine, tenant_id)
    forn = await _fornecedor2(engine, tenant_id, nome="Forn IP LTDA")
    _d, p = await _debito_liberado(engine, tenant_id, forn=forn, nat=nat, fonte=fonte,
                                   conta=conta, unidade_id=unidade_id)
    return p


async def _pagar(engine, tenant_id, slug, usuario_id, parcela_id, headers):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(
                select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, slug)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await c.post(f"/api/v2/pagamentos/parcelas/{parcela_id}/pagar",
                                json={"forma_pagamento": "PIX"}, headers=headers)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


async def _linha(engine, tenant_id: int, parcela_id: int):
    async with _sm(engine)() as s:
        return (await s.execute(text(
            "SELECT ip, request_id FROM aprimora_py.audit_log WHERE tenant_id=:t "
            "AND acao='pagamento.parcela_paga' AND id_entidade=:p"),
            {"t": tenant_id, "p": parcela_id})).one()


@pytest.mark.asyncio
async def test_http_ato_auditado_no_service_guarda_ip_real_e_request_id(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        p = await _parcela_liberada(admin_engine, tenant.id)
        tesouraria = await _usuario_com(admin_engine, tenant.id, ["pagamento_pagar"])

        # Como chega atrás do nginx: X-Real-IP sobrescrito por ele, e um
        # X-Forwarded-For cujo PRIMEIRO item foi o cliente que escreveu.
        resp = await _pagar(admin_engine, tenant.id, tenant.slug, tesouraria, p, {
            "x-real-ip": "203.0.113.7", "x-forwarded-for": "198.51.100.99, 203.0.113.7",
            "x-request-id": "req-auditoria-ip"})
        assert resp.status_code == 200, resp.text

        ip, request_id = await _linha(admin_engine, tenant.id, p)
        # O IP forjado no X-Forwarded-For não entra na trilha.
        assert ip == "203.0.113.7"
        assert request_id == "req-auditoria-ip"
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_sem_x_real_ip_vale_o_forwarded_e_depois_a_conexao(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        p = await _parcela_liberada(admin_engine, tenant.id)
        tesouraria = await _usuario_com(admin_engine, tenant.id, ["pagamento_pagar"])

        resp = await _pagar(admin_engine, tenant.id, tenant.slug, tesouraria, p, {})
        assert resp.status_code == 200, resp.text

        ip, request_id = await _linha(admin_engine, tenant.id, p)
        assert ip == "127.0.0.1"
        assert request_id

        p2 = await _parcela_liberada(admin_engine, tenant.id)
        resp = await _pagar(admin_engine, tenant.id, tenant.slug, tesouraria, p2, {
            "x-forwarded-for": "203.0.113.8, 10.0.0.2"})
        assert resp.status_code == 200, resp.text
        assert (await _linha(admin_engine, tenant.id, p2))[0] == "203.0.113.8"
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_fora_de_um_request_a_linha_nasce_sem_ip(admin_engine):
    """Seed, task e CLI auditam sem request nenhum: IP nulo é a resposta
    certa, e não pode sobrar o IP de um request anterior."""
    tenant, solicitante = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            s.info["tenant_id"] = tenant.id
            log_id = await audit.log(
                s, tenant_id=tenant.id, id_usuario=solicitante,
                acao="pagamento.parcela_paga", entidade="parcela", id_entidade=None)
            await s.commit()
        async with _sm(admin_engine)() as s:
            ip, request_id = (await s.execute(text(
                "SELECT ip, request_id FROM aprimora_py.audit_log WHERE id=:i"),
                {"i": log_id})).one()
        assert (ip, request_id) == (None, None)
    finally:
        await _cleanup(admin_engine, tenant.id)
