"""Orçamento — dotação, créditos e execução (O1, migration 0146).

As propriedades que este arquivo trava:

1. **A dotação atualizada é derivada.** Nunca uma coluna. Se alguém "otimizar"
   guardando o valor, ele passa a divergir dos créditos no primeiro lançamento
   que esquecer de atualizá-lo — e um orçamento que não bate com os próprios
   créditos é pior que nenhum.
2. **O sinal é do tipo, não do valor.** Anulação subtrai; suplementação soma.
   Valor negativo gravado por engano viraria suplementação que diminui a
   dotação, e ninguém confere duas vezes um número positivo numa soma.
3. **Despesa sem dotação não é rateada.** Ela é contada e mostrada à parte.
   Distribuí-la entre as dotações existentes inventaria execução.
4. **Despesa sem retorno de empenho não conta como executada**, e a contagem
   dela acompanha o número: execução baixa pode ser "gastou pouco" ou "o
   retorno não chegou", e as duas leituras pedem ações opostas.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Debito, Dotacao, FonteRecursos, UnidadeTrabalho
from app.schemas.pagamentos import CreditoCreate, DotacaoCreate
from app.services import pagamentos_orcamento as orc
from tests.test_pagamentos_f2_versionamento import _provisionar, _setup_debito, _sm


async def _criar_dotacao(engine, tenant_id: int, valor: str = "100000.00",
                         acao: str | None = None) -> Dotacao:
    """Dotação mínima. Cria fonte se ainda não houver: o tenant recém
    provisionado só ganha fonte dentro de `_setup_debito`, e vários testes
    daqui montam a dotação ANTES de existir despesa."""
    from app.schemas.pagamentos import FonteCreate
    from app.services import pagamentos_cadastros as cad

    async with _sm(engine)() as s:
        unidade = (await s.execute(select(UnidadeTrabalho.id).where(
            UnidadeTrabalho.tenant_id == tenant_id))).scalars().first()
        fonte = (await s.execute(select(FonteRecursos.id).where(
            FonteRecursos.tenant_id == tenant_id,
            FonteRecursos.excluido.is_(False)))).scalars().first()
        if fonte is None:
            f = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
                codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Ordinários",
                grupos_despesa_permitidos=[]))
            fonte = f.id
        return await orc.criar_dotacao(s, tenant_id=tenant_id, payload=DotacaoCreate(
            exercicio=2026, id_unidade=unidade, funcao="10", subfuncao="301",
            programa="0012", acao=acao or uuid.uuid4().hex[:8],
            natureza_codigo="3.3.90.30", grupo_despesa="CUSTEIO",
            id_fonte_recursos=fonte, descricao="Manutenção da atenção básica",
            valor_inicial=Decimal(valor)))


async def _vincular(engine, debito_id: int, dotacao_id: int, empenhado: str | None):
    async with _sm(engine)() as s:
        d = (await s.execute(select(Debito).where(Debito.id == debito_id))).scalar_one()
        d.id_dotacao = dotacao_id
        d.exercicio = 2026
        if empenhado is not None:
            d.valor_empenhado = Decimal(empenhado)
        await s.commit()


@pytest.mark.asyncio
async def test_dotacao_sem_credito_tem_atualizada_igual_a_inicial(admin_engine):
    tenant, _ = await _provisionar(admin_engine)
    await _criar_dotacao(admin_engine, tenant.id, "50000.00")

    async with _sm(admin_engine)() as s:
        pos = await orc.posicao_dotacao(s, tenant_id=tenant.id, exercicio=2026)

    assert len(pos) == 1
    assert pos[0].dotacao_atualizada == Decimal("50000.00")
    assert pos[0].creditos == Decimal("0")


@pytest.mark.asyncio
async def test_suplementacao_soma_e_anulacao_subtrai(admin_engine):
    """O sinal é do TIPO. Os dois créditos entram com valor positivo."""
    tenant, _ = await _provisionar(admin_engine)
    dot = await _criar_dotacao(admin_engine, tenant.id, "100000.00")

    async with _sm(admin_engine)() as s:
        await orc.lancar_credito(s, tenant_id=tenant.id, usuario_id=None,
                                 payload=CreditoCreate(
                                     id_dotacao=dot.id, tipo="SUPLEMENTAR",
                                     valor=Decimal("30000.00"), data=date(2026, 3, 1),
                                     ato="Decreto 12/2026"))
    async with _sm(admin_engine)() as s:
        await orc.lancar_credito(s, tenant_id=tenant.id, usuario_id=None,
                                 payload=CreditoCreate(
                                     id_dotacao=dot.id, tipo="ANULACAO",
                                     valor=Decimal("10000.00"), data=date(2026, 4, 1),
                                     ato="Decreto 20/2026"))

    async with _sm(admin_engine)() as s:
        pos = await orc.posicao_dotacao(s, tenant_id=tenant.id, exercicio=2026)

    assert pos[0].creditos == Decimal("20000.00")
    assert pos[0].dotacao_atualizada == Decimal("120000.00")


@pytest.mark.asyncio
async def test_atualizada_e_derivada_nao_coluna(admin_engine):
    """Não existe coluna de valor atualizado na tabela — o número sai da soma."""
    assert not hasattr(Dotacao, "valor_atualizado"), (
        "guardar a dotação atualizada em coluna reabre a divergência com os créditos")


@pytest.mark.asyncio
async def test_execucao_usa_o_empenhado_do_retorno(admin_engine):
    tenant, solic = await _provisionar(admin_engine)
    dot = await _criar_dotacao(admin_engine, tenant.id, "10000.00")
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _vincular(admin_engine, debito.id, dot.id, "2500.00")

    async with _sm(admin_engine)() as s:
        out = await orc.execucao_orcamentaria(s, tenant_id=tenant.id, exercicio=2026)

    assert out.empenhado == Decimal("2500.00")
    assert out.disponivel == Decimal("7500.00")
    assert round(out.execucao_pct, 1) == 25.0


@pytest.mark.asyncio
async def test_despesa_sem_retorno_nao_conta_mas_e_avisada(admin_engine):
    """Execução baixa por falta de retorno não pode parecer execução baixa por
    economia — são leituras opostas."""
    tenant, solic = await _provisionar(admin_engine)
    dot = await _criar_dotacao(admin_engine, tenant.id, "10000.00")
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _vincular(admin_engine, debito.id, dot.id, None)

    async with _sm(admin_engine)() as s:
        out = await orc.execucao_orcamentaria(s, tenant_id=tenant.id, exercicio=2026)

    assert out.empenhado == Decimal("0")
    assert out.despesas_sem_retorno == 1
    assert out.itens[0].despesas_sem_retorno == 1
    assert out.itens[0].despesas_com_retorno == 0


@pytest.mark.asyncio
async def test_despesa_sem_dotacao_e_contada_a_parte_nunca_rateada(admin_engine):
    tenant, solic = await _provisionar(admin_engine)
    await _criar_dotacao(admin_engine, tenant.id, "10000.00")
    debito = await _setup_debito(admin_engine, tenant.id, solic)  # sem vínculo

    async with _sm(admin_engine)() as s:
        out = await orc.execucao_orcamentaria(s, tenant_id=tenant.id, exercicio=2026)

    assert out.despesas_sem_dotacao_qtd == 1
    assert out.despesas_sem_dotacao_valor == debito.valor_total
    # E não entrou na execução de dotação nenhuma.
    assert out.empenhado == Decimal("0")
    assert sum((i.empenhado for i in out.itens), Decimal("0")) == Decimal("0")


@pytest.mark.asyncio
async def test_dotacao_estourada_e_marcada_e_vem_primeiro(admin_engine):
    tenant, solic = await _provisionar(admin_engine)
    folgada = await _criar_dotacao(admin_engine, tenant.id, "100000.00", acao="A1")
    apertada = await _criar_dotacao(admin_engine, tenant.id, "1000.00", acao="A2")

    d1 = await _setup_debito(admin_engine, tenant.id, solic)
    await _vincular(admin_engine, d1.id, folgada.id, "1000.00")
    d2 = await _setup_debito(admin_engine, tenant.id, solic)
    await _vincular(admin_engine, d2.id, apertada.id, "5000.00")

    async with _sm(admin_engine)() as s:
        out = await orc.execucao_orcamentaria(s, tenant_id=tenant.id, exercicio=2026)

    assert out.dotacoes_estouradas == 1
    assert out.itens[0].estourada is True
    assert out.itens[0].id_dotacao == apertada.id
    assert out.itens[0].disponivel < 0


@pytest.mark.asyncio
async def test_credito_em_dotacao_de_outro_tenant_e_recusado(admin_engine):
    tenant_a, _ = await _provisionar(admin_engine)
    dot_a = await _criar_dotacao(admin_engine, tenant_a.id)
    tenant_b, _ = await _provisionar(admin_engine)

    from fastapi import HTTPException
    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException):
            await orc.lancar_credito(s, tenant_id=tenant_b.id, usuario_id=None,
                                     payload=CreditoCreate(
                                         id_dotacao=dot_a.id, tipo="SUPLEMENTAR",
                                         valor=Decimal("1.00"), data=date(2026, 1, 1),
                                         ato="x"))


@pytest.mark.asyncio
async def test_orcamento_de_outro_tenant_nao_vaza(admin_engine):
    tenant_a, solic = await _provisionar(admin_engine)
    dot = await _criar_dotacao(admin_engine, tenant_a.id, "80000.00")
    debito = await _setup_debito(admin_engine, tenant_a.id, solic)
    await _vincular(admin_engine, debito.id, dot.id, "4000.00")

    tenant_b, _ = await _provisionar(admin_engine)
    async with _sm(admin_engine)() as s:
        out = await orc.execucao_orcamentaria(s, tenant_id=tenant_b.id, exercicio=2026)

    assert out.qtd_dotacoes == 0
    assert out.empenhado == Decimal("0")


@pytest.mark.asyncio
async def test_exercicio_omitido_usa_o_mais_recente(admin_engine):
    tenant, _ = await _provisionar(admin_engine)
    await _criar_dotacao(admin_engine, tenant.id, "7000.00")

    async with _sm(admin_engine)() as s:
        out = await orc.execucao_orcamentaria(s, tenant_id=tenant.id)

    assert out.exercicio == 2026
    assert out.dotacao_atualizada == Decimal("7000.00")
