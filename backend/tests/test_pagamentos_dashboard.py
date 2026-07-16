"""Dashboard financeiro de Pagamentos — agregações de `services/pagamentos_dashboard.py`.
Cenário mínimo (1 conta saldo 10000, 1 entrada 2000 no mês corrente, 1 débito com
2 parcelas: 600 paga no mês corrente, 400 a pagar vencida ontem). Mesmo padrão de
`test_pagamentos_autorizacao.py`; helpers duplicados para independência."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import (
    AlcadaCreate, ContaCreate, DebitoCreate, FonteCreate, FornecedorCreate, MovimentacaoCreate,
    NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_caixa as caixa
from app.services import pagamentos_dashboard as dash
from app.services import pagamentos_debitos as deb
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("pagdash")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos Dashboard", admin_email=f"{slug}@t.local",
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
    async with _sm(engine)() as s:
        forn = await cad.criar_fornecedor(s, tenant_id=tenant_id, payload=FornecedorCreate(
            tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Fornecedor Dash LTDA"))
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome="Conta Dash", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO", saldo_inicial=saldo_inicial))
    return forn, nat, conta


def _payload_debito(forn, nat, conta, *, valor="1000.00", parcelas=None):
    return DebitoCreate(
        id_fornecedor=forn.id, id_natureza=nat.id, id_conta=conta.id,
        valor_total=valor, competencia="2026-07", descricao="Compra de material",
        parcelas=parcelas or [ParcelaCreate(numero=1, valor=valor, vencimento="2026-08-01")],
    )


async def _novo_usuario(engine, tenant_id, sufixo):
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


async def _cenario(engine, tenant_id):
    """1 conta saldo 10000, 1 entrada 2000 no mês corrente, 1 débito 2 parcelas
    (600 paga no mês corrente, 400 a pagar vencida ontem). Retorna (debito, conta)."""
    hoje = date.today()
    ontem = hoje - timedelta(days=1)
    d, _sol, _apr, conta = await _debito_aprovado(
        engine, tenant_id, valor="1000.00",
        parcelas=[ParcelaCreate(numero=1, valor="600.00", vencimento=hoje.isoformat()),
                  ParcelaCreate(numero=2, valor="400.00", vencimento=ontem.isoformat())])
    autorizador = await _autorizador_com_alcada(engine, tenant_id)
    async with _sm(engine)() as s:
        await aut.autorizar_lote(s, tenant_id=tenant_id, usuario_id=autorizador, debito_ids=[d.id])
    tesoureiro = await _novo_usuario(engine, tenant_id, f"tes{uuid.uuid4().hex[:6]}")
    async with _sm(engine)() as s:
        parcelas = await deb.listar_parcelas(s, tenant_id=tenant_id, debito_id=d.id)
        p1 = next(p for p in parcelas if p.valor == Decimal("600.00"))
        await aut.pagar_parcela(s, tenant_id=tenant_id, usuario_id=tesoureiro,
                                parcela_id=p1.id, forma_pagamento="PIX",
                                data_pagamento=hoje)
    async with _sm(engine)() as s:
        await caixa.lancar_movimentacao(s, tenant_id=tenant_id, usuario_id=tesoureiro,
                                        payload=MovimentacaoCreate(
                                            id_conta=conta.id, tipo="ENTRADA", valor="2000.00",
                                            origem="RECEITA", data=hoje))
    async with _sm(engine)() as s:
        d = await deb.obter_debito(s, tenant_id=tenant_id, debito_id=d.id)
    return d, conta


async def test_kpis(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, conta = await _cenario(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            out = await dash.montar_dashboard(s, tenant_id=t.id)
        k = out.kpis
        assert k.saldo_total == Decimal("11400.00")
        assert k.comprometido_total == Decimal("400.00")
        assert k.disponivel_total == Decimal("11000.00")
        assert k.pago_no_mes == Decimal("600.00")
        assert k.vencidas_qtd == 1
        assert k.vencidas_valor == Decimal("400.00")
    finally:
        await _cleanup(admin_engine, t.id)


async def test_fluxo_mensal(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        await _cenario(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            out = await dash.montar_dashboard(s, tenant_id=t.id, meses=12)
        assert len(out.fluxo_mensal) == 12
        mes_atual = date.today().strftime("%Y-%m")
        item = next(i for i in out.fluxo_mensal if i.mes == mes_atual)
        assert item.entradas == Decimal("2000.00")
        assert item.saidas == Decimal("600.00")
        outros = [i for i in out.fluxo_mensal if i.mes != mes_atual]
        for i in outros:
            assert i.entradas == Decimal("0") and i.saidas == Decimal("0")
    finally:
        await _cleanup(admin_engine, t.id)


async def test_por_natureza_e_fonte(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        await _cenario(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            out = await dash.montar_dashboard(s, tenant_id=t.id)
        assert len(out.por_natureza) == 1
        assert out.por_natureza[0].valor == Decimal("600.00")
        assert len(out.por_fonte) == 1
        assert out.por_fonte[0].valor == Decimal("600.00")
    finally:
        await _cleanup(admin_engine, t.id)


async def test_maiores_e_alertas(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, conta = await _cenario(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            out = await dash.montar_dashboard(s, tenant_id=t.id)
        assert any(m.id == d.id and m.status == "PAGO_PARCIAL" for m in out.maiores_debitos)
        vencidas = out.alertas.parcelas_vencidas
        assert len(vencidas) == 1
        assert vencidas[0].id_debito == d.id
        assert vencidas[0].dias_atraso == 1
    finally:
        await _cleanup(admin_engine, t.id)
