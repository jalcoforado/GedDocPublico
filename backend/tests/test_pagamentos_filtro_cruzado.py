"""Exploração interativa do painel — filtro cruzado (fatia 8, §9.2 do brief).

A propriedade que carrega o arquivo é **o recorte valer para todas as
agregações ao mesmo tempo**. Se valesse para uns gráficos e não para outros, a
tela mostraria barras de escopos diferentes lado a lado, somando coisas que não
se somam — e o leitor não teria como perceber, porque todos os gráficos
continuariam parecendo corretos isoladamente.

A segunda propriedade: o que NÃO é recortável tem de continuar consolidado e
ser declarado. Saldo é da conta bancária; não existe "saldo da Secretaria de
Saúde". Filtrar o saldo por secretaria inventaria um número.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import ContaBancaria, Debito, MovimentacaoConta
from app.services import pagamentos_dashboard as dash
from tests.test_pagamentos_f2_versionamento import _provisionar, _setup_debito, _sm


async def _pagar(engine, tenant_id: int, debito, valor: str):
    async with _sm(engine)() as s:
        conta_id = (await s.execute(select(ContaBancaria.id).where(
            ContaBancaria.tenant_id == tenant_id,
            ContaBancaria.excluido.is_(False)))).scalars().first()
        s.add(MovimentacaoConta(
            tenant_id=tenant_id, id_conta=conta_id, tipo="SAIDA", valor=Decimal(valor),
            origem="PAGAMENTO", id_debito=debito.id, data=datetime.utcnow().date(),
            criado_em=datetime.utcnow()))
        await s.commit()


def _soma(itens) -> Decimal:
    return sum((i.valor for i in itens), Decimal("0"))


@pytest.mark.asyncio
async def test_sem_filtro_o_painel_nao_declara_recorte(admin_engine):
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _pagar(admin_engine, tenant.id, debito, "700.00")

    async with _sm(admin_engine)() as s:
        out = await dash.montar_dashboard(s, tenant_id=tenant.id, meses=12)

    assert out.filtros_ativos == {}
    assert out.total_filtrado == Decimal("700.00")


@pytest.mark.asyncio
async def test_recorte_vale_para_todas_as_agregacoes(admin_engine):
    """Filtrar por fornecedor tem de recortar secretaria, natureza, fonte e
    contrato junto — não só o gráfico de fornecedores."""
    tenant, solic = await _provisionar(admin_engine)
    d1 = await _setup_debito(admin_engine, tenant.id, solic)
    d2 = await _setup_debito(admin_engine, tenant.id, solic)
    await _pagar(admin_engine, tenant.id, d1, "600.00")
    await _pagar(admin_engine, tenant.id, d2, "400.00")

    async with _sm(admin_engine)() as s:
        debito1 = (await s.execute(select(Debito).where(Debito.id == d1.id))).scalar_one()
        alvo = debito1.id_fornecedor

    async with _sm(admin_engine)() as s:
        out = await dash.montar_dashboard(s, tenant_id=tenant.id, meses=12,
                                          filtros={"fornecedor": alvo})

    assert out.filtros_ativos == {"fornecedor": alvo}
    # Cada arreio cria o próprio fornecedor, então o recorte isola um débito.
    assert out.total_filtrado == Decimal("600.00")
    for nome, itens in (("secretaria", out.por_secretaria), ("natureza", out.por_natureza),
                        ("fonte", out.por_fonte), ("contrato", out.top_contratos),
                        ("fornecedor", out.top_fornecedores)):
        assert _soma(itens) == out.total_filtrado, (
            f"a dimensão '{nome}' ignorou o recorte — gráficos de escopos diferentes na "
            "mesma tela")


@pytest.mark.asyncio
async def test_filtro_por_unidade_recorta(admin_engine):
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _pagar(admin_engine, tenant.id, debito, "250.00")

    async with _sm(admin_engine)() as s:
        d = (await s.execute(select(Debito).where(Debito.id == debito.id))).scalar_one()
        unidade = d.id_unidade

    async with _sm(admin_engine)() as s:
        dentro = await dash.montar_dashboard(s, tenant_id=tenant.id, meses=12,
                                             filtros={"unidade": unidade})
        fora = await dash.montar_dashboard(s, tenant_id=tenant.id, meses=12,
                                           filtros={"unidade": unidade + 9999})

    assert dentro.total_filtrado == Decimal("250.00")
    assert fora.total_filtrado == Decimal("0")
    assert fora.por_secretaria == []


@pytest.mark.asyncio
async def test_barra_traz_o_id_para_poder_ser_clicada(admin_engine):
    """Sem id na barra não há drill-down: a tela não teria o que enviar."""
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _pagar(admin_engine, tenant.id, debito, "120.00")

    async with _sm(admin_engine)() as s:
        out = await dash.montar_dashboard(s, tenant_id=tenant.id, meses=12)

    for itens in (out.por_secretaria, out.por_natureza, out.por_fonte, out.top_fornecedores):
        assert itens and itens[0].id is not None


@pytest.mark.asyncio
async def test_linha_agregada_nao_tem_id(admin_engine):
    """"Outras" junta várias dimensões: clicar nela não seria um recorte.

    Monta sete naturezas pagas para estourar o corte de seis do gráfico.
    """
    tenant, solic = await _provisionar(admin_engine)
    from app.schemas.pagamentos import NaturezaCreate
    from app.services import pagamentos_cadastros as cad
    import uuid

    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _pagar(admin_engine, tenant.id, debito, "100.00")

    for i in range(7):
        async with _sm(admin_engine)() as s:
            nat = await cad.criar_natureza(
                s, tenant_id=tenant.id,
                payload=NaturezaCreate(codigo=f"N{uuid.uuid4().hex[:5]}", descricao=f"Nat {i}"))
            nat_id = nat.id
        outro = await _setup_debito(admin_engine, tenant.id, solic)
        async with _sm(admin_engine)() as s:
            d = (await s.execute(select(Debito).where(Debito.id == outro.id))).scalar_one()
            d.id_natureza = nat_id
            await s.commit()
        await _pagar(admin_engine, tenant.id, outro, f"{10 + i}.00")

    async with _sm(admin_engine)() as s:
        out = await dash.montar_dashboard(s, tenant_id=tenant.id, meses=12)

    agregadas = [i for i in out.por_natureza if i.descricao == "Outras"]
    assert agregadas, "o arreio devia ter estourado o corte de seis"
    assert agregadas[0].id is None


@pytest.mark.asyncio
async def test_saldo_nao_e_recortado_pelo_filtro(admin_engine):
    """Não existe "saldo da Secretaria de Saúde": saldo é da conta bancária.
    Recortá-lo inventaria um número."""
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _pagar(admin_engine, tenant.id, debito, "300.00")

    async with _sm(admin_engine)() as s:
        d = (await s.execute(select(Debito).where(Debito.id == debito.id))).scalar_one()
        unidade = d.id_unidade

    async with _sm(admin_engine)() as s:
        sem = await dash.montar_dashboard(s, tenant_id=tenant.id, meses=12)
        com = await dash.montar_dashboard(s, tenant_id=tenant.id, meses=12,
                                          filtros={"unidade": unidade})

    assert com.kpis.saldo_total == sem.kpis.saldo_total
    assert com.kpis.disponivel_total == sem.kpis.disponivel_total
    assert com.disponibilidade_contas == sem.disponibilidade_contas


@pytest.mark.asyncio
async def test_filtro_nulo_e_ignorado(admin_engine):
    """A rota manda as cinco dimensões, quase sempre nulas."""
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _pagar(admin_engine, tenant.id, debito, "90.00")

    async with _sm(admin_engine)() as s:
        out = await dash.montar_dashboard(
            s, tenant_id=tenant.id, meses=12,
            filtros={"unidade": None, "fornecedor": None, "contrato": None,
                     "natureza": None, "fonte": None})

    assert out.filtros_ativos == {}
    assert out.total_filtrado == Decimal("90.00")
