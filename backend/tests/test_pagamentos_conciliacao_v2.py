"""Pagamentos v2.0 Onda B — conciliação bancária (RF-EXT-01..10, RN-11/RN-14).

Fluxo: paga uma parcela → importa extrato com o débito correspondente → sugere e
efetua a baixa → o débito vira CONCILIADO e o saldo conciliado reflete a saída.
Guardas: RN-11 (conta do extrato) e RN-14 (sem dupla baixa).
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import (
    AlcadaCreate, ContaCreate, DebitoCreate, FonteCreate, FornecedorCreate,
    GrupoAutorizacaoIn, ImportarExtratoIn, NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_caixa as caixa
from app.services import pagamentos_conciliacao as conc
from app.services import pagamentos_debitos as deb
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _doc() -> str:
    return str(uuid.uuid4().int)[:14]


async def _provisionar(engine):
    slug = f"pagconc{uuid.uuid4().hex[:8]}"
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Conc", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico")
    return tenant


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.conciliacao WHERE tenant_id=:t",
            "DELETE FROM pagamentos.lancamento_extrato WHERE tenant_id=:t",
            "DELETE FROM pagamentos.extrato WHERE tenant_id=:t",
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


async def _novo_usuario(engine, tenant_id, sufixo):
    async with _sm(engine)() as s:
        r = await s.execute(text(
            """INSERT INTO utils.usuario (tenant_id, nome, email, cpf, senha, ativo, excluido, data_criacao)
               VALUES (:t, :n, :e, :c, 'x', true, false, NOW()) RETURNING id"""),
            {"t": tenant_id, "n": f"U {sufixo}", "e": f"{sufixo}@t.local", "c": uuid.uuid4().hex[:11]})
        uid = r.scalar_one(); await s.commit()
    return uid


async def _base(engine, tenant_id, *, saldo="10000.00"):
    async with _sm(engine)() as s:
        forn = await cad.criar_fornecedor(s, tenant_id=tenant_id, payload=FornecedorCreate(
            tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Forn"))
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Mat"))
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome="Conta", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO", saldo_inicial=saldo))
    return forn, nat, fonte, conta


async def _debito_pago(engine, tenant_id, forn, nat, fonte, conta, *, valor="1000.00", venc="2026-08-01"):
    """Percorre o rito completo até PAGO. Retorna (debito, parcela, movimentacao)."""
    sol = await _novo_usuario(engine, tenant_id, f"s{uuid.uuid4().hex[:6]}")
    val = await _novo_usuario(engine, tenant_id, f"v{uuid.uuid4().hex[:6]}")
    autor = await _novo_usuario(engine, tenant_id, f"au{uuid.uuid4().hex[:6]}")
    tes = await _novo_usuario(engine, tenant_id, f"t{uuid.uuid4().hex[:6]}")
    async with _sm(engine)() as s:
        d = await deb.criar_debito(s, tenant_id=tenant_id, usuario_id=sol, payload=DebitoCreate(
            id_fornecedor=forn.id, id_natureza=nat.id, id_fonte_recursos=fonte.id,
            valor_total=valor, competencia="2026-07", descricao="x", numero_ne="NE-1",
            parcelas=[ParcelaCreate(numero=1, valor=valor, vencimento=venc)]))
    async with _sm(engine)() as s:
        await deb.enviar_validacao(s, tenant_id=tenant_id, debito_id=d.id, usuario_id=sol)
    async with _sm(engine)() as s:
        await deb.confirmar_liquidacao(s, tenant_id=tenant_id, debito_id=d.id, usuario_id=val)
    async with _sm(engine)() as s:
        await deb.validar(s, tenant_id=tenant_id, debito_id=d.id, usuario_id=val)
    async with _sm(engine)() as s:
        await deb.encaminhar(s, tenant_id=tenant_id, debito_id=d.id, usuario_id=val)
    async with _sm(engine)() as s:
        await cad.criar_alcada(s, tenant_id=tenant_id, payload=AlcadaCreate(
            id_usuario=autor, id_natureza=None, valor_maximo="9999999.00"))
    async with _sm(engine)() as s:
        await aut.autorizar_lote(s, tenant_id=tenant_id, usuario_id=autor, grupos=[
            GrupoAutorizacaoIn(id_fonte=fonte.id, id_conta_pagadora=conta.id, debito_ids=[d.id])])
    async with _sm(engine)() as s:
        parcelas = await deb.listar_parcelas(s, tenant_id=tenant_id, debito_id=d.id)
        await aut.liberar_parcelas(s, tenant_id=tenant_id, usuario_id=autor,
                                   parcela_ids=[parcelas[0].id])
    async with _sm(engine)() as s:
        # `pagar_parcela` é chamada direta de service (sem coerção do Pydantic):
        # `data_pagamento` precisa ser `date`, não a string do vencimento.
        p = await aut.pagar_parcela(s, tenant_id=tenant_id, usuario_id=tes,
                                    parcela_id=parcelas[0].id, forma_pagamento="PIX",
                                    data_pagamento=date.fromisoformat(venc))
    return d, p


def _csv(valor="1000.00", data="2026-08-01", tipo="DEBITO"):
    return (f"data;historico;documento;favorecido;valor;tipo\n"
            f"{data};Pagamento fornecedor;DOC1;Forn;{valor};{tipo}\n")


async def test_conciliacao_completa_debito_vira_conciliado(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta = await _base(admin_engine, t.id)
        d, _p = await _debito_pago(admin_engine, t.id, forn, nat, fonte, conta, valor="1000.00")
        uid = await _novo_usuario(admin_engine, t.id, f"c{uuid.uuid4().hex[:6]}")
        # importa extrato com um débito de R$ 1000 em 2026-08-01
        async with _sm(admin_engine)() as s:
            ex = await conc.importar_extrato(s, tenant_id=t.id, usuario_id=uid, payload=ImportarExtratoIn(
                id_conta=conta.id, nome_arquivo="ext.csv", conteudo=_csv()))
        assert ex.qtd_lancamentos == 1 and ex.status_processamento == "PROCESSADO"
        # reimportar o mesmo arquivo → 409
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await conc.importar_extrato(s, tenant_id=t.id, usuario_id=uid, payload=ImportarExtratoIn(
                    id_conta=conta.id, nome_arquivo="ext.csv", conteudo=_csv()))
            assert exc.value.status_code == 409
        # sugestão EXATA
        async with _sm(admin_engine)() as s:
            sug = await conc.sugerir_baixas(s, tenant_id=t.id, id_extrato=ex.id)
        assert len(sug) == 1 and sug[0].tipo_correspondencia == "EXATA"
        # baixa automática concilia e leva o débito a CONCILIADO
        async with _sm(admin_engine)() as s:
            n = await conc.baixa_automatica(s, tenant_id=t.id, id_extrato=ex.id, usuario_id=uid)
        assert n == 1
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            saldo = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
            lancs = await conc.listar_lancamentos(s, tenant_id=t.id, id_extrato=ex.id)
        assert d2.status == "CONCILIADO"
        assert lancs[0].conciliado is True
        # saldo conciliado = inicial 10000 − 1000 pago conciliado
        assert saldo.saldo_conciliado == Decimal("9000.00")
    finally:
        await _cleanup(admin_engine, t.id)


async def test_conciliar_movimentacao_de_outra_conta_bloqueia_rn11(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta = await _base(admin_engine, t.id)
        _f2, _n2, fonte2, conta2 = await _base(admin_engine, t.id)
        d, p = await _debito_pago(admin_engine, t.id, forn, nat, fonte, conta, valor="1000.00")
        uid = await _novo_usuario(admin_engine, t.id, f"c{uuid.uuid4().hex[:6]}")
        # extrato importado na CONTA2, mas a movimentação do pagamento é da conta1
        async with _sm(admin_engine)() as s:
            ex = await conc.importar_extrato(s, tenant_id=t.id, usuario_id=uid, payload=ImportarExtratoIn(
                id_conta=conta2.id, nome_arquivo="ext2.csv", conteudo=_csv()))
            lancs = await conc.listar_lancamentos(s, tenant_id=t.id, id_extrato=ex.id)
            mov_id = (await s.execute(text(
                "SELECT id_movimentacao FROM pagamentos.parcela WHERE id=:p"), {"p": p.id})).scalar_one()
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await conc.conciliar(s, tenant_id=t.id, id_lancamento=lancs[0].id,
                                     id_movimentacao=mov_id, usuario_id=uid)
            assert exc.value.status_code == 422
            assert "conta do extrato" in exc.value.detail.lower()
    finally:
        await _cleanup(admin_engine, t.id)


async def test_dupla_baixa_bloqueada_rn14(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta = await _base(admin_engine, t.id)
        d, p = await _debito_pago(admin_engine, t.id, forn, nat, fonte, conta, valor="1000.00")
        uid = await _novo_usuario(admin_engine, t.id, f"c{uuid.uuid4().hex[:6]}")
        # dois lançamentos iguais no extrato
        csv = (_csv() + "2026-08-01;Pagamento fornecedor;DOC2;Forn;1000.00;DEBITO\n")
        async with _sm(admin_engine)() as s:
            ex = await conc.importar_extrato(s, tenant_id=t.id, usuario_id=uid, payload=ImportarExtratoIn(
                id_conta=conta.id, nome_arquivo="ext.csv", conteudo=csv))
            lancs = await conc.listar_lancamentos(s, tenant_id=t.id, id_extrato=ex.id)
            mov_id = (await s.execute(text(
                "SELECT id_movimentacao FROM pagamentos.parcela WHERE id=:p"), {"p": p.id})).scalar_one()
        async with _sm(admin_engine)() as s:
            await conc.conciliar(s, tenant_id=t.id, id_lancamento=lancs[0].id,
                                 id_movimentacao=mov_id, usuario_id=uid)
        # a mesma movimentação não pode ser conciliada de novo (RN-14)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await conc.conciliar(s, tenant_id=t.id, id_lancamento=lancs[1].id,
                                     id_movimentacao=mov_id, usuario_id=uid)
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)
