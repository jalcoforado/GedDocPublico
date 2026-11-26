"""Painel executivo (fatia 2): despesa por secretaria, fornecedor e contrato.

A propriedade que estes testes existem para travar é **a reconciliação**: as
três dimensões novas medem a MESMA coisa que os gráficos antigos — o que saiu
da conta como pagamento no período. Se alguém trocar a medida de uma delas
(valor do débito em vez do pago, por exemplo), dois gráficos do mesmo painel
passam a discordar sobre quanto a prefeitura gastou, e o leitor não tem como
saber qual acreditar. O sintoma não é exceção nem tela quebrada: é um número
errado com aparência de certo, que é o defeito mais caro de um painel.

Arreio emprestado de `test_pagamentos_f2_versionamento.py`.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import ContaBancaria, MovimentacaoConta
from app.services import pagamentos_dashboard as dash
from tests.test_pagamentos_f2_versionamento import _provisionar, _setup_debito, _sm


async def _pagar(engine, tenant_id: int, debito, valor: str, quando: date | None = None):
    """Simula a saída de caixa que uma baixa gera, que é o que o painel mede."""
    async with _sm(engine)() as s:
        conta_id = (await s.execute(
            select(ContaBancaria.id).where(ContaBancaria.tenant_id == tenant_id,
                                           ContaBancaria.excluido.is_(False))
        )).scalars().first()
        s.add(MovimentacaoConta(
            tenant_id=tenant_id, id_conta=conta_id, tipo="SAIDA",
            valor=Decimal(valor), origem="PAGAMENTO", id_debito=debito.id,
            data=quando or datetime.utcnow().date(), criado_em=datetime.utcnow(),
        ))
        await s.commit()
    return conta_id


def _total(itens) -> Decimal:
    return sum((i.valor for i in itens), Decimal("0"))


@pytest.mark.asyncio
async def test_as_tres_dimensoes_novas_reconciliam_entre_si(admin_engine):
    """Secretaria, fornecedor e contrato somam o mesmo total — e o mesmo que
    natureza e fonte, que já existiam."""
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    await _pagar(admin_engine, tenant.id, debito, "400.00")
    await _pagar(admin_engine, tenant.id, debito, "350.00")

    async with _sm(admin_engine)() as s:
        out = await dash.montar_dashboard(s, tenant_id=tenant.id, meses=12)

    esperado = Decimal("750.00")
    assert _total(out.por_secretaria) == esperado
    assert _total(out.top_fornecedores) == esperado
    assert _total(out.top_contratos) == esperado
    # As duas que já existiam, para a prova valer como reconciliação do painel
    # inteiro e não só das dimensões novas.
    assert _total(out.por_natureza) == esperado
    assert _total(out.por_fonte) == esperado


@pytest.mark.asyncio
async def test_despesa_por_secretaria_usa_a_unidade_do_debito(admin_engine):
    """A unidade vem de `Debito.id_unidade` — o campo que a F1 tornou NOT NULL
    e que é o que torna esta agregação possível."""
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    await _pagar(admin_engine, tenant.id, debito, "123.00")

    async with _sm(admin_engine)() as s:
        out = await dash.montar_dashboard(s, tenant_id=tenant.id, meses=12)

    assert len(out.por_secretaria) == 1
    assert out.por_secretaria[0].valor == Decimal("123.00")
    assert out.por_secretaria[0].descricao  # nome da unidade, não vazio


@pytest.mark.asyncio
async def test_despesa_sem_contrato_aparece_no_ranking_de_contratos(admin_engine):
    """Sem esta linha o ranking não fecha com o total pago, e quem soma as
    barras conclui que a prefeitura gastou menos do que gastou."""
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    # Tira o contrato do débito: vira despesa avulsa, o caso que o outerjoin cobre.
    async with _sm(admin_engine)() as s:
        from app.models import Debito
        d = (await s.execute(select(Debito).where(Debito.id == debito.id))).scalar_one()
        d.id_contrato = None
        await s.commit()

    await _pagar(admin_engine, tenant.id, debito, "500.00")

    async with _sm(admin_engine)() as s:
        out = await dash.montar_dashboard(s, tenant_id=tenant.id, meses=12)

    rotulos = [i.codigo for i in out.top_contratos]
    assert "Sem contrato" in rotulos, rotulos
    assert _total(out.top_contratos) == Decimal("500.00")


@pytest.mark.asyncio
async def test_painel_declara_quando_foi_apurado_e_desde_quando_conta(admin_engine):
    """§5.1 do brief: todo indicador diz de quando é. Sem isso o gestor não
    sabe se está olhando o dado de agora ou o de ontem."""
    tenant, _solicitante_id = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        out = await dash.montar_dashboard(s, tenant_id=tenant.id, meses=12)

    assert out.apurado_em is not None
    assert out.periodo_inicio is not None
    assert out.periodo_inicio <= datetime.utcnow().date()


@pytest.mark.asyncio
async def test_tenant_sem_pagamento_devolve_listas_vazias_e_nao_estoura(admin_engine):
    """Prefeitura recém-provisionada abre o painel no primeiro dia."""
    tenant, _solicitante_id = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        out = await dash.montar_dashboard(s, tenant_id=tenant.id, meses=12)

    assert out.por_secretaria == []
    assert out.top_fornecedores == []
    assert out.top_contratos == []


@pytest.mark.asyncio
async def test_pagamento_de_outro_tenant_nao_entra(admin_engine):
    """Isolamento por tenant nas agregações novas — a falha aqui seria dado de
    uma prefeitura aparecendo no painel de outra."""
    tenant_a, solic_a = await _provisionar(admin_engine)
    debito_a = await _setup_debito(admin_engine, tenant_a.id, solic_a)
    await _pagar(admin_engine, tenant_a.id, debito_a, "900.00")

    tenant_b, solic_b = await _provisionar(admin_engine)
    debito_b = await _setup_debito(admin_engine, tenant_b.id, solic_b)
    await _pagar(admin_engine, tenant_b.id, debito_b, "111.00")

    async with _sm(admin_engine)() as s:
        out_b = await dash.montar_dashboard(s, tenant_id=tenant_b.id, meses=12)

    assert _total(out_b.por_secretaria) == Decimal("111.00")
    assert _total(out_b.top_fornecedores) == Decimal("111.00")
    assert _total(out_b.top_contratos) == Decimal("111.00")
