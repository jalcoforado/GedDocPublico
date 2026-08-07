"""Pagamentos F1 — Fluxo de Validação e Autoridade (Task 6).

Cobre as 4 transições de validação/autoridade (`services/pagamentos_debitos.py`):
- validar: AGUARDANDO_VALIDACAO → AGUARDANDO_AUTORIDADE
- autoridade_aprovar: AGUARDANDO_AUTORIDADE → AUTORIZADA + ELEGIVEL
- autoridade_indeferir: AGUARDANDO_AUTORIDADE → INDEFERIDA_AUTORIDADE (terminal)
- cancelar: de qualquer etapa não-terminal → CANCELADA

Também testa segregação, lock_version e histórico.
"""
from __future__ import annotations

import uuid

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
    slug = _slug("pagvld")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos Validacao", admin_email=f"{slug}@t.local",
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
    """Fornecedor + natureza + fonte + conta + unidade prontos para um débito."""
    from sqlalchemy import select
    from app.models import TipoUnidadeTrabalho, UnidadeTrabalho
    async with _sm(engine)() as s:
        forn = await cad.criar_fornecedor(s, tenant_id=tenant_id, payload=FornecedorCreate(
            tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Fornecedor Vld LTDA"))
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome="Conta Vld", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO", saldo_inicial="10000.00"))

        # Unidade
        tipo_stmt = select(TipoUnidadeTrabalho).limit(1)
        tipo_result = await s.execute(tipo_stmt)
        tipo = tipo_result.scalar()
        if not tipo:
            tipo = TipoUnidadeTrabalho(tenant_id=tenant_id, tipo_unidade_trabalho="Administração")
            s.add(tipo)
            await s.flush()
        unidade = UnidadeTrabalho(
            tenant_id=tenant_id, id_tipo_unidade_trabalho=tipo.id,
            unidade_trabalho="Unidade Vld",
        )
        s.add(unidade)
        await s.commit()
    return forn, nat, conta, unidade


def _payload_debito(forn, nat, conta, unidade, *, valor="1000.00"):
    return DebitoCreate(
        id_fornecedor=forn.id, id_natureza=nat.id, id_unidade=unidade.id,
        id_fonte_recursos=conta.id_fonte_recursos, id_conta=conta.id,
        valor_total=valor, competencia="2026-07", descricao="Compra de material",
        parcelas=[ParcelaCreate(numero=1, valor=valor, vencimento="2026-08-01")],
    )


async def _novo_usuario(engine, tenant_id, sufixo):
    """Cria um segundo usuário no tenant."""
    async with _sm(engine)() as s:
        r = await s.execute(text(
            """INSERT INTO utils.usuario (tenant_id, nome, email, cpf, senha, ativo, excluido, data_criacao)
               VALUES (:t, :n, :e, :c, 'x', true, false, NOW()) RETURNING id"""),
            {"t": tenant_id, "n": f"User {sufixo}", "e": f"{sufixo}@t.local",
             "c": uuid.uuid4().hex[:11]})
        uid = r.scalar_one(); await s.commit()
    return uid


@pytest.fixture
async def arreio_debito_em_validacao(admin_engine):
    """Retorna (tenant, debito, ...) com débito já em AGUARDANDO_VALIDACAO."""
    t = await _provisionar(admin_engine)
    forn, nat, conta, unidade = await _base(admin_engine, t.id)

    # Admin (solicitante)
    async with _sm(admin_engine)() as s:
        solicitante = (await s.execute(text(
            "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()

    # Gestor (outro usuário)
    gestor = await _novo_usuario(admin_engine, t.id, f"gest{uuid.uuid4().hex[:6]}")

    # Validador (outro usuário)
    validador = await _novo_usuario(admin_engine, t.id, f"vald{uuid.uuid4().hex[:6]}")

    # Cria débito em RASCUNHO
    async with _sm(admin_engine)() as s:
        d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=solicitante,
                                   payload=_payload_debito(forn, nat, conta, unidade))

    # Envia para gestor
    async with _sm(admin_engine)() as s:
        d = await svc.enviar_para_gestor(s, tenant_id=t.id, debito_id=d.id,
                                        usuario_id=solicitante, lock_version=d.lock_version)

    # Gestor autoriza → AGUARDANDO_VALIDACAO
    async with _sm(admin_engine)() as s:
        d = await svc.gestor_autorizar(s, tenant_id=t.id, debito_id=d.id,
                                      usuario_id=gestor, lock_version=d.lock_version)

    return t, d, solicitante, gestor, validador, forn, nat, conta


@pytest.fixture
async def arreio_debito_em_autoridade(admin_engine, arreio_debito_em_validacao):
    """Retorna (tenant, debito, ...) com débito já em AGUARDANDO_AUTORIDADE."""
    t, d, solicitante, gestor, validador, forn, nat, conta = arreio_debito_em_validacao

    # Validador valida → AGUARDANDO_AUTORIDADE
    async with _sm(admin_engine)() as s:
        d = await svc.confirmar_liquidacao(
            s, tenant_id=t.id, debito_id=d.id, usuario_id=validador)
        d = await svc.validar(s, tenant_id=t.id, debito_id=d.id,
                             usuario_id=validador, lock_version=d.lock_version)

    return t, d, solicitante, gestor, validador, forn, nat, conta


@pytest.mark.asyncio
async def test_validar_transita_para_autoridade(admin_engine, arreio_debito_em_validacao):
    """AGUARDANDO_VALIDACAO → AGUARDANDO_AUTORIDADE."""
    t, d, _sol, _gest, validador, _forn, _nat, _conta = arreio_debito_em_validacao
    try:
        async with _sm(admin_engine)() as s:
            d = await svc.confirmar_liquidacao(
                s, tenant_id=t.id, debito_id=d.id, usuario_id=validador)
            result = await svc.validar(s, tenant_id=t.id, debito_id=d.id,
                                      usuario_id=validador, lock_version=d.lock_version)
        assert result.situacao_tramitacao == est.AGUARDANDO_AUTORIDADE
        assert result.id_validador == validador
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        assert any(h.acao == "VALIDADO" for h in hist)
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_autoridade_aprovar_transita_para_autorizada(admin_engine, arreio_debito_em_autoridade):
    """AGUARDANDO_AUTORIDADE → AUTORIZADA + ELEGIVEL."""
    t, d, _sol, _gest, _val, _forn, _nat, _conta = arreio_debito_em_autoridade
    autoridade = await _novo_usuario(admin_engine, t.id, f"aut{uuid.uuid4().hex[:6]}")
    try:
        async with _sm(admin_engine)() as s:
            result = await svc.autoridade_aprovar(s, tenant_id=t.id, debito_id=d.id,
                                                 usuario_id=autoridade, lock_version=d.lock_version)
        assert result.situacao_tramitacao == est.AUTORIZADA
        assert result.situacao_fila == est.ELEGIVEL
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        assert any(h.acao == "AUTORIZADO" for h in hist)
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_autoridade_indeferir_terminal(admin_engine, arreio_debito_em_autoridade):
    """AGUARDANDO_AUTORIDADE → INDEFERIDA_AUTORIDADE (terminal)."""
    t, d, _sol, _gest, _val, _forn, _nat, _conta = arreio_debito_em_autoridade
    autoridade = await _novo_usuario(admin_engine, t.id, f"aut{uuid.uuid4().hex[:6]}")
    try:
        async with _sm(admin_engine)() as s:
            result = await svc.autoridade_indeferir(s, tenant_id=t.id, debito_id=d.id,
                                                   usuario_id=autoridade, lock_version=d.lock_version,
                                                   justificativa="Recurso insuficiente")
        assert result.situacao_tramitacao == est.INDEFERIDA_AUTORIDADE
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        ind = [h for h in hist if h.acao == "INDEFERIDO"]
        assert len(ind) == 1
        assert ind[0].justificativa == "Recurso insuficiente"
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_autoridade_indeferir_sem_justificativa_422(admin_engine, arreio_debito_em_autoridade):
    """autoridade_indeferir exige justificativa."""
    t, d, _sol, _gest, _val, _forn, _nat, _conta = arreio_debito_em_autoridade
    autoridade = await _novo_usuario(admin_engine, t.id, f"aut{uuid.uuid4().hex[:6]}")
    try:
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.autoridade_indeferir(s, tenant_id=t.id, debito_id=d.id,
                                              usuario_id=autoridade, lock_version=d.lock_version,
                                              justificativa="")
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_cancelar_de_rascunho(admin_engine):
    """Pode cancelar de RASCUNHO."""
    t = await _provisionar(admin_engine)
    forn, nat, conta, unidade = await _base(admin_engine, t.id)
    async with _sm(admin_engine)() as s:
        solicitante = (await s.execute(text(
            "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
    try:
        async with _sm(admin_engine)() as s:
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=solicitante,
                                       payload=_payload_debito(forn, nat, conta, unidade))
        async with _sm(admin_engine)() as s:
            result = await svc.cancelar(s, tenant_id=t.id, debito_id=d.id,
                                       usuario_id=solicitante, lock_version=d.lock_version,
                                       justificativa="Solicitação cancelada")
        assert result.situacao_tramitacao == est.CANCELADA
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        canc = [h for h in hist if h.acao == "CANCELADO"]
        assert len(canc) == 1
        assert canc[0].justificativa == "Solicitação cancelada"
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_cancelar_de_autoridade(admin_engine, arreio_debito_em_autoridade):
    """Pode cancelar de AGUARDANDO_AUTORIDADE."""
    t, d, _sol, _gest, _val, _forn, _nat, _conta = arreio_debito_em_autoridade
    try:
        async with _sm(admin_engine)() as s:
            result = await svc.cancelar(s, tenant_id=t.id, debito_id=d.id,
                                       usuario_id=_val, lock_version=d.lock_version,
                                       justificativa="Cancelado por erro de entrada")
        assert result.situacao_tramitacao == est.CANCELADA
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_cancelar_terminal_409(admin_engine, arreio_debito_em_autoridade):
    """Não pode cancelar de estado terminal (INDEFERIDA_AUTORIDADE)."""
    t, d, _sol, _gest, _val, _forn, _nat, _conta = arreio_debito_em_autoridade
    autoridade = await _novo_usuario(admin_engine, t.id, f"aut{uuid.uuid4().hex[:6]}")
    try:
        # Indeferir (terminal)
        async with _sm(admin_engine)() as s:
            d = await svc.autoridade_indeferir(s, tenant_id=t.id, debito_id=d.id,
                                              usuario_id=autoridade, lock_version=d.lock_version,
                                              justificativa="Não aprovado")

        # Tentar cancelar
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.cancelar(s, tenant_id=t.id, debito_id=d.id,
                                  usuario_id=_val, lock_version=d.lock_version,
                                  justificativa="Cancelado")
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_cancelar_sem_justificativa_422(admin_engine, arreio_debito_em_validacao):
    """cancelar exige justificativa."""
    t, d, _sol, _gest, _val, _forn, _nat, _conta = arreio_debito_em_validacao
    try:
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.cancelar(s, tenant_id=t.id, debito_id=d.id,
                                  usuario_id=_val, lock_version=d.lock_version,
                                  justificativa="")
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_validar_lock_version_mismatch_409(admin_engine, arreio_debito_em_validacao):
    """Lock version incompatível (concorrência) → 409."""
    t, d, _sol, _gest, validador, _forn, _nat, _conta = arreio_debito_em_validacao
    try:
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.validar(s, tenant_id=t.id, debito_id=d.id,
                                 usuario_id=validador, lock_version=d.lock_version + 999)
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_autoridade_aprovar_lock_version_mismatch_409(admin_engine, arreio_debito_em_autoridade):
    """Lock version incompatível em autoridade_aprovar → 409."""
    t, d, _sol, _gest, _val, _forn, _nat, _conta = arreio_debito_em_autoridade
    autoridade = await _novo_usuario(admin_engine, t.id, f"aut{uuid.uuid4().hex[:6]}")
    try:
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.autoridade_aprovar(s, tenant_id=t.id, debito_id=d.id,
                                            usuario_id=autoridade, lock_version=d.lock_version + 999)
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)
