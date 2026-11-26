"""`GET /pagamentos/debitos/exportar.csv` respeita o filtro de etapa da tela.

A exportação aceitava todos os filtros de `GET /pagamentos/debitos` menos
`situacao_tramitacao`, que é justamente o seletor da tela de Solicitações: com
a lista filtrada por "Aguardando gestor", o arquivo traria a base inteira.

Pela porta HTTP e com usuário COMUM (auditor): é quem usa a exportação, e o
bypass de super-usuário não exercita o gate de leitura.
"""
from __future__ import annotations

import uuid

import pytest

from app.services import pagamentos_debitos as svc
from tests.test_pagamentos_f3_elegibilidade import (
    _base, _novo_usuario, _payload_debito, _provisionar, _sm,
)
from tests.test_pagamentos_f4_retencao import _cleanup, _get, _usuario_com


def _ids(csv: str) -> list[int]:
    """Primeira coluna (id) das linhas de dados; a primeira linha é o cabeçalho."""
    linhas = [ln for ln in csv.lstrip("﻿").splitlines() if ln.strip()]
    return [int(ln.split(";")[0]) for ln in linhas[1:]]


@pytest.mark.asyncio
async def test_http_export_filtra_por_etapa_e_sem_filtro_traz_tudo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta, unidade = await _base(admin_engine, t.id)
        autor = await _novo_usuario(admin_engine, t.id, f"sol{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            rascunho = await svc.criar_debito(
                s, tenant_id=t.id, usuario_id=autor,
                payload=_payload_debito(forn, nat, fonte, conta, unidade))
        async with _sm(admin_engine)() as s:
            enviado = await svc.criar_debito(
                s, tenant_id=t.id, usuario_id=autor,
                payload=_payload_debito(forn, nat, fonte, conta, unidade))
        async with _sm(admin_engine)() as s:
            enviado = await svc.enviar_para_gestor(
                s, tenant_id=t.id, debito_id=enviado.id, usuario_id=autor,
                lock_version=enviado.lock_version)

        auditor = await _usuario_com(admin_engine, t.id, ["pagamento_auditar"])
        base = "/api/v2/pagamentos/debitos/exportar.csv"

        resp = await _get(admin_engine, t.id, t.slug, auditor,
                          f"{base}?situacao_tramitacao=AGUARDANDO_GESTOR")
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"].startswith("text/csv")
        assert _ids(resp.text) == [enviado.id]

        resp = await _get(admin_engine, t.id, t.slug, auditor, base)
        assert resp.status_code == 200, resp.text
        assert sorted(_ids(resp.text)) == sorted([rascunho.id, enviado.id])
    finally:
        await _cleanup(admin_engine, t.id)
