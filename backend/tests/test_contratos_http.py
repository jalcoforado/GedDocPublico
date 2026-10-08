"""Contratos G1 — a costura router↔service, por HTTP.

Teste de service não cobre esta classe de defeito: gate de permissão, ordem de
rotas e convivência com o cadastro de pagamentos moram no router, que é onde o
`Depends` some.

Quase tudo aqui roda com USUÁRIO COMUM de propósito. O bypass de super-usuário
em `auth/perms.py` retorna antes do `getattr(item, action)`; uma bateria só de
SU passaria verde com o gate quebrado (foi assim que o transporte devolveu 500
para todo operador não-SU).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import contratos as svc
from app.services.contratos import ContratoError
from app.services.modulos import contratar
from app.services.sigilo import SigiloAcessoError
from tests.contratos_util import (
    como_usuario,
    criar_fornecedor_e_unidade,
    criar_usuario_comum,
    criar_usuario_su,
    numero,
    provisionar,
    sm,
)

BASE = "/api/v2/contratos"
MODULOS_SEM_CONTRATOS = ["protocolo", "pagamentos", "frota", "transporte", "administracao"]


def _cliente() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _limpar() -> None:
    app.dependency_overrides.clear()
    from app.database import engine as app_engine
    await app_engine.dispose()


def _corpo_contrato(id_fornecedor: int, id_unidade: int, **extra) -> dict:
    corpo = {
        "numero": numero(), "id_fornecedor": id_fornecedor, "id_unidade": id_unidade,
        "objeto": "Locação de imóvel para o CRAS", "vigencia_inicio": "2026-01-01",
        "vigencia_fim": "2026-12-31", "valor_total": "100000.00", "categoria": "LOCACOES",
        "data_celebracao": "2026-01-01", "tipo_objeto": "I", "natureza_duracao": "CONTINUO",
    }
    corpo.update(extra)
    return corpo


async def test_usuario_comum_percorre_o_ciclo_inteiro(admin_engine):
    """Cria, assina, adita e lê — com a transação `contrato` concedida via
    grupo. Prova, de uma vez, que cada `action` usada no router existe
    (`inserir`/`atualizar`), que `/resumo` e `/catalogos` não são engolidas por
    `/{contrato_id}`, e que a listagem devolve `Paginated`."""
    tenant = await provisionar(admin_engine)
    try:
        uid = await criar_usuario_comum(admin_engine, tenant.id, transacao="contrato")
        f, u = await criar_fornecedor_e_unidade(admin_engine, tenant.id)
        como_usuario(admin_engine, uid, tenant.id, tenant.slug)

        async with _cliente() as client:
            r = await client.get(f"{BASE}/resumo")
            assert r.status_code == 200, r.text
            assert r.json()["vigentes"] == 0

            r = await client.get(f"{BASE}/catalogos")
            assert r.status_code == 200, r.text
            assert len(r.json()["tipos_objeto"]) == 18
            assert [t["codigo"] for t in r.json()["tipos_aditivo"]] == [
                "AA", "AR", "AP", "PA", "PR", "RE"]

            r = await client.post(BASE, json=_corpo_contrato(f, u))
            assert r.status_code == 201, r.text
            contrato = r.json()
            assert contrato["situacao"] == "RASCUNHO"
            cid = contrato["id"]

            r = await client.post(f"{BASE}/{cid}/assinar")
            assert r.status_code == 200, r.text
            assert r.json()["situacao"] == "VIGENTE"

            r = await client.post(f"{BASE}/{cid}/aditivos", json={
                "numero": numero(), "tipo": "PA", "data_assinatura": "2026-06-01",
                "valor": "10000.00", "nova_vigencia_fim": "2027-06-30"})
            assert r.status_code == 201, r.text
            aid = r.json()["id"]
            r = await client.post(f"{BASE}/{cid}/aditivos/{aid}/assinar")
            assert r.status_code == 200, r.text

            r = await client.post(f"{BASE}/{cid}/apostilas", json={
                "tipo": "DOTACAO", "data": "2026-06-02",
                "descricao": "Empenho da dotação 0801.12.361"})
            assert r.status_code == 201, r.text

            r = await client.get(f"{BASE}/{cid}")
            assert r.status_code == 200, r.text
            detalhe = r.json()
            assert detalhe["valor_total"] == "100000.00"
            assert detalhe["calculo"]["valor_atualizado"] == "110000.00"
            assert detalhe["calculo"]["vigencia_fim_atual"] == "2027-06-30"
            assert len(detalhe["aditivos"]) == 1 and len(detalhe["apostilas"]) == 1

            r = await client.get(BASE, params={"page_size": 1})
            assert r.status_code == 200, r.text
            pagina = r.json()
            assert set(pagina) == {"items", "total", "page", "page_size"}
            assert pagina["total"] == 1
            assert pagina["items"][0]["valor_atualizado"] == "110000.00"

            # Edição de campo do ato em contrato vigente: 409, não 200 nem 500.
            r = await client.put(f"{BASE}/{cid}", json={"valor_total": "1.00"})
            assert r.status_code == 409, r.text
    finally:
        await _limpar()


async def test_usuario_sem_a_transacao_leva_403(admin_engine):
    tenant = await provisionar(admin_engine)
    try:
        uid = await criar_usuario_comum(admin_engine, tenant.id, transacao=None)
        como_usuario(admin_engine, uid, tenant.id, tenant.slug)
        async with _cliente() as client:
            for metodo, caminho in (
                ("GET", BASE), ("GET", f"{BASE}/resumo"), ("GET", f"{BASE}/catalogos"),
                ("GET", f"{BASE}/fornecedores"), ("GET", f"{BASE}/1"),
            ):
                r = await client.request(metodo, caminho)
                assert r.status_code == 403, (metodo, caminho, r.text)
    finally:
        await _limpar()


async def test_tenant_sem_o_modulo_barra_ate_o_super_usuario(admin_engine):
    """Transação de módulo não contratado é bloqueada ANTES do bypass de SU —
    é deliberado (CLAUDE.md, §Modularização). O router não tem
    `require_modulo`; este teste é o que prova que não precisa."""
    tenant = await provisionar(admin_engine)
    try:
        async with sm(admin_engine)() as s:
            await contratar(s, tenant.id, MODULOS_SEM_CONTRATOS)
            await s.commit()
        su = await criar_usuario_su(admin_engine, tenant.id)
        como_usuario(admin_engine, su, tenant.id, tenant.slug)
        async with _cliente() as client:
            r = await client.get(BASE)
            assert r.status_code == 403, r.text
            assert "não contratado" in r.json()["detail"]
            r = await client.get(f"{BASE}/resumo")
            assert r.status_code == 403, r.text
    finally:
        await _limpar()


async def test_fornecedor_pelo_modulo_nao_expoe_dado_bancario(admin_engine):
    """Quem tem só `contrato` escolhe e cria fornecedor (decisão Q2) — e não
    ganha, por tabela, acesso ao cadastro de pagamentos."""
    tenant = await provisionar(admin_engine)
    try:
        uid = await criar_usuario_comum(admin_engine, tenant.id, transacao="contrato")
        await criar_fornecedor_e_unidade(admin_engine, tenant.id)
        como_usuario(admin_engine, uid, tenant.id, tenant.slug)
        async with _cliente() as client:
            r = await client.get(f"{BASE}/fornecedores")
            assert r.status_code == 200, r.text
            assert len(r.json()) == 1
            assert set(r.json()[0]) == {
                "id", "tipo_pessoa", "cnpj_cpf", "nome", "situacao_cadastral"}

            r = await client.post(f"{BASE}/fornecedores", json={
                "tipo_pessoa": "JURIDICA", "cnpj_cpf": "11222333000181",
                "nome": "Construtora Exemplo LTDA"})
            assert r.status_code == 201, r.text

            r = await client.get("/api/v2/pagamentos/fornecedores")
            assert r.status_code == 403, r.text
    finally:
        await _limpar()


# ---------- convivência com o cadastro simples de pagamentos (spec §5.2) -------

def _corpo_contrato_pagamentos(id_fornecedor: int, id_unidade: int) -> dict:
    return {
        "numero": numero(), "id_fornecedor": id_fornecedor, "id_unidade": id_unidade,
        "objeto": "Contrato simples", "vigencia_inicio": "2026-01-01",
        "vigencia_fim": "2026-12-31", "valor_total": "5000.00", "categoria": "SERVICOS",
    }


async def test_com_o_modulo_a_escrita_por_pagamentos_e_recusada(admin_engine):
    tenant = await provisionar(admin_engine)
    try:
        su = await criar_usuario_su(admin_engine, tenant.id)
        f, u = await criar_fornecedor_e_unidade(admin_engine, tenant.id)
        como_usuario(admin_engine, su, tenant.id, tenant.slug)
        async with _cliente() as client:
            r = await client.post(
                "/api/v2/pagamentos/contratos", json=_corpo_contrato_pagamentos(f, u))
            assert r.status_code == 409, r.text
            assert "módulo Contratos" in r.json()["detail"]
            # A leitura segue: pagamentos precisa listar contrato para vincular débito.
            r = await client.get("/api/v2/pagamentos/contratos")
            assert r.status_code == 200, r.text
    finally:
        await _limpar()


async def test_sem_o_modulo_o_cadastro_de_pagamentos_segue_funcionando(admin_engine):
    """O controle do teste acima: sem ele, um 409 incondicional passaria verde
    e quebraria todo município que tem pagamentos e não tem contratos."""
    tenant = await provisionar(admin_engine)
    try:
        async with sm(admin_engine)() as s:
            await contratar(s, tenant.id, MODULOS_SEM_CONTRATOS)
            await s.commit()
        su = await criar_usuario_su(admin_engine, tenant.id)
        f, u = await criar_fornecedor_e_unidade(admin_engine, tenant.id)
        como_usuario(admin_engine, su, tenant.id, tenant.slug)
        async with _cliente() as client:
            r = await client.post(
                "/api/v2/pagamentos/contratos", json=_corpo_contrato_pagamentos(f, u))
            assert r.status_code == 201, r.text
            criado = r.json()
            r = await client.put(
                f"/api/v2/pagamentos/contratos/{criado['id']}", json={"valor_total": "6000.00"})
            assert r.status_code == 200, r.text
    finally:
        await _limpar()

    # Nasceu como o backfill da 0132 trata o legado: vigente, exercício pela vigência.
    async with sm(admin_engine)() as s:
        c = await svc.obter(s, tenant_id=tenant.id, contrato_id=criado["id"])
    assert (c.situacao, c.exercicio) == ("VIGENTE", 2026)


# ---------- sigilo do processo vinculado ---------------------------------------
# Só o caminho da RECUSA, sem banco: `assert_acesso_processo` é trocado por um
# que nega. O caminho em que o usuário TEM credencial exige um processo real e
# fica para a G3, quando o vínculo com o protocolo deixa de ser opcional.

async def _nega(*_args, **_kwargs):
    raise SigiloAcessoError("Processo não encontrado")


async def test_processo_sigiloso_some_do_detalhe_sem_derrubar_o_contrato(monkeypatch):
    monkeypatch.setattr(svc, "assert_acesso_processo", _nega)
    contrato = SimpleNamespace(id_processo=4242)
    visivel = await svc._processo_visivel(
        None, tenant_id=1, contrato=contrato, usuario=SimpleNamespace(id=1))
    assert visivel is None


async def test_vincular_processo_sem_credencial_devolve_a_mesma_recusa_de_inexistente(
        monkeypatch):
    """A mensagem não pode distinguir "não existe" de "existe e você não pode
    ver" — é a regra que saiu do conserto do anexo sigiloso."""
    monkeypatch.setattr(svc, "assert_acesso_processo", _nega)
    with pytest.raises(ContratoError) as exc:
        await svc._validar_processo(
            None, tenant_id=1, id_processo=4242, usuario=SimpleNamespace(id=1))
    assert exc.value.status_code == 422
    assert exc.value.detail == "Processo não encontrado"

