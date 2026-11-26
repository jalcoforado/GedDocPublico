"""Previsão financeira de saída — 7/15/30/60/90 dias (fatia 5).

A prova que carrega o arquivo é `test_projecao_reconcilia_com_o_disponivel`.
O risco desta fatia não é exceção nem tela quebrada: é **contagem dupla**.
`disponivel` já é `saldo − comprometido − bloqueado`, e `comprometido` é a soma
das mesmas parcelas que a projeção percorre por vencimento. Quem projetar a
partir do disponível desconta cada obrigação duas vezes e mostra um caixa
futuro menor que o real — número errado com cara de certo, no lugar onde se
decide se dá para pagar.

A invariante que trava isso: com horizonte longo o bastante para cobrir todos
os vencimentos, `saldo_projetado` tem de bater **exatamente** com o disponível
consolidado.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Debito, Parcela
from app.services import pagamentos_caixa as caixa
from app.services import pagamentos_estados as est
from app.services import pagamentos_previsao as pv
from tests.test_pagamentos_f2_versionamento import _provisionar, _setup_debito, _sm


async def _autorizar_com_vencimento(engine, tenant_id: int, debito_id: int,
                                    vencimento: date) -> None:
    """Põe o débito com reserva ativa e a parcela vencendo na data pedida.

    A `id_conta_pagadora` é obrigatória aqui porque o fluxo real a grava no ato
    de autorizar (é a conta reservada, imutável depois). Sem ela o débito fica
    num estado que a produção não produz — e `comprometido_conta` o ignoraria,
    porque ela soma por conta pagadora. Foi exatamente o que o primeiro arreio
    deste arquivo fez, e a reconciliação acusou.
    """
    async with _sm(engine)() as s:
        from app.models import ContaBancaria
        conta_id = (await s.execute(select(ContaBancaria.id).where(
            ContaBancaria.tenant_id == tenant_id,
            ContaBancaria.excluido.is_(False)))).scalars().first()
        d = (await s.execute(select(Debito).where(Debito.id == debito_id))).scalar_one()
        d.situacao_tramitacao = est.AUTORIZADA
        d.id_conta_pagadora = conta_id
        parcelas = (await s.execute(select(Parcela).where(
            Parcela.id_debito == debito_id))).scalars().all()
        for p in parcelas:
            p.vencimento = vencimento
            p.status = "A_PAGAR"
        await s.commit()


@pytest.mark.asyncio
async def test_projecao_reconcilia_com_o_disponivel(admin_engine):
    """Sem contagem dupla: base − tudo que vence == disponível consolidado."""
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _autorizar_com_vencimento(admin_engine, tenant.id, debito.id,
                                    date.today() + timedelta(days=10))

    async with _sm(admin_engine)() as s:
        out = await pv.montar_previsao(s, tenant_id=tenant.id)
        painel = await caixa.painel_caixa(s, tenant_id=tenant.id)

    disponivel = sum((c.disponivel for c in painel), Decimal("0"))
    # O vencimento está em D+10, dentro de todas as janelas de 15 dias ou mais.
    noventa = out.horizontes[-1]
    assert noventa.saldo_projetado == disponivel, (
        "projeção divergiu do disponível — provável contagem dupla do comprometido")


@pytest.mark.asyncio
async def test_janelas_sao_cumulativas(admin_engine):
    """30 dias inclui o que vence em 7. Janela que não acumula faria o gestor
    somar as janelas e inventar uma dívida que não existe."""
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _autorizar_com_vencimento(admin_engine, tenant.id, debito.id,
                                    date.today() + timedelta(days=5))

    async with _sm(admin_engine)() as s:
        out = await pv.montar_previsao(s, tenant_id=tenant.id)

    valores = [h.vence_acumulado for h in out.horizontes]
    assert valores == sorted(valores), "acumulado não pode diminuir ao longo do tempo"
    assert all(h.vence_acumulado == debito.valor_total for h in out.horizontes), (
        "vencimento em D+5 tem de aparecer em TODAS as janelas")
    # A soma das janelas é o acumulado final, não o dobro dele.
    assert sum((h.vence_na_janela for h in out.horizontes), Decimal("0")) == \
        out.horizontes[-1].vence_acumulado


@pytest.mark.asyncio
async def test_vencimento_distante_nao_entra_nas_janelas_curtas(admin_engine):
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _autorizar_com_vencimento(admin_engine, tenant.id, debito.id,
                                    date.today() + timedelta(days=75))

    async with _sm(admin_engine)() as s:
        out = await pv.montar_previsao(s, tenant_id=tenant.id)

    por_dias = {h.dias: h for h in out.horizontes}
    assert por_dias[7].vence_acumulado == Decimal("0")
    assert por_dias[30].vence_acumulado == Decimal("0")
    assert por_dias[90].vence_acumulado == debito.valor_total


@pytest.mark.asyncio
async def test_parcela_vencida_entra_em_todas_as_janelas(admin_engine):
    """Obrigação vencida e não paga continua sendo dinheiro que vai sair.
    Deixá-la fora mostraria um caixa futuro melhor do que é."""
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _autorizar_com_vencimento(admin_engine, tenant.id, debito.id,
                                    date.today() - timedelta(days=20))

    async with _sm(admin_engine)() as s:
        out = await pv.montar_previsao(s, tenant_id=tenant.id)

    assert out.vencidas_qtd == 1
    assert out.vencidas_valor == debito.valor_total
    assert all(h.vence_acumulado == debito.valor_total for h in out.horizontes)


@pytest.mark.asyncio
async def test_debito_nao_autorizado_nao_entra_na_previsao(admin_engine):
    """Solicitação ainda em rascunho não é obrigação: não há o que projetar."""
    tenant, solic = await _provisionar(admin_engine)
    await _setup_debito(admin_engine, tenant.id, solic)

    async with _sm(admin_engine)() as s:
        out = await pv.montar_previsao(s, tenant_id=tenant.id)

    assert all(h.vence_acumulado == Decimal("0") for h in out.horizontes)
    assert out.vencidas_qtd == 0


@pytest.mark.asyncio
async def test_conta_que_nao_cobre_os_proprios_vencimentos_e_listada(admin_engine):
    """Saldo de uma conta não paga obrigação de outra — total saudável pode
    esconder conta no vermelho."""
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)

    async with _sm(admin_engine)() as s:
        from app.models import ContaBancaria
        conta_id = (await s.execute(select(ContaBancaria.id).where(
            ContaBancaria.tenant_id == tenant.id,
            ContaBancaria.excluido.is_(False)))).scalars().first()
        d = (await s.execute(select(Debito).where(Debito.id == debito.id))).scalar_one()
        d.situacao_tramitacao = est.AUTORIZADA
        d.id_conta_pagadora = conta_id
        # Acima do saldo inicial do arreio (10.000).
        for p in (await s.execute(select(Parcela).where(
                Parcela.id_debito == debito.id))).scalars().all():
            p.valor = Decimal("50000.00")
            p.vencimento = date.today() + timedelta(days=20)
            p.status = "A_PAGAR"
        await s.commit()

    async with _sm(admin_engine)() as s:
        out = await pv.montar_previsao(s, tenant_id=tenant.id)

    assert len(out.contas_em_risco) == 1
    c = out.contas_em_risco[0]
    assert c.falta > 0
    assert c.falta == -c.saldo_projetado


@pytest.mark.asyncio
async def test_declara_que_nao_considera_receita(admin_engine):
    """A tela é obrigada a dizer o que a projeção não inclui."""
    tenant, _solic = await _provisionar(admin_engine)
    async with _sm(admin_engine)() as s:
        out = await pv.montar_previsao(s, tenant_id=tenant.id)
    assert out.considera_receita is False
    assert out.apurado_em is not None
