"""Pagamentos R1 — Caixa: movimentações, extrato e saldo por conta.

Cobre o serviço de domínio (`services/pagamentos_caixa.py`): saldo derivado de
conta.saldo_inicial + movimentações, extrato tenant-scoped, e bloqueio de
origens internas (PAGAMENTO/ESTORNO — exclusivas do R2) via API pública. Mesmo
padrão dos testes de cadastros (provisionar_tenant + admin_engine).
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import ContaCreate, FonteCreate, MovimentacaoCreate
from app.services import pagamentos_caixa as caixa
from app.services import pagamentos_cadastros as cad
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("pagcaixa")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos Caixa", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


async def _criar_conta(engine, tenant_id, *, saldo_inicial=Decimal("0"), nome="C1", codigo="700",
                       saldo_minimo_alerta=Decimal("0")):
    async with _sm(engine)() as s:
        fonte = await cad.criar_fonte(
            s, tenant_id=tenant_id,
            payload=FonteCreate(codigo=codigo, descricao="F", grupos_despesa_permitidos=["CUSTEIO"]),
        )
    async with _sm(engine)() as s:
        conta = await cad.criar_conta(
            s, tenant_id=tenant_id,
            payload=ContaCreate(
                nome=nome, banco="001", agencia="1", conta="1", id_fonte_recursos=fonte.id,
                grupo_despesa="CUSTEIO", saldo_inicial=saldo_inicial,
                saldo_minimo_alerta=saldo_minimo_alerta,
            ),
        )
    return conta


async def _usuario_id(engine, tenant_id):
    async with _sm(engine)() as s:
        return (await s.execute(
            text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": tenant_id},
        )).scalar_one()


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.movimentacao_conta WHERE tenant_id=:t",
            "DELETE FROM pagamentos.contrato WHERE tenant_id=:t",
            "DELETE FROM pagamentos.alcada WHERE tenant_id=:t",
            "DELETE FROM pagamentos.natureza_despesa WHERE tenant_id=:t",
            "DELETE FROM pagamentos.conta_bancaria WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fonte_recursos WHERE tenant_id=:t",
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


# ============================ saldo/extrato ====================================
async def test_saldo_reflete_entradas_e_saidas(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        conta = await _criar_conta(admin_engine, t.id, saldo_inicial=Decimal("1000"))
        usuario_id = await _usuario_id(admin_engine, t.id)

        async with _sm(admin_engine)() as s:
            await caixa.lancar_movimentacao(
                s, tenant_id=t.id, usuario_id=usuario_id,
                payload=MovimentacaoCreate(id_conta=conta.id, tipo="ENTRADA", valor=Decimal("500"),
                                            origem="APORTE", data=date(2026, 7, 14)),
            )
        async with _sm(admin_engine)() as s:
            await caixa.lancar_movimentacao(
                s, tenant_id=t.id, usuario_id=usuario_id,
                payload=MovimentacaoCreate(id_conta=conta.id, tipo="SAIDA", valor=Decimal("200"),
                                            origem="AJUSTE", data=date(2026, 7, 14)),
            )

        async with _sm(admin_engine)() as s:
            saldo = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert saldo.saldo_inicial == Decimal("1000")
        assert saldo.total_entradas == Decimal("500")
        assert saldo.total_saidas == Decimal("200")
        assert saldo.saldo_atual == Decimal("1300")

        async with _sm(admin_engine)() as s:
            extrato = await caixa.listar_extrato(s, tenant_id=t.id, conta_id=conta.id)
        assert len(extrato) == 2
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ origem interna bloqueada ==========================
async def test_origem_interna_via_api_bloqueada(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        conta = await _criar_conta(admin_engine, t.id, saldo_inicial=Decimal("1000"))
        usuario_id = await _usuario_id(admin_engine, t.id)

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await caixa.lancar_movimentacao(
                    s, tenant_id=t.id, usuario_id=usuario_id,
                    payload=MovimentacaoCreate(id_conta=conta.id, tipo="SAIDA", valor=Decimal("1"),
                                                origem="PAGAMENTO", data=date(2026, 7, 14)),
                )
            assert exc.value.status_code == 400
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ cross-tenant 404 ==================================
async def test_extrato_e_saldo_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        conta = await _criar_conta(admin_engine, a.id, saldo_inicial=Decimal("100"))
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await caixa.saldo_conta(s, tenant_id=b.id, conta_id=conta.id)
            assert exc.value.status_code == 404
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await caixa.listar_extrato(s, tenant_id=b.id, conta_id=conta.id)
            assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ============================ painel de caixa ===================================
async def test_painel_caixa_lista_saldos_e_alerta_minimo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        conta_ok = await _criar_conta(
            admin_engine, t.id, nome="Conta Saudavel", codigo="701",
            saldo_inicial=Decimal("1000"), saldo_minimo_alerta=Decimal("100"),
        )
        conta_baixa = await _criar_conta(
            admin_engine, t.id, nome="Conta Critica", codigo="702",
            saldo_inicial=Decimal("50"), saldo_minimo_alerta=Decimal("500"),
        )
        usuario_id = await _usuario_id(admin_engine, t.id)

        async with _sm(admin_engine)() as s:
            await caixa.lancar_movimentacao(
                s, tenant_id=t.id, usuario_id=usuario_id,
                payload=MovimentacaoCreate(id_conta=conta_ok.id, tipo="ENTRADA", valor=Decimal("200"),
                                            origem="APORTE", data=date(2026, 7, 14)),
            )
        async with _sm(admin_engine)() as s:
            await caixa.lancar_movimentacao(
                s, tenant_id=t.id, usuario_id=usuario_id,
                payload=MovimentacaoCreate(id_conta=conta_baixa.id, tipo="SAIDA", valor=Decimal("10"),
                                            origem="AJUSTE", data=date(2026, 7, 14)),
            )

        async with _sm(admin_engine)() as s:
            painel = await caixa.painel_caixa(s, tenant_id=t.id)

        assert [p.nome for p in painel] == ["Conta Critica", "Conta Saudavel"]

        p_ok = next(p for p in painel if p.id_conta == conta_ok.id)
        assert p_ok.saldo_atual == Decimal("1200")
        assert p_ok.abaixo_minimo is False

        p_baixa = next(p for p in painel if p.id_conta == conta_baixa.id)
        assert p_baixa.saldo_atual == Decimal("40")
        assert p_baixa.abaixo_minimo is True
    finally:
        await _cleanup(admin_engine, t.id)
