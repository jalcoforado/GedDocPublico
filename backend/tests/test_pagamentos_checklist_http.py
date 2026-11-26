"""Checklist documental do débito pela porta HTTP, com usuário COMUM.

A tela "Conferência de documentos" do detalhe do débito depende destes dois
endpoints, e até ela existir ninguém os chamava: só havia teste de service, que
não passa pelo `Depends` de permissão nem pelo bypass de super-usuário.

O que se trava aqui: quem valida marca; quem só solicita lê e NÃO marca; e a
marcação feita por HTTP é a que destrava `validar`.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.schemas.pagamentos import ChecklistItemCreate
from app.services import pagamentos_checklist as chk
from tests.test_pagamentos_f4_retencao import (
    _cleanup, _get, _post, _provisionar, _setup_debito, _sm, _usuario_com,
)


async def _cleanup_checklist(engine, tenant_id: int) -> None:
    """As marcas referenciam débito e item: saem antes do `_cleanup` geral."""
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.debito_checklist_marca WHERE tenant_id=:t",
            "DELETE FROM pagamentos.checklist_item WHERE tenant_id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()
    await _cleanup(engine, tenant_id)


async def _item_obrigatorio(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        item = await chk.criar_item(s, tenant_id=tenant_id, payload=ChecklistItemCreate(
            descricao="Nota fiscal atestada", obrigatorio=True))
        return item.id


@pytest.mark.asyncio
async def test_http_validador_comum_marca_e_o_checklist_deixa_de_estar_pendente(admin_engine):
    tenant, solicitante_id = await _provisionar(admin_engine)
    try:
        debito, _conta = await _setup_debito(admin_engine, tenant.id, solicitante_id)
        item_id = await _item_obrigatorio(admin_engine, tenant.id)
        validador = await _usuario_com(admin_engine, tenant.id, ["pagamento_validar"])
        caminho = f"/api/v2/pagamentos/debitos/{debito.id}/checklist"

        resp = await _get(admin_engine, tenant.id, tenant.slug, validador, caminho)
        assert resp.status_code == 200, resp.text
        assert [(i["id_checklist_item"], i["obrigatorio"], i["marcado"])
                for i in resp.json()] == [(item_id, True, False)]

        resp = await _post(admin_engine, tenant.id, tenant.slug, validador, caminho,
                           {"id_checklist_item": item_id, "marcado": True})
        assert resp.status_code == 200, resp.text
        # O POST devolve o checklist inteiro já no estado novo — a tela usa essa
        # resposta em vez de refazer o GET.
        assert [(i["id_checklist_item"], i["marcado"]) for i in resp.json()] == [(item_id, True)]

        async with _sm(admin_engine)() as s:
            assert await chk.checklist_pendente(s, tenant_id=tenant.id, debito_id=debito.id) == []
    finally:
        await _cleanup_checklist(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_quem_so_solicita_le_mas_nao_marca(admin_engine):
    tenant, solicitante_id = await _provisionar(admin_engine)
    try:
        debito, _conta = await _setup_debito(admin_engine, tenant.id, solicitante_id)
        item_id = await _item_obrigatorio(admin_engine, tenant.id)
        solicitante = await _usuario_com(admin_engine, tenant.id, ["pagamento_solicitar"])
        caminho = f"/api/v2/pagamentos/debitos/{debito.id}/checklist"

        resp = await _get(admin_engine, tenant.id, tenant.slug, solicitante, caminho)
        assert resp.status_code == 200, resp.text

        resp = await _post(admin_engine, tenant.id, tenant.slug, solicitante, caminho,
                           {"id_checklist_item": item_id, "marcado": True})
        assert resp.status_code == 403, resp.text

        async with _sm(admin_engine)() as s:
            assert await chk.checklist_pendente(
                s, tenant_id=tenant.id, debito_id=debito.id) == ["Nota fiscal atestada"]
    finally:
        await _cleanup_checklist(admin_engine, tenant.id)
