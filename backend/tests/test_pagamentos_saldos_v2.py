"""Pagamentos v2.0 Fase 2B — saldos completos (bloqueio + 5 saldos + snapshot) e
elegibilidade por modo_movimentacao.

Cobre: bloqueio administrativo reduz o disponível projetado (RF-SLD-07); bloqueio
fora do período não afeta; contas com modo_movimentacao != 'PAGA' não são
elegíveis nem aceitas como conta pagadora (RF-CTA-08); snapshot diário idempotente
(RF-SLD-03). Padrão: provisionar_tenant + admin_engine.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import (
    AlcadaCreate, BloqueioSaldoCreate, ContaCreate, DebitoCreate, FonteCreate,
    FornecedorCreate, GrupoAutorizacaoIn, NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_bloqueios as bloq
from app.services import pagamentos_caixa as caixa
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as deb
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _doc() -> str:
    return str(uuid.uuid4().int)[:14]


async def _provisionar(engine):
    slug = f"pagsld{uuid.uuid4().hex[:8]}"
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Saldos", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico")
    return tenant


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.saldo_historico WHERE tenant_id=:t",
            "DELETE FROM pagamentos.bloqueio_saldo WHERE tenant_id=:t",
            "DELETE FROM pagamentos.ordem_pagamento_debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.ordem_pagamento WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito_historico WHERE tenant_id=:t",
            "UPDATE pagamentos.parcela SET id_movimentacao=NULL WHERE tenant_id=:t",
            "DELETE FROM pagamentos.movimentacao_conta WHERE tenant_id=:t",
            "DELETE FROM pagamentos.parcela WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito WHERE tenant_id=:t",
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


async def _conta(engine, tenant_id, *, saldo="1000.00", modo="PAGA", fonte_id=None):
    async with _sm(engine)() as s:
        if fonte_id is None:
            fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
                codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
            fonte_id = fonte.id
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome="Conta", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte_id, grupo_despesa="CUSTEIO",
            saldo_inicial=saldo, modo_movimentacao=modo))
    return fonte_id, conta


async def test_bloqueio_reduz_disponivel_projetado(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        _fonte, conta = await _conta(admin_engine, t.id, saldo="1000.00")
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            await bloq.criar_bloqueio(s, tenant_id=t.id, usuario_id=uid, payload=BloqueioSaldoCreate(
                id_conta=conta.id, valor="300.00", motivo="Reserva judicial",
                periodo_inicio=date.today()))
        async with _sm(admin_engine)() as s:
            saldo = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert saldo.bloqueado == Decimal("300.00")
        assert saldo.saldo_bancario == Decimal("1000.00")
        assert saldo.disponivel == Decimal("700.00")
        assert saldo.disponivel_projetado == Decimal("700.00")
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueio_fora_do_periodo_nao_afeta(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        _fonte, conta = await _conta(admin_engine, t.id, saldo="1000.00")
        futuro = date.today() + timedelta(days=10)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            await bloq.criar_bloqueio(s, tenant_id=t.id, usuario_id=uid, payload=BloqueioSaldoCreate(
                id_conta=conta.id, valor="300.00", motivo="Futuro",
                periodo_inicio=futuro, periodo_fim=futuro + timedelta(days=5)))
        async with _sm(admin_engine)() as s:
            saldo = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert saldo.bloqueado == Decimal("0")
        assert saldo.disponivel == Decimal("1000.00")
    finally:
        await _cleanup(admin_engine, t.id)


async def test_conta_nao_paga_fora_de_elegiveis(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        fonte_id, conta_paga = await _conta(admin_engine, t.id, modo="PAGA")
        _f, conta_recebe = await _conta(admin_engine, t.id, modo="RECEBE", fonte_id=fonte_id)
        async with _sm(admin_engine)() as s:
            elegiveis = await aut.contas_elegiveis(s, tenant_id=t.id, id_fonte=fonte_id)
        ids = {c.id_conta for c in elegiveis}
        assert conta_paga.id in ids
        assert conta_recebe.id not in ids
    finally:
        await _cleanup(admin_engine, t.id)


async def test_snapshot_saldos_idempotente(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        _fonte, conta = await _conta(admin_engine, t.id, saldo="500.00")
        async with _sm(admin_engine)() as s:
            n1 = await caixa.registrar_snapshot_saldos(s, tenant_id=t.id)
        # 2ª execução no mesmo dia não duplica (upsert por conta+data)
        async with _sm(admin_engine)() as s:
            n2 = await caixa.registrar_snapshot_saldos(s, tenant_id=t.id)
        assert n1 == 1 and n2 == 1
        async with _sm(admin_engine)() as s:
            linhas = (await s.execute(text(
                "SELECT saldo_bancario FROM pagamentos.saldo_historico "
                "WHERE tenant_id=:t AND id_conta=:c AND data=CURRENT_DATE"),
                {"t": t.id, "c": conta.id})).all()
        assert len(linhas) == 1
        assert linhas[0][0] == Decimal("500.00")
    finally:
        await _cleanup(admin_engine, t.id)


# ---- autorizar rejeita conta pagadora não-PAGA (RF-CTA-08) ----
async def _novo_usuario(engine, tenant_id, sufixo):
    async with _sm(engine)() as s:
        r = await s.execute(text(
            """INSERT INTO utils.usuario (tenant_id, nome, email, cpf, senha, ativo, excluido, data_criacao)
               VALUES (:t, :n, :e, :c, 'x', true, false, NOW()) RETURNING id"""),
            {"t": tenant_id, "n": f"U {sufixo}", "e": f"{sufixo}@t.local", "c": uuid.uuid4().hex[:11]})
        uid = r.scalar_one(); await s.commit()
    return uid


async def test_autorizar_conta_nao_paga_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        fonte_id, conta_recebe = await _conta(admin_engine, t.id, modo="RECEBE")
        async with _sm(admin_engine)() as s:
            forn = await cad.criar_fornecedor(s, tenant_id=t.id, payload=FornecedorCreate(
                tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Forn"))
            nat = await cad.criar_natureza(s, tenant_id=t.id, payload=NaturezaCreate(
                codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Mat"))
        sol = await _novo_usuario(admin_engine, t.id, f"s{uuid.uuid4().hex[:6]}")
        apr = await _novo_usuario(admin_engine, t.id, f"a{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            d = await deb.criar_debito(s, tenant_id=t.id, usuario_id=sol, payload=DebitoCreate(
                id_fornecedor=forn.id, id_natureza=nat.id, id_fonte_recursos=fonte_id,
                valor_total="100.00", competencia="2026-07", descricao="x",
                parcelas=[ParcelaCreate(numero=1, valor="100.00", vencimento="2026-08-01")]))
        async with _sm(admin_engine)() as s:
            await deb.enviar_validacao(s, tenant_id=t.id, debito_id=d.id, usuario_id=sol)
        async with _sm(admin_engine)() as s:
            await deb.confirmar_liquidacao(s, tenant_id=t.id, debito_id=d.id, usuario_id=apr)
        async with _sm(admin_engine)() as s:
            await deb.validar(s, tenant_id=t.id, debito_id=d.id, usuario_id=apr)
        async with _sm(admin_engine)() as s:
            await deb.encaminhar(s, tenant_id=t.id, debito_id=d.id, usuario_id=apr)
        autorizador = await _novo_usuario(admin_engine, t.id, f"au{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            await cad.criar_alcada(s, tenant_id=t.id, payload=AlcadaCreate(
                id_usuario=autorizador, id_natureza=None, valor_maximo="999999.00"))
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador, grupos=[
                    GrupoAutorizacaoIn(id_fonte=fonte_id, id_conta_pagadora=conta_recebe.id,
                                       debito_ids=[d.id])])
            assert exc.value.status_code == 422
            assert "pagamento" in exc.value.detail.lower()
    finally:
        await _cleanup(admin_engine, t.id)
