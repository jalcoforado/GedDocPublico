"""`GET /pagamentos/auditoria` — a trilha do módulo para quem audita pagamentos.

O que se trava:

- só aparecem atos de pagamentos, mesmo havendo outras linhas no `audit_log`
  do mesmo tenant, e mesmo que o cliente peça uma ação de fora;
- só o tenant da sessão;
- quem tem `pagamento_auditar` lê; quem só paga, não;
- toda ação que o módulo grava cai num dos `PREFIXOS` — senão ela existe no
  banco e some da tela, em silêncio.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import text

from app.routers.pagamentos_auditoria import PREFIXOS
from tests.test_pagamentos_f4_retencao import (
    _cleanup, _criar_usuario, _get, _provisionar, _sm, _usuario_com,
)

APP = Path(__file__).resolve().parents[1] / "app"


async def _grava(engine, tenant_id: int, usuario_id: int | None, acao: str) -> None:
    async with _sm(engine)() as s:
        await s.execute(text(
            "INSERT INTO aprimora_py.audit_log (tenant_id, id_usuario, acao, entidade, "
            "id_entidade, payload, criado_em) VALUES (:t, :u, :a, 'teste', 1, "
            "CAST(:p AS jsonb), NOW())"),
            {"t": tenant_id, "u": usuario_id, "a": acao, "p": '{"id_debito": 7}'})
        await s.commit()


@pytest.mark.asyncio
async def test_http_auditor_ve_so_atos_de_pagamentos_do_proprio_tenant(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    outro, _sol2 = await _provisionar(admin_engine)
    try:
        quem = await _criar_usuario(admin_engine, tenant.id, "Teresa Tesoureira")
        await _grava(admin_engine, tenant.id, quem, "pagamento.parcela_paga")
        await _grava(admin_engine, tenant.id, quem, "debito.versao_criada")
        await _grava(admin_engine, tenant.id, quem, "processo.aberto")        # outro módulo
        await _grava(admin_engine, outro.id, None, "pagamento.parcela_paga")   # outro tenant

        auditor = await _usuario_com(admin_engine, tenant.id, ["pagamento_auditar"])
        base = "/api/v2/pagamentos/auditoria"

        resp = await _get(admin_engine, tenant.id, tenant.slug, auditor, base)
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert corpo["total"] == 2
        assert sorted(i["acao"] for i in corpo["items"]) == [
            "debito.versao_criada", "pagamento.parcela_paga"]
        assert {i["nome_usuario"] for i in corpo["items"]} == {"Teresa Tesoureira"}

        resp = await _get(admin_engine, tenant.id, tenant.slug, auditor,
                          f"{base}?acao=pagamento.parcela_paga")
        assert [i["acao"] for i in resp.json()["items"]] == ["pagamento.parcela_paga"]

        # Pedir uma ação de fora do módulo não a traz.
        resp = await _get(admin_engine, tenant.id, tenant.slug, auditor,
                          f"{base}?acao=processo.aberto")
        assert resp.status_code == 200 and resp.json()["total"] == 0

        resp = await _get(admin_engine, tenant.id, tenant.slug, auditor,
                          f"{base}?id_usuario={auditor}")
        assert resp.json()["total"] == 0
    finally:
        await _cleanup(admin_engine, tenant.id)
        await _cleanup(admin_engine, outro.id)


@pytest.mark.asyncio
async def test_http_quem_so_paga_nao_le_a_trilha(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        tesoureiro = await _usuario_com(admin_engine, tenant.id, ["pagamento_pagar"])
        resp = await _get(admin_engine, tenant.id, tenant.slug, tesoureiro,
                          "/api/v2/pagamentos/auditoria")
        assert resp.status_code == 403, resp.text
    finally:
        await _cleanup(admin_engine, tenant.id)


def test_toda_acao_que_o_modulo_grava_cai_num_prefixo_da_consulta():
    """Varre routers e services de pagamentos atrás de `acao="…"` passado a
    `audit.log`. Ação com prefixo fora de `PREFIXOS` seria gravada e nunca
    apareceria na tela do auditor."""
    padrao = re.compile(r"""audit(?:_log|\.log)\(.*?acao\s*=\s*["']([^"']+)["']""", re.S)
    achadas: set[str] = set()
    for pasta in ("routers", "services"):
        for arq in (APP / pasta).glob("pagamentos_*.py"):
            achadas |= set(padrao.findall(arq.read_text(encoding="utf-8")))
    assert achadas, "a varredura não achou nenhuma ação — o padrão quebrou"
    fora = sorted(a for a in achadas if not a.startswith(PREFIXOS))
    assert fora == [], f"ações de pagamentos fora de PREFIXOS: {fora}"
