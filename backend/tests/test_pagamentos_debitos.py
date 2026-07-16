"""Pagamentos R2 — Débito com parcelas (CRUD de rascunho + trilha de histórico).

Cobre o serviço de domínio (`services/pagamentos_debitos.py`): criação de débito
com validação de referências (fornecedor/natureza/conta/contrato) e de soma de
parcelas == valor_total, gravação de debito_historico (CRIADO na criação),
edição restrita a RASCUNHO e exclusão lógica (soft-delete) restrita a
RASCUNHO/REJEITADO/CANCELADO. Mesmo padrão de `test_pagamentos_cadastros.py`
(provisionar_tenant + admin_engine).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import (
    ContaCreate, DebitoCreate, DebitoUpdate, FonteCreate, FornecedorCreate,
    NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("pagdeb")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos Debito", admin_email=f"{slug}@t.local",
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


async def _base(engine, tenant_id, *, saldo_inicial="10000.00"):
    """Fornecedor + natureza + fonte + conta prontos para um débito."""
    async with _sm(engine)() as s:
        forn = await cad.criar_fornecedor(s, tenant_id=tenant_id, payload=FornecedorCreate(
            tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Fornecedor Deb LTDA"))
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome="Conta Deb", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO", saldo_inicial=saldo_inicial))
    return forn, nat, conta


def _payload_debito(forn, nat, conta, *, valor="1000.00", parcelas=None):
    return DebitoCreate(
        id_fornecedor=forn.id, id_natureza=nat.id, id_conta=conta.id,
        valor_total=valor, competencia="2026-07", descricao="Compra de material",
        parcelas=parcelas or [ParcelaCreate(numero=1, valor=valor, vencimento="2026-08-01")],
    )


async def test_criar_debito_com_parcelas(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, conta = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                payload=_payload_debito(forn, nat, conta, valor="1000.00", parcelas=[
                    ParcelaCreate(numero=1, valor="600.00", vencimento="2026-08-01"),
                    ParcelaCreate(numero=2, valor="400.00", vencimento="2026-09-01"),
                ]))
        assert d.status == "RASCUNHO"
        async with _sm(admin_engine)() as s:
            parcelas = await svc.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        assert [p.numero for p in parcelas] == [1, 2]
        assert len(hist) == 1 and hist[0].acao == "CRIADO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_criar_debito_soma_parcelas_diferente_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, conta = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            with pytest.raises(HTTPException) as exc:
                await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                    payload=_payload_debito(forn, nat, conta, valor="1000.00", parcelas=[
                        ParcelaCreate(numero=1, valor="999.00", vencimento="2026-08-01")]))
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


async def test_atualizar_debito_fora_de_rascunho_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, conta = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                payload=_payload_debito(forn, nat, conta))
        async with _sm(admin_engine)() as s:
            await s.execute(text(
                "UPDATE pagamentos.debito SET status='AGUARDANDO_APROVACAO' WHERE id=:i"),
                {"i": d.id})
            await s.commit()
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.atualizar_debito(s, tenant_id=t.id, debito_id=d.id, usuario_id=uid,
                    payload=DebitoUpdate(descricao="Alterado"))
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_atualizar_debito_rascunho_troca_parcelas(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, conta = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                payload=_payload_debito(forn, nat, conta))
        async with _sm(admin_engine)() as s:
            atualizado = await svc.atualizar_debito(s, tenant_id=t.id, debito_id=d.id,
                usuario_id=uid, payload=DebitoUpdate(
                    descricao="Compra revisada", valor_total="1500.00", parcelas=[
                        ParcelaCreate(numero=1, valor="900.00", vencimento="2026-08-01"),
                        ParcelaCreate(numero=2, valor="600.00", vencimento="2026-09-01"),
                    ]))
        assert atualizado.descricao == "Compra revisada"
        assert atualizado.valor_total == Decimal("1500.00")
        async with _sm(admin_engine)() as s:
            parcelas = await svc.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
        # parcela antiga (1x 1000.00) soft-deletada; só as novas aparecem
        assert [(p.numero, p.valor) for p in parcelas] == [
            (1, Decimal("900.00")), (2, Decimal("600.00"))]
        async with _sm(admin_engine)() as s:
            total = (await s.execute(text(
                "SELECT count(*) FROM pagamentos.parcela WHERE id_debito=:i"),
                {"i": d.id})).scalar_one()
        assert total == 3  # 1 antiga (excluido=true) + 2 novas
    finally:
        await _cleanup(admin_engine, t.id)


async def test_atualizar_valor_total_sem_parcelas_divergente_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, conta = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                payload=_payload_debito(forn, nat, conta))
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.atualizar_debito(s, tenant_id=t.id, debito_id=d.id, usuario_id=uid,
                    payload=DebitoUpdate(valor_total="2000.00"))
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


async def test_excluir_debito_fora_de_status_permitido_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, conta = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                payload=_payload_debito(forn, nat, conta))
        async with _sm(admin_engine)() as s:
            await s.execute(text(
                "UPDATE pagamentos.debito SET status='APROVADO' WHERE id=:i"), {"i": d.id})
            await s.commit()
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.excluir_debito(s, tenant_id=t.id, debito_id=d.id)
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_excluir_debito_rascunho_soft_delete(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, conta = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                payload=_payload_debito(forn, nat, conta))
        async with _sm(admin_engine)() as s:
            await svc.excluir_debito(s, tenant_id=t.id, debito_id=d.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            assert exc.value.status_code == 404
        async with _sm(admin_engine)() as s:
            row = (await s.execute(text(
                "SELECT excluido FROM pagamentos.debito WHERE id=:i"), {"i": d.id})).fetchone()
        assert row[0] is True
    finally:
        await _cleanup(admin_engine, t.id)


async def _debito_pronto(engine, tenant_id, **kw):
    forn, nat, conta = await _base(engine, tenant_id)
    async with _sm(engine)() as s:
        uid = (await s.execute(text(
            "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": tenant_id})).scalar_one()
        d = await svc.criar_debito(s, tenant_id=tenant_id, usuario_id=uid,
                                   payload=_payload_debito(forn, nat, conta, **kw))
    return d, uid, conta


async def _novo_usuario(engine, tenant_id, sufixo):
    """Segundo usuário no tenant (para segregação)."""
    async with _sm(engine)() as s:
        r = await s.execute(text(
            """INSERT INTO utils.usuario (tenant_id, nome, email, cpf, senha, ativo, excluido, data_criacao)
               VALUES (:t, :n, :e, :c, 'x', true, false, NOW()) RETURNING id"""),
            {"t": tenant_id, "n": f"User {sufixo}", "e": f"{sufixo}@t.local",
             "c": uuid.uuid4().hex[:11]})
        uid = r.scalar_one(); await s.commit()
    return uid


async def test_fluxo_enviar_aprovar(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, solicitante, _ = await _debito_pronto(admin_engine, t.id)
        aprovador = await _novo_usuario(admin_engine, t.id, f"apr{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            d2 = await svc.enviar_aprovacao(s, tenant_id=t.id, debito_id=d.id, usuario_id=solicitante)
        assert d2.status == "AGUARDANDO_APROVACAO"
        async with _sm(admin_engine)() as s:
            d3 = await svc.aprovar(s, tenant_id=t.id, debito_id=d.id, usuario_id=aprovador)
        assert d3.status == "APROVADO"
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        assert [h.acao for h in hist] == ["APROVADO", "ENVIADO", "CRIADO"]
    finally:
        await _cleanup(admin_engine, t.id)


async def test_aprovar_pelo_proprio_solicitante_403(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, solicitante, _ = await _debito_pronto(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            await svc.enviar_aprovacao(s, tenant_id=t.id, debito_id=d.id, usuario_id=solicitante)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.aprovar(s, tenant_id=t.id, debito_id=d.id, usuario_id=solicitante)
            assert exc.value.status_code == 403
    finally:
        await _cleanup(admin_engine, t.id)


async def test_devolver_volta_a_rascunho_com_motivo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, solicitante, _ = await _debito_pronto(admin_engine, t.id)
        aprovador = await _novo_usuario(admin_engine, t.id, f"dev{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            await svc.enviar_aprovacao(s, tenant_id=t.id, debito_id=d.id, usuario_id=solicitante)
        async with _sm(admin_engine)() as s:
            d2 = await svc.devolver(s, tenant_id=t.id, debito_id=d.id, usuario_id=aprovador,
                                    justificativa="Falta nota fiscal")
        assert d2.status == "RASCUNHO"
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        assert hist[0].acao == "DEVOLVIDO" and hist[0].justificativa == "Falta nota fiscal"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_transicao_invalida_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, solicitante, _ = await _debito_pronto(admin_engine, t.id)
        # aprovar direto de RASCUNHO → 409
        outro = await _novo_usuario(admin_engine, t.id, f"inv{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.aprovar(s, tenant_id=t.id, debito_id=d.id, usuario_id=outro)
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_cancelar_apos_parcela_paga_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, solicitante, _ = await _debito_pronto(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            parcelas = await svc.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
        async with _sm(admin_engine)() as s:
            await s.execute(text(
                "UPDATE pagamentos.parcela SET status='PAGA' WHERE id=:i"), {"i": parcelas[0].id})
            await s.commit()
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.cancelar(s, tenant_id=t.id, debito_id=d.id, usuario_id=solicitante,
                                   justificativa="Cancelamento indevido")
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)
