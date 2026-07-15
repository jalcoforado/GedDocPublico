"""Pagamentos R2 — Autorização em lote (saldo/alçada/segregação) + Ordem de
Pagamento (OP). Cobre `services/pagamentos_autorizacao.py`: autorizar_lote é
all-or-nothing (todas as validações antes de qualquer mudança de status),
respeita alçada (específica > geral > sem alçada = 403), segregação de funções
(solicitante e aprovadores não podem autorizar) e saldo disponível por conta
(saldo_atual - comprometido). Mesmo padrão de `test_pagamentos_debitos.py`
(provisionar_tenant + admin_engine); helpers duplicados para independência.
"""
from __future__ import annotations

from decimal import Decimal
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import (
    AlcadaCreate, ContaCreate, DebitoCreate, FonteCreate, FornecedorCreate,
    NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_caixa as caixa
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as deb
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("pagaut")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos Autorizacao", admin_email=f"{slug}@t.local",
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
            "UPDATE pagamentos.parcela SET id_movimentacao=NULL WHERE tenant_id=:t",
            "DELETE FROM pagamentos.movimentacao_conta WHERE tenant_id=:t",
            "DELETE FROM pagamentos.parcela WHERE tenant_id=:t",
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
            tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Fornecedor Aut LTDA"))
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome="Conta Aut", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO", saldo_inicial=saldo_inicial))
    return forn, nat, conta


def _payload_debito(forn, nat, conta, *, valor="1000.00", parcelas=None):
    return DebitoCreate(
        id_fornecedor=forn.id, id_natureza=nat.id, id_conta=conta.id,
        valor_total=valor, competencia="2026-07", descricao="Compra de material",
        parcelas=parcelas or [ParcelaCreate(numero=1, valor=valor, vencimento="2026-08-01")],
    )


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


async def _debito_aprovado(engine, tenant_id, *, valor="1000.00", saldo_inicial="10000.00",
                           parcelas=None, base=None):
    """Débito RASCUNHO→ENVIADO→APROVADO com solicitante/aprovador distintos.
    Retorna (debito, solicitante_id, aprovador_id, conta). `base` reusa (forn, nat, conta)."""
    if base is None:
        forn, nat, conta = await _base(engine, tenant_id, saldo_inicial=saldo_inicial)
    else:
        forn, nat, conta = base
    solicitante = await _novo_usuario(engine, tenant_id, f"sol{uuid.uuid4().hex[:6]}")
    aprovador = await _novo_usuario(engine, tenant_id, f"apr{uuid.uuid4().hex[:6]}")
    async with _sm(engine)() as s:
        d = await deb.criar_debito(s, tenant_id=tenant_id, usuario_id=solicitante,
                                   payload=_payload_debito(forn, nat, conta, valor=valor,
                                                           parcelas=parcelas))
    async with _sm(engine)() as s:
        await deb.enviar_aprovacao(s, tenant_id=tenant_id, debito_id=d.id, usuario_id=solicitante)
    async with _sm(engine)() as s:
        d = await deb.aprovar(s, tenant_id=tenant_id, debito_id=d.id, usuario_id=aprovador)
    return d, solicitante, aprovador, conta


async def _dar_alcada(engine, tenant_id, usuario_id, *, valor_maximo="999999.00", id_natureza=None):
    async with _sm(engine)() as s:
        await cad.criar_alcada(s, tenant_id=tenant_id, payload=AlcadaCreate(
            id_usuario=usuario_id, id_natureza=id_natureza, valor_maximo=valor_maximo))


async def _autorizador_com_alcada(engine, tenant_id, *, valor_maximo="999999.00"):
    uid = await _novo_usuario(engine, tenant_id, f"aut{uuid.uuid4().hex[:6]}")
    await _dar_alcada(engine, tenant_id, uid, valor_maximo=valor_maximo)
    return uid


async def _debito_autorizado(engine, tenant_id, *, valor="1000.00", saldo_inicial="10000.00",
                             parcelas=None, base=None):
    """Débito RASCUNHO→...→APROVADO→AUTORIZADO. Retorna (debito, solicitante_id,
    aprovador_id, autorizador_id, conta)."""
    d, solicitante, aprovador, conta = await _debito_aprovado(
        engine, tenant_id, valor=valor, saldo_inicial=saldo_inicial, parcelas=parcelas, base=base)
    autorizador = await _autorizador_com_alcada(engine, tenant_id)
    async with _sm(engine)() as s:
        await aut.autorizar_lote(s, tenant_id=tenant_id, usuario_id=autorizador, debito_ids=[d.id])
    async with _sm(engine)() as s:
        d = await deb.obter_debito(s, tenant_id=tenant_id, debito_id=d.id)
    return d, solicitante, aprovador, autorizador, conta


async def test_autorizar_gera_op_e_muda_status(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, _conta = await _debito_aprovado(admin_engine, t.id, valor="1000.00")
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            op = await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador,
                                          debito_ids=[d.id])
        assert op.numero.startswith("OP-") and op.numero.endswith("-0001")
        assert op.valor_total == Decimal("1000.00")
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            hist = await deb.listar_historico(s, tenant_id=t.id, debito_id=d.id)
            debs_op = await aut.debitos_da_ordem(s, tenant_id=t.id, ordem_id=op.id)
        assert d2.status == "AUTORIZADO"
        assert hist[0].acao == "AUTORIZADO"
        assert [x.id for x in debs_op] == [d.id]
    finally:
        await _cleanup(admin_engine, t.id)


async def test_autorizar_sem_saldo_disponivel_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, _conta = await _debito_aprovado(
            admin_engine, t.id, valor="1000.00", saldo_inicial="100.00")
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador,
                                         debito_ids=[d.id])
            assert exc.value.status_code == 422
            assert "saldo" in exc.value.detail.lower()
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert d2.status == "APROVADO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_autorizar_acima_da_alcada_403(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, _conta = await _debito_aprovado(admin_engine, t.id, valor="1000.00")
        autorizador_com_alcada_baixa = await _autorizador_com_alcada(
            admin_engine, t.id, valor_maximo="500.00")
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador_com_alcada_baixa,
                                         debito_ids=[d.id])
            assert exc.value.status_code == 403
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert d2.status == "APROVADO"

        sem_alcada = await _novo_usuario(admin_engine, t.id, f"nal{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=sem_alcada,
                                         debito_ids=[d.id])
            assert exc.value.status_code == 403
        async with _sm(admin_engine)() as s:
            d3 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert d3.status == "APROVADO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_autorizar_por_solicitante_ou_aprovador_403(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, solicitante, aprovador, _conta = await _debito_aprovado(admin_engine, t.id, valor="1000.00")
        await _dar_alcada(admin_engine, t.id, solicitante)
        await _dar_alcada(admin_engine, t.id, aprovador)

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=solicitante,
                                         debito_ids=[d.id])
            assert exc.value.status_code == 403

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=aprovador,
                                         debito_ids=[d.id])
            assert exc.value.status_code == 403

        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert d2.status == "APROVADO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_comprometido_bloqueia_segunda_autorizacao(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        base = await _base(admin_engine, t.id, saldo_inicial="1000.00")
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)

        d_a, _sol_a, _apr_a, conta = await _debito_aprovado(
            admin_engine, t.id, valor="800.00", base=base)
        async with _sm(admin_engine)() as s:
            await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador,
                                     debito_ids=[d_a.id])

        async with _sm(admin_engine)() as s:
            saldo = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert saldo.comprometido == Decimal("800.00")
        assert saldo.disponivel == Decimal("200.00")

        d_b, _sol_b, _apr_b, _conta_b = await _debito_aprovado(
            admin_engine, t.id, valor="500.00", base=base)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador,
                                         debito_ids=[d_b.id])
            assert exc.value.status_code == 422
        async with _sm(admin_engine)() as s:
            d_b2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d_b.id)
        assert d_b2.status == "APROVADO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_autorizacao_em_lote_all_or_nothing(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        base = await _base(admin_engine, t.id, saldo_inicial="1000.00")
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)

        d_a, _sol_a, _apr_a, _conta_a = await _debito_aprovado(
            admin_engine, t.id, valor="600.00", base=base)
        d_b, _sol_b, _apr_b, _conta_b = await _debito_aprovado(
            admin_engine, t.id, valor="600.00", base=base)

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador,
                                         debito_ids=[d_a.id, d_b.id])
            assert exc.value.status_code == 422

        async with _sm(admin_engine)() as s:
            d_a2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d_a.id)
            d_b2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d_b.id)
        assert d_a2.status == "APROVADO"
        assert d_b2.status == "APROVADO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_pagar_parcela_deduz_saldo_e_finaliza_debito(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, conta = await _debito_aprovado(
            admin_engine, t.id, valor="1000.00",
            parcelas=[ParcelaCreate(numero=1, valor="600.00", vencimento="2026-08-01"),
                      ParcelaCreate(numero=2, valor="400.00", vencimento="2026-09-01")])
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        tesoureiro = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador, debito_ids=[d.id])
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
            p1 = await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                         parcela_id=parcelas[0].id, forma_pagamento="PIX")
        assert p1.status == "PAGA" and p1.id_movimentacao is not None
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            saldo = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert d2.status == "PAGO_PARCIAL"
        assert saldo.saldo_atual == Decimal("9400.00")
        assert saldo.comprometido == Decimal("400.00")
        async with _sm(admin_engine)() as s:
            await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                    parcela_id=parcelas[1].id, forma_pagamento="TED")
        async with _sm(admin_engine)() as s:
            d3 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            saldo2 = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert d3.status == "PAGO"
        assert saldo2.saldo_atual == Decimal("9000.00")
        assert saldo2.comprometido == Decimal("0")
    finally:
        await _cleanup(admin_engine, t.id)


async def test_pagar_parcela_de_debito_nao_autorizado_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, _conta = await _debito_aprovado(admin_engine, t.id, valor="1000.00")
        tesoureiro = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                        parcela_id=parcelas[0].id, forma_pagamento="PIX")
            assert exc.value.status_code == 409
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            p2 = (await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id))[0]
        assert d2.status == "APROVADO"
        assert p2.status == "A_PAGAR"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_pagar_parcela_ja_paga_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, _autorizador, _conta = await _debito_autorizado(admin_engine, t.id, valor="1000.00")
        tesoureiro = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
            await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                    parcela_id=parcelas[0].id, forma_pagamento="PIX")
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                        parcela_id=parcelas[0].id, forma_pagamento="PIX")
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_estornar_parcela_repoe_saldo_e_reabre(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, _autorizador, conta = await _debito_autorizado(
            admin_engine, t.id, valor="1000.00",
            parcelas=[ParcelaCreate(numero=1, valor="600.00", vencimento="2026-08-01"),
                      ParcelaCreate(numero=2, valor="400.00", vencimento="2026-09-01")])
        tesoureiro = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
            await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                    parcela_id=parcelas[0].id, forma_pagamento="PIX")
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
            await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                    parcela_id=parcelas[1].id, forma_pagamento="TED")
        async with _sm(admin_engine)() as s:
            d1 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert d1.status == "PAGO"

        async with _sm(admin_engine)() as s:
            p2_estornada = await aut.estornar_parcela(
                s, tenant_id=t.id, usuario_id=tesoureiro, parcela_id=parcelas[1].id,
                justificativa="Pagamento em duplicidade")
        assert p2_estornada.status == "A_PAGAR"
        assert p2_estornada.data_pagamento is None
        assert p2_estornada.forma_pagamento is None
        assert p2_estornada.id_movimentacao is None
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            saldo = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert d2.status == "PAGO_PARCIAL"
        assert saldo.saldo_atual == Decimal("9400.00")
        assert saldo.comprometido == Decimal("400.00")

        async with _sm(admin_engine)() as s:
            await aut.estornar_parcela(
                s, tenant_id=t.id, usuario_id=tesoureiro, parcela_id=parcelas[0].id,
                justificativa="Pagamento em duplicidade")
        async with _sm(admin_engine)() as s:
            d3 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            saldo2 = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert d3.status == "AUTORIZADO"
        assert saldo2.saldo_atual == Decimal("10000.00")
        assert saldo2.comprometido == Decimal("1000.00")
    finally:
        await _cleanup(admin_engine, t.id)
