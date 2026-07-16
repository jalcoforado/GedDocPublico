"""Pagamentos — Liberação de pagamento (2º ato do rito, R2b): `liberar_parcelas`
(lote all-or-nothing), `revogar_liberacao`, e os guards novos de `pagar_parcela`/
`estornar_parcela` em `services/pagamentos_autorizacao.py`. Mesmo padrão de
`test_pagamentos_autorizacao.py`; helpers duplicados para independência.
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
    slug = _slug("pagliber")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos Liberacao", admin_email=f"{slug}@t.local",
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
            tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Fornecedor Liber LTDA"))
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome="Conta Liber", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
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
                             parcelas=None, base=None, autorizador=None):
    """Débito RASCUNHO→...→APROVADO→AUTORIZADO. Retorna (debito, solicitante_id,
    aprovador_id, autorizador_id, conta)."""
    d, solicitante, aprovador, conta = await _debito_aprovado(
        engine, tenant_id, valor=valor, saldo_inicial=saldo_inicial, parcelas=parcelas, base=base)
    if autorizador is None:
        autorizador = await _autorizador_com_alcada(engine, tenant_id)
    async with _sm(engine)() as s:
        await aut.autorizar_lote(s, tenant_id=tenant_id, usuario_id=autorizador, debito_ids=[d.id])
    async with _sm(engine)() as s:
        d = await deb.obter_debito(s, tenant_id=tenant_id, debito_id=d.id)
    return d, solicitante, aprovador, autorizador, conta


# ============================ liberar_parcelas ==================================
async def test_liberar_duas_parcelas_de_debitos_distintos(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        d_a, _sa, _aa, _autA, _conta_a = await _debito_autorizado(
            admin_engine, t.id, valor="500.00", autorizador=autorizador)
        d_b, _sb, _ab, _autB, _conta_b = await _debito_autorizado(
            admin_engine, t.id, valor="700.00", autorizador=autorizador)
        async with _sm(admin_engine)() as s:
            p_a = (await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d_a.id))[0]
            p_b = (await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d_b.id))[0]

        async with _sm(admin_engine)() as s:
            liberadas = await aut.liberar_parcelas(
                s, tenant_id=t.id, usuario_id=autorizador, parcela_ids=[p_a.id, p_b.id])
        assert {p.status for p in liberadas} == {"LIBERADA"}
        for p in liberadas:
            assert p.data_liberacao is not None
            assert p.id_usuario_liberacao == autorizador

        for d in (d_a, d_b):
            async with _sm(admin_engine)() as s:
                hist = await deb.listar_historico(s, tenant_id=t.id, debito_id=d.id)
            liberados = [h for h in hist if h.acao == "LIBERADO"]
            assert len(liberados) == 1
            assert "1" in liberados[0].justificativa
    finally:
        await _cleanup(admin_engine, t.id)


async def test_liberar_parcela_de_debito_nao_autorizado_409_all_or_nothing(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        base = await _base(admin_engine, t.id)
        d_autorizado, _s1, _a1, _aut1, _c1 = await _debito_autorizado(
            admin_engine, t.id, valor="500.00", base=base, autorizador=autorizador)
        d_aprovado, _s2, _a2, _c2 = await _debito_aprovado(
            admin_engine, t.id, valor="300.00", base=base)

        async with _sm(admin_engine)() as s:
            p_ok = (await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d_autorizado.id))[0]
            p_bloqueada = (await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d_aprovado.id))[0]

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.liberar_parcelas(
                    s, tenant_id=t.id, usuario_id=autorizador,
                    parcela_ids=[p_ok.id, p_bloqueada.id])
            assert exc.value.status_code == 409

        async with _sm(admin_engine)() as s:
            p_ok2 = (await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d_autorizado.id))[0]
        assert p_ok2.status == "A_PAGAR"
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ pagar_parcela exige LIBERADA =======================
async def test_pagar_parcela_a_pagar_409_depois_libera_e_paga(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, autorizador, _conta = await _debito_autorizado(admin_engine, t.id, valor="1000.00")
        tesoureiro = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcela = (await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id))[0]

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                        parcela_id=parcela.id, forma_pagamento="PIX")
            assert exc.value.status_code == 409
            assert "liberada" in exc.value.detail.lower()

        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=autorizador,
                                       parcela_ids=[parcela.id])
        async with _sm(admin_engine)() as s:
            paga = await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                           parcela_id=parcela.id, forma_pagamento="PIX")
        assert paga.status == "PAGA"
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ revogar_liberacao ==================================
async def test_revogar_liberacao_volta_a_pagar_e_bloqueia_paga(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, autorizador, _conta = await _debito_autorizado(admin_engine, t.id, valor="1000.00")
        tesoureiro = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcela = (await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id))[0]
        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=autorizador,
                                       parcela_ids=[parcela.id])

        async with _sm(admin_engine)() as s:
            revogada = await aut.revogar_liberacao(
                s, tenant_id=t.id, usuario_id=autorizador, parcela_id=parcela.id,
                justificativa="Liberação por engano")
        assert revogada.status == "A_PAGAR"
        assert revogada.data_liberacao is None
        assert revogada.id_usuario_liberacao is None
        assert revogada.data_prevista_pagamento is None

        async with _sm(admin_engine)() as s:
            hist = await deb.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        assert any(h.acao == "LIBERACAO_REVOGADA" for h in hist)

        # revogar parcela paga → 409
        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=autorizador,
                                       parcela_ids=[parcela.id])
        async with _sm(admin_engine)() as s:
            await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                    parcela_id=parcela.id, forma_pagamento="PIX")
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.revogar_liberacao(
                    s, tenant_id=t.id, usuario_id=autorizador, parcela_id=parcela.id,
                    justificativa="Tentativa inválida")
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ estornar_parcela reverte p/ A_PAGAR ================
async def test_estornar_parcela_paga_volta_a_pagar_nao_liberada(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, autorizador, _conta = await _debito_autorizado(admin_engine, t.id, valor="1000.00")
        tesoureiro = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcela = (await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id))[0]
        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=autorizador,
                                       parcela_ids=[parcela.id])
        async with _sm(admin_engine)() as s:
            await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                    parcela_id=parcela.id, forma_pagamento="PIX")

        async with _sm(admin_engine)() as s:
            estornada = await aut.estornar_parcela(
                s, tenant_id=t.id, usuario_id=tesoureiro, parcela_id=parcela.id,
                justificativa="Pagamento em duplicidade")
        assert estornada.status == "A_PAGAR"
        assert estornada.data_liberacao is None
        assert estornada.id_usuario_liberacao is None
        assert estornada.data_prevista_pagamento is None

        # re-pagar exige re-liberar
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                        parcela_id=parcela.id, forma_pagamento="PIX")
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ comprometido inclui LIBERADA =======================
async def test_comprometido_inclui_liberada(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, autorizador, conta = await _debito_autorizado(admin_engine, t.id, valor="1000.00")
        async with _sm(admin_engine)() as s:
            saldo_antes = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert saldo_antes.comprometido == Decimal("1000.00")

        async with _sm(admin_engine)() as s:
            parcela = (await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id))[0]
        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=autorizador,
                                       parcela_ids=[parcela.id])

        async with _sm(admin_engine)() as s:
            saldo_depois = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert saldo_depois.comprometido == Decimal("1000.00")
        assert saldo_depois.disponivel == saldo_antes.disponivel
    finally:
        await _cleanup(admin_engine, t.id)
