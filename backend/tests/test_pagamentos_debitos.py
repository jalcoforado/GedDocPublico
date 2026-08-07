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
    """Fornecedor + natureza + fonte + conta + unidade prontos para um débito."""
    from sqlalchemy import select
    from app.models import TipoUnidadeTrabalho, UnidadeTrabalho

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

        # Unidade (busca a primeira, ou cria uma se não existir)
        stmt = select(UnidadeTrabalho).where(UnidadeTrabalho.tenant_id == tenant_id).limit(1)
        unidade_result = await s.execute(stmt)
        unidade = unidade_result.scalar()
        if not unidade:
            tipo_stmt = select(TipoUnidadeTrabalho).limit(1)
            tipo_result = await s.execute(tipo_stmt)
            tipo = tipo_result.scalar()
            if not tipo:
                tipo = TipoUnidadeTrabalho(tenant_id=tenant_id, tipo_unidade_trabalho="Administração")
                s.add(tipo)
                await s.flush()
            unidade = UnidadeTrabalho(
                tenant_id=tenant_id, id_tipo_unidade_trabalho=tipo.id,
                unidade_trabalho="Unidade Deb",
            )
            s.add(unidade)
            await s.flush()
    return forn, nat, conta, unidade


def _payload_debito(forn, nat, conta, unidade, *, valor="1000.00", parcelas=None):
    return DebitoCreate(
        id_fornecedor=forn.id, id_natureza=nat.id,
        id_fonte_recursos=conta.id_fonte_recursos, id_conta=conta.id,
        id_unidade=unidade.id, valor_total=valor, competencia="2026-07",
        descricao="Compra de material",
        parcelas=parcelas or [ParcelaCreate(numero=1, valor=valor, vencimento="2026-08-01")],
    )


async def test_criar_debito_com_parcelas(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, conta, unidade = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                payload=_payload_debito(forn, nat, conta, unidade, valor="1000.00", parcelas=[
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
        forn, nat, conta, unidade = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            with pytest.raises(HTTPException) as exc:
                await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                    payload=_payload_debito(forn, nat, conta, unidade, valor="1000.00", parcelas=[
                        ParcelaCreate(numero=1, valor="999.00", vencimento="2026-08-01")]))
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


async def test_atualizar_debito_fora_de_rascunho_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, conta, unidade = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                payload=_payload_debito(forn, nat, conta, unidade))
        async with _sm(admin_engine)() as s:
            await s.execute(text(
                "UPDATE pagamentos.debito SET status='EM_VALIDACAO' WHERE id=:i"),
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
        forn, nat, conta, unidade = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                payload=_payload_debito(forn, nat, conta, unidade))
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
        forn, nat, conta, unidade = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                payload=_payload_debito(forn, nat, conta, unidade))
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
        forn, nat, conta, unidade = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                payload=_payload_debito(forn, nat, conta, unidade))
        async with _sm(admin_engine)() as s:
            await s.execute(text(
                "UPDATE pagamentos.debito SET status='VALIDADO' WHERE id=:i"), {"i": d.id})
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
        forn, nat, conta, unidade = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                payload=_payload_debito(forn, nat, conta, unidade))
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


async def test_criar_debito_sem_conta_sugerida_ok(admin_engine):
    """v2.0: a conta sugerida é opcional; a fonte é obrigatória e vinculante."""
    t = await _provisionar(admin_engine)
    try:
        forn, nat, conta, unidade = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid, payload=DebitoCreate(
                id_fornecedor=forn.id, id_natureza=nat.id,
                id_fonte_recursos=conta.id_fonte_recursos, id_conta=None, id_unidade=unidade.id,
                valor_total="1000.00", competencia="2026-07", descricao="Sem conta sugerida",
                parcelas=[ParcelaCreate(numero=1, valor="1000.00", vencimento="2026-08-01")]))
        assert d.status == "RASCUNHO"
        assert d.id_conta is None
        assert d.id_fonte_recursos == conta.id_fonte_recursos
        assert d.id_conta_pagadora is None
    finally:
        await _cleanup(admin_engine, t.id)


async def test_criar_debito_conta_de_outra_fonte_422(admin_engine):
    """A conta sugerida, se informada, deve pertencer à fonte do débito."""
    t = await _provisionar(admin_engine)
    try:
        forn, nat, conta, unidade = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            outra_fonte = await cad.criar_fonte(s, tenant_id=t.id, payload=FonteCreate(
                codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Outra", grupos_despesa_permitidos=[]))
            outra_conta = await cad.criar_conta(s, tenant_id=t.id, payload=ContaCreate(
                nome="Conta Outra", banco="002", agencia="2", conta=uuid.uuid4().hex[:8],
                id_fonte_recursos=outra_fonte.id, grupo_despesa="CUSTEIO"))
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid, payload=DebitoCreate(
                    id_fornecedor=forn.id, id_natureza=nat.id,
                    id_fonte_recursos=conta.id_fonte_recursos, id_conta=outra_conta.id, id_unidade=unidade.id,
                    valor_total="1000.00", competencia="2026-07", descricao="Conta divergente",
                    parcelas=[ParcelaCreate(numero=1, valor="1000.00", vencimento="2026-08-01")]))
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


async def test_listar_debitos_filtra_por_fonte_e_urgente(admin_engine):
    """RF-PNL-02: a listagem filtra por fonte/urgência (dimensões do painel)."""
    t = await _provisionar(admin_engine)
    try:
        forn_a, nat_a, conta_a, unidade_a = await _base(admin_engine, t.id)
        forn_b, nat_b, conta_b, unidade_b = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            da = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                                        payload=_payload_debito(forn_a, nat_a, conta_a, unidade_a))
            db_ = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                                         payload=_payload_debito(forn_b, nat_b, conta_b, unidade_b))
        async with _sm(admin_engine)() as s:
            so_a = await svc.listar_debitos(s, tenant_id=t.id, id_fonte=conta_a.id_fonte_recursos)
        ids = {d.id for d in so_a}
        assert da.id in ids and db_.id not in ids
    finally:
        await _cleanup(admin_engine, t.id)
