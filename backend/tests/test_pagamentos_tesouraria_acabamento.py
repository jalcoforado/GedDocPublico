"""Acabamento da tesouraria: forma de pagamento do lote e nomes no lugar de ids.

- O retorno de lote gravava `forma_pagamento = "TED"` para toda parcela paga,
  inclusive as pagas por PIX ou boleto. Passa a aceitar a forma informada;
  ausente, continua "TED" (retorno antigo não muda de sentido).
- `GET /pagamentos/lotes/elegiveis` devolvia só o id do débito; quem monta o
  lote via "Débito #12" e precisava abrir cada um para saber de quem era.
- A lista de anexos do débito devolvia só `id_usuario`.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models import AnexoDebito, Parcela
from app.schemas.pagamentos import NaturezaCreate, RetornoParcelaIn
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_lotes as lot
from tests.fixtures.pagamentos import id_unidade_padrao
from tests.test_pagamentos_f4_lote import (
    _cleanup, _criar_usuario, _debito_liberado, _fonte_conta, _fornecedor2,
    _lote_ate_enviado, _provisionar, _sm,
)
from tests.test_pagamentos_f4_retencao import _get, _usuario_com


async def _forma_gravada(engine, parcela_id: int) -> str | None:
    async with _sm(engine)() as s:
        return (await s.execute(
            select(Parcela.forma_pagamento).where(Parcela.id == parcela_id))).scalar_one()


@pytest.mark.asyncio
async def test_retorno_grava_a_forma_de_pagamento_informada(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        lote, d1, p1, _conta = await _lote_ate_enviado(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            await lot.processar_retorno(
                s, tenant_id=tenant.id, lote_id=lote.id, usuario_id=d1.id_usuario_solicitante,
                retornos=[RetornoParcelaIn(parcela_id=p1, resultado="PAGA", forma_pagamento="PIX")])
        assert await _forma_gravada(admin_engine, p1) == "PIX"
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_retorno_sem_forma_informada_continua_ted(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        lote, d1, p1, _conta = await _lote_ate_enviado(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            await lot.processar_retorno(
                s, tenant_id=tenant.id, lote_id=lote.id, usuario_id=d1.id_usuario_solicitante,
                retornos=[RetornoParcelaIn(parcela_id=p1, resultado="PAGA")])
        assert await _forma_gravada(admin_engine, p1) == "TED"
    finally:
        await _cleanup(admin_engine, tenant.id)


async def _debito_liberado_fora_de_lote(engine, tenant_id: int, *, nome_forn: str):
    async with _sm(engine)() as s:
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
    async with _sm(engine)() as s:
        unidade_id = await id_unidade_padrao(s, tenant_id)
    fonte, conta = await _fonte_conta(engine, tenant_id)
    forn = await _fornecedor2(engine, tenant_id, nome=nome_forn)
    d, p = await _debito_liberado(engine, tenant_id, forn=forn, nat=nat, fonte=fonte,
                                  conta=conta, unidade_id=unidade_id)
    return d, p, conta


@pytest.mark.asyncio
async def test_http_elegiveis_dizem_de_quem_e_a_parcela(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        d, p, conta = await _debito_liberado_fora_de_lote(
            admin_engine, tenant.id, nome_forn="Papelaria Elegível LTDA")
        tesouraria = await _usuario_com(admin_engine, tenant.id, ["pagamento_pagar"])

        resp = await _get(admin_engine, tenant.id, tenant.slug, tesouraria,
                          f"/api/v2/pagamentos/lotes/elegiveis?id_conta_pagadora={conta.id}")
        assert resp.status_code == 200, resp.text
        itens = resp.json()
        assert [i["id"] for i in itens] == [p]
        assert itens[0]["nome_fornecedor"] == "Papelaria Elegível LTDA"
        assert itens[0]["descricao_debito"] == d.descricao
        # O contrato anterior (ParcelaOut) continua inteiro.
        assert itens[0]["id_debito"] == d.id and itens[0]["status"] == "LIBERADA"
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_anexos_do_debito_trazem_o_nome_de_quem_anexou(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        d, _p, _conta = await _debito_liberado_fora_de_lote(
            admin_engine, tenant.id, nome_forn="Forn Anexo LTDA")
        quem = await _criar_usuario(admin_engine, tenant.id, "Rita Anexadora")
        async with _sm(admin_engine)() as s:
            # Vínculo sem arquivo físico: o endpoint tolera anexo ausente
            # (nome/tamanho nulos) e é o nome do USUÁRIO que se confere aqui.
            from app.models import Anexo
            anexo = Anexo(tenant_id=tenant.id, e_doc=f"teste-{uuid.uuid4().hex[:8]}.pdf",
                          excluido=False)
            s.add(anexo); await s.flush()
            s.add(AnexoDebito(tenant_id=tenant.id, id_debito=d.id, id_anexo=anexo.id,
                              versao_debito=1, id_usuario=quem, criado_em=datetime.utcnow()))
            await s.commit()

        leitor = await _usuario_com(admin_engine, tenant.id, ["pagamento_auditar"])
        resp = await _get(admin_engine, tenant.id, tenant.slug, leitor,
                          f"/api/v2/pagamentos/debitos/{d.id}/anexos")
        assert resp.status_code == 200, resp.text
        assert [a["nome_usuario"] for a in resp.json()] == ["Rita Anexadora"]
    finally:
        await _cleanup(admin_engine, tenant.id)
