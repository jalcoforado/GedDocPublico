"""Impacto de autorizar o que está pendente (fatia 4).

Duas propriedades valem o arquivo:

1. **O impacto é POR FONTE.** Um débito só pode ser pago por conta da própria
   fonte (RN-02/05). Um painel que respondesse "cabe?" olhando o caixa inteiro
   diria que cabe quando não cabe — e o erro só apareceria na hora em que a
   autorização recusasse, depois de o gestor já ter decidido.
2. **Ver o impacto não autoriza nada.** É consulta. Se um dia alguém fizer esta
   função reservar saldo ou mudar situação, o teste fica vermelho.

Arreio emprestado de `test_pagamentos_f2_versionamento.py`.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Debito
from app.services import pagamentos_estados as est
from app.services import pagamentos_filas as filas
from tests.test_pagamentos_f2_versionamento import _provisionar, _setup_debito, _sm


async def _levar_para_autoridade(engine, tenant_id: int, debito_id: int) -> None:
    """Põe o débito em AGUARDANDO_AUTORIDADE, que é a fila do impacto."""
    async with _sm(engine)() as s:
        d = (await s.execute(select(Debito).where(Debito.id == debito_id))).scalar_one()
        d.situacao_tramitacao = est.AGUARDANDO_AUTORIDADE
        await s.commit()


@pytest.mark.asyncio
async def test_sem_pendencia_nao_inventa_numero(admin_engine):
    tenant, _solic = await _provisionar(admin_engine)
    async with _sm(admin_engine)() as s:
        out = await filas.impacto_autorizacoes(s, tenant_id=tenant.id)
    assert out.qtd_debitos == 0
    assert out.total_pendente == Decimal("0")
    assert out.fontes == []
    assert out.por_unidade == []


@pytest.mark.asyncio
async def test_soma_o_que_aguarda_autoridade_e_agrupa_por_fonte(admin_engine):
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _levar_para_autoridade(admin_engine, tenant.id, debito.id)

    async with _sm(admin_engine)() as s:
        out = await filas.impacto_autorizacoes(s, tenant_id=tenant.id)

    assert out.qtd_debitos == 1
    assert out.total_pendente == debito.valor_total
    assert len(out.fontes) == 1
    f = out.fontes[0]
    assert f.qtd_debitos == 1
    assert f.pendente == debito.valor_total
    # A conta do arreio tem saldo inicial de 10.000 e o débito é de 1.000.
    assert f.disponivel_depois == f.disponivel_antes - f.pendente
    assert f.suficiente is True
    assert f.falta == Decimal("0")


@pytest.mark.asyncio
async def test_debito_que_ainda_nao_chegou_na_autoridade_nao_conta(admin_engine):
    """O arreio cria o débito em RASCUNHO: nada a decidir ainda."""
    tenant, solic = await _provisionar(admin_engine)
    await _setup_debito(admin_engine, tenant.id, solic)

    async with _sm(admin_engine)() as s:
        out = await filas.impacto_autorizacoes(s, tenant_id=tenant.id)
    assert out.qtd_debitos == 0


@pytest.mark.asyncio
async def test_fonte_sem_lastro_e_marcada_e_vem_primeiro(admin_engine):
    """Pendência maior que o disponível da fonte: `suficiente=False` e `falta`
    com o tamanho do buraco. É a linha que muda o que o gestor faz."""
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)

    # Infla o débito muito acima do saldo inicial da conta do arreio (10.000).
    async with _sm(admin_engine)() as s:
        d = (await s.execute(select(Debito).where(Debito.id == debito.id))).scalar_one()
        d.valor_total = Decimal("999999.00")
        d.situacao_tramitacao = est.AGUARDANDO_AUTORIDADE
        await s.commit()

    async with _sm(admin_engine)() as s:
        out = await filas.impacto_autorizacoes(s, tenant_id=tenant.id)

    assert out.fontes_insuficientes == 1
    f = out.fontes[0]
    assert f.suficiente is False
    assert f.falta > 0
    assert f.falta == -f.disponivel_depois
    # Insuficiente primeiro na ordenação.
    assert out.fontes[0].suficiente is False


@pytest.mark.asyncio
async def test_consultar_o_impacto_nao_autoriza_nada(admin_engine):
    """A função é leitura. Nada de situação mudada, nada de reserva criada."""
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _levar_para_autoridade(admin_engine, tenant.id, debito.id)

    async with _sm(admin_engine)() as s:
        await filas.impacto_autorizacoes(s, tenant_id=tenant.id)

    async with _sm(admin_engine)() as s:
        d = (await s.execute(select(Debito).where(Debito.id == debito.id))).scalar_one()
    assert d.situacao_tramitacao == est.AGUARDANDO_AUTORIDADE
    assert d.id_conta_pagadora is None, "simular não pode reservar conta pagadora"


@pytest.mark.asyncio
async def test_distribuicao_por_unidade_soma_o_total(admin_engine):
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _levar_para_autoridade(admin_engine, tenant.id, debito.id)

    async with _sm(admin_engine)() as s:
        out = await filas.impacto_autorizacoes(s, tenant_id=tenant.id)

    assert sum((u.valor for u in out.por_unidade), Decimal("0")) == out.total_pendente
    assert sum(u.qtd_debitos for u in out.por_unidade) == out.qtd_debitos


@pytest.mark.asyncio
async def test_pendencia_de_outro_tenant_nao_entra(admin_engine):
    tenant_a, solic_a = await _provisionar(admin_engine)
    debito_a = await _setup_debito(admin_engine, tenant_a.id, solic_a)
    await _levar_para_autoridade(admin_engine, tenant_a.id, debito_a.id)

    tenant_b, _solic_b = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        out_b = await filas.impacto_autorizacoes(s, tenant_id=tenant_b.id)
    assert out_b.qtd_debitos == 0
