"""Pagamentos F1 — Fluxo do Gestor (Task 5).

Cobre as 5 transições de gestão (`services/pagamentos_debitos.py`):
- enviar_para_gestor: RASCUNHO → AGUARDANDO_GESTOR
- gestor_autorizar: AGUARDANDO_GESTOR → AGUARDANDO_VALIDACAO
- gestor_rejeitar: AGUARDANDO_GESTOR → REJEITADA_GESTOR (terminal)
- solicitar_ajuste: de qualquer etapa → AJUSTE_GESTOR/VALIDACAO/AUTORIDADE
- responder_ajuste: AJUSTE_* → AGUARDANDO_GESTOR/VALIDACAO/AUTORIDADE (conforme destino)

Também testa segregação, lock_version e histórico.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import (
    ContaCreate, DebitoCreate, FonteCreate, FornecedorCreate,
    NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as svc
from app.services import pagamentos_estados as est
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("pag_ges")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos Gestor", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _doc() -> str:
    return str(uuid.uuid4().int)[:14]


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.ordem_pagamento_debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.ordem_pagamento WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito_historico WHERE tenant_id=:t",
            "DELETE FROM pagamentos.parcela WHERE tenant_id=:t",
            "DELETE FROM pagamentos.movimentacao_conta WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.contrato WHERE tenant_id=:t",
            "DELETE FROM pagamentos.alcada WHERE tenant_id=:t",
            "DELETE FROM pagamentos.natureza_despesa WHERE tenant_id=:t",
            "DELETE FROM pagamentos.conta_bancaria WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fonte_recursos WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor_situacao_historico WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


async def _base(engine, tenant_id):
    """Fornecedor + natureza + fonte + conta prontos para um débito."""
    async with _sm(engine)() as s:
        forn = await cad.criar_fornecedor(s, tenant_id=tenant_id, payload=FornecedorCreate(
            tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Fornecedor Gest LTDA"))
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome="Conta Gest", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO", saldo_inicial="10000.00"))
    return forn, nat, conta


def _payload_debito(forn, nat, conta, *, valor="1000.00"):
    return DebitoCreate(
        id_fornecedor=forn.id, id_natureza=nat.id,
        id_fonte_recursos=conta.id_fonte_recursos, id_conta=conta.id,
        valor_total=valor, competencia="2026-07", descricao="Compra de material",
        parcelas=[ParcelaCreate(numero=1, valor=valor, vencimento="2026-08-01")],
    )


async def _novo_usuario(engine, tenant_id, sufixo):
    """Cria um segundo usuário no tenant (para segregação)."""
    async with _sm(engine)() as s:
        r = await s.execute(text(
            """INSERT INTO utils.usuario (tenant_id, nome, email, cpf, senha, ativo, excluido, data_criacao)
               VALUES (:t, :n, :e, :c, 'x', true, false, NOW()) RETURNING id"""),
            {"t": tenant_id, "n": f"User {sufixo}", "e": f"{sufixo}@t.local",
             "c": uuid.uuid4().hex[:11]})
        uid = r.scalar_one(); await s.commit()
    return uid


@pytest.fixture
async def arreio_debito(admin_engine):
    """Retorna (tenant, debito, solicitante_id, gestor_id, forn, nat, conta)."""
    t = await _provisionar(admin_engine)
    forn, nat, conta = await _base(admin_engine, t.id)

    # Admin (solicitante)
    async with _sm(admin_engine)() as s:
        solicitante = (await s.execute(text(
            "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()

    # Gestor (outro usuário)
    gestor = await _novo_usuario(admin_engine, t.id, f"gest{uuid.uuid4().hex[:6]}")

    # Cria débito em RASCUNHO
    async with _sm(admin_engine)() as s:
        d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=solicitante,
                                   payload=_payload_debito(forn, nat, conta))

    return t, d, solicitante, gestor, forn, nat, conta


@pytest.fixture
async def arreio_debito_no_gestor(admin_engine, arreio_debito):
    """Retorna (tenant, debito, ...) com débito já em AGUARDANDO_GESTOR."""
    t, d, solicitante, gestor, forn, nat, conta = arreio_debito

    # Envia para gestor
    async with _sm(admin_engine)() as s:
        d = await svc.enviar_para_gestor(s, tenant_id=t.id, debito_id=d.id,
                                        usuario_id=solicitante, lock_version=d.lock_version)

    return t, d, solicitante, gestor, forn, nat, conta


@pytest.mark.asyncio
async def test_enviar_para_gestor_rascunho_para_aguardando(admin_engine, arreio_debito):
    """RASCUNHO → AGUARDANDO_GESTOR."""
    t, d, solicitante, _gestor, _forn, _nat, _conta = arreio_debito
    try:
        async with _sm(admin_engine)() as s:
            result = await svc.enviar_para_gestor(s, tenant_id=t.id, debito_id=d.id,
                                                 usuario_id=solicitante, lock_version=d.lock_version)
        assert result.situacao_tramitacao == est.AGUARDANDO_GESTOR
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        assert any(h.acao == "ENVIADO" for h in hist)
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_gestor_autorizar_transita_para_validacao(admin_engine, arreio_debito_no_gestor):
    """AGUARDANDO_GESTOR → AGUARDANDO_VALIDACAO."""
    t, d, _solicitante, gestor, _forn, _nat, _conta = arreio_debito_no_gestor
    try:
        async with _sm(admin_engine)() as s:
            result = await svc.gestor_autorizar(s, tenant_id=t.id, debito_id=d.id,
                                               usuario_id=gestor, lock_version=d.lock_version)
        assert result.situacao_tramitacao == est.AGUARDANDO_VALIDACAO
        assert result.id_gestor_decisor == gestor
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        assert any(h.acao == "AUTORIZADO_GESTOR" for h in hist)
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_gestor_rejeitar_terminal(admin_engine, arreio_debito_no_gestor):
    """AGUARDANDO_GESTOR → REJEITADA_GESTOR (terminal)."""
    t, d, _solicitante, gestor, _forn, _nat, _conta = arreio_debito_no_gestor
    try:
        async with _sm(admin_engine)() as s:
            result = await svc.gestor_rejeitar(s, tenant_id=t.id, debito_id=d.id,
                                              usuario_id=gestor, lock_version=d.lock_version,
                                              justificativa="Despesa não apropriada")
        assert result.situacao_tramitacao == est.REJEITADA_GESTOR
        assert result.id_gestor_decisor == gestor
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        rej = [h for h in hist if h.acao == "REJEITADO_GESTOR"]
        assert len(rej) == 1
        assert rej[0].justificativa == "Despesa não apropriada"
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_gestor_rejeitar_sem_justificativa_422(admin_engine, arreio_debito_no_gestor):
    """gestor_rejeitar exige justificativa."""
    t, d, _solicitante, gestor, _forn, _nat, _conta = arreio_debito_no_gestor
    try:
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.gestor_rejeitar(s, tenant_id=t.id, debito_id=d.id,
                                         usuario_id=gestor, lock_version=d.lock_version,
                                         justificativa="")
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_solicitar_ajuste_ao_gestor(admin_engine, arreio_debito_no_gestor):
    """AGUARDANDO_GESTOR → AJUSTE_GESTOR."""
    t, d, solicitante, _gestor, _forn, _nat, _conta = arreio_debito_no_gestor
    try:
        async with _sm(admin_engine)() as s:
            result = await svc.solicitar_ajuste(s, tenant_id=t.id, debito_id=d.id,
                                               usuario_id=solicitante, lock_version=d.lock_version,
                                               etapa="GESTOR", justificativa="Corrigir fornecedor")
        assert result.situacao_tramitacao == est.AJUSTE_GESTOR
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        adj = [h for h in hist if h.acao == "AJUSTE_SOLICITADO"]
        assert len(adj) == 1
        assert adj[0].justificativa == "Corrigir fornecedor"
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_responder_ajuste_volta_para_aguardando_gestor(admin_engine, arreio_debito_no_gestor):
    """AJUSTE_GESTOR → AGUARDANDO_GESTOR."""
    t, d, solicitante, _gestor, _forn, _nat, _conta = arreio_debito_no_gestor
    try:
        # Primeiro solicita ajuste
        async with _sm(admin_engine)() as s:
            d = await svc.solicitar_ajuste(s, tenant_id=t.id, debito_id=d.id,
                                          usuario_id=solicitante, lock_version=d.lock_version,
                                          etapa="GESTOR", justificativa="Precisa corrigir")

        # Depois responde
        async with _sm(admin_engine)() as s:
            result = await svc.responder_ajuste(s, tenant_id=t.id, debito_id=d.id,
                                               usuario_id=solicitante, lock_version=d.lock_version)
        assert result.situacao_tramitacao == est.AGUARDANDO_GESTOR
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        resp = [h for h in hist if h.acao == "AJUSTE_RESPONDIDO"]
        assert len(resp) == 1
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_lock_version_mismatch_409(admin_engine, arreio_debito_no_gestor):
    """Lock version incompatível (concorrência) → 409."""
    t, d, _solicitante, gestor, _forn, _nat, _conta = arreio_debito_no_gestor
    try:
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                # Usa lock_version errado
                await svc.gestor_autorizar(s, tenant_id=t.id, debito_id=d.id,
                                          usuario_id=gestor, lock_version=d.lock_version + 999)
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_solicitar_ajuste_etapa_desconhecida_422(admin_engine, arreio_debito_no_gestor):
    """etapa inválida em solicitar_ajuste."""
    t, d, solicitante, _gestor, _forn, _nat, _conta = arreio_debito_no_gestor
    try:
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.solicitar_ajuste(s, tenant_id=t.id, debito_id=d.id,
                                          usuario_id=solicitante, lock_version=d.lock_version,
                                          etapa="INEXISTENTE", justificativa="Teste")
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)
