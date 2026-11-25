"""Central de alertas gerenciais (fatia 6, §11 do brief).

As propriedades que este arquivo trava são de CONTRATO, não de aparência:

- Todo alerta precisa de `acao` e `origem` preenchidos. Aviso sem o que fazer é
  barulho, e barulho treina o gestor a ignorar a lista inteira — inclusive os
  alertas que importam. Aviso sem origem é número que ninguém consegue
  conferir.
- Banco saudável não inventa alerta. Lista cheia por padrão tem o mesmo efeito
  do barulho.
- A ordenação põe o crítico em cima. Alerta crítico no fim da lista é alerta
  que não existe.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import ContaBancaria, Debito, FonteRecursos, Parcela
from app.services import pagamentos_alertas as al
from app.services import pagamentos_estados as est
from tests.test_pagamentos_f2_versionamento import _provisionar, _setup_debito, _sm


async def _autorizar(engine, tenant_id: int, debito_id: int, vencimento: date,
                     com_conta: bool = True) -> None:
    async with _sm(engine)() as s:
        conta_id = (await s.execute(select(ContaBancaria.id).where(
            ContaBancaria.tenant_id == tenant_id,
            ContaBancaria.excluido.is_(False)))).scalars().first()
        d = (await s.execute(select(Debito).where(Debito.id == debito_id))).scalar_one()
        d.situacao_tramitacao = est.AUTORIZADA
        if com_conta:
            d.id_conta_pagadora = conta_id
        for p in (await s.execute(select(Parcela).where(
                Parcela.id_debito == debito_id))).scalars().all():
            p.vencimento = vencimento
            p.status = "A_PAGAR"
        await s.commit()


async def _preencher_vinculacao(engine, tenant_id: int) -> None:
    """Tira do caminho o alerta informativo de cadastro, que é o único que o
    arreio dispara sozinho."""
    async with _sm(engine)() as s:
        for f in (await s.execute(select(FonteRecursos).where(
                FonteRecursos.tenant_id == tenant_id))).scalars().all():
            f.tipo_vinculacao = "NAO_VINCULADA"
        await s.commit()


@pytest.mark.asyncio
async def test_todo_alerta_diz_o_que_fazer_e_de_onde_veio(admin_engine):
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _autorizar(admin_engine, tenant.id, debito.id, date.today() - timedelta(days=5))

    async with _sm(admin_engine)() as s:
        out = await al.montar_alertas(s, tenant_id=tenant.id)

    assert out.itens, "o arreio tem parcela vencida: algum alerta tem de sair"
    for a in out.itens:
        assert a.acao.strip(), f"{a.codigo} sem ação — vira barulho"
        assert a.origem.strip(), f"{a.codigo} sem origem — número que ninguém confere"
        assert a.titulo.strip() and a.descricao.strip()


@pytest.mark.asyncio
async def test_parcela_vencida_vira_alerta_critico_com_impacto(admin_engine):
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _autorizar(admin_engine, tenant.id, debito.id, date.today() - timedelta(days=3))

    async with _sm(admin_engine)() as s:
        out = await al.montar_alertas(s, tenant_id=tenant.id)

    vencidas = [a for a in out.itens if a.codigo == "parcelas_vencidas"]
    assert len(vencidas) == 1
    a = vencidas[0]
    assert a.severidade == "CRITICO"
    assert a.impacto_valor == debito.valor_total
    assert a.impacto_qtd == 1
    assert out.criticos >= 1


@pytest.mark.asyncio
async def test_critico_vem_antes_do_informativo(admin_engine):
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _autorizar(admin_engine, tenant.id, debito.id, date.today() - timedelta(days=3))

    async with _sm(admin_engine)() as s:
        out = await al.montar_alertas(s, tenant_id=tenant.id)

    severidades = [a.severidade for a in out.itens]
    assert severidades[0] == "CRITICO"
    ordem = {"CRITICO": 0, "ALTO": 1, "MEDIO": 2, "INFORMATIVO": 3}
    assert severidades == sorted(severidades, key=lambda s: ordem[s])


@pytest.mark.asyncio
async def test_vencimento_proximo_e_alto_nao_critico(admin_engine):
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _autorizar(admin_engine, tenant.id, debito.id, date.today() + timedelta(days=3))

    async with _sm(admin_engine)() as s:
        out = await al.montar_alertas(s, tenant_id=tenant.id)

    prox = [a for a in out.itens if a.codigo == "vence_7_dias"]
    assert len(prox) == 1
    assert prox[0].severidade == "ALTO"
    assert not [a for a in out.itens if a.codigo == "parcelas_vencidas"]


@pytest.mark.asyncio
async def test_autorizado_sem_conta_pagadora_e_sinalizado(admin_engine):
    """A anomalia que a previsão documentou: reserva que não aparece no
    comprometido de conta nenhuma."""
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _autorizar(admin_engine, tenant.id, debito.id,
                     date.today() + timedelta(days=40), com_conta=False)

    async with _sm(admin_engine)() as s:
        out = await al.montar_alertas(s, tenant_id=tenant.id)

    achados = [a for a in out.itens if a.codigo == "autorizado_sem_conta_pagadora"]
    assert len(achados) == 1
    assert achados[0].impacto_qtd == 1


@pytest.mark.asyncio
async def test_fonte_sem_vinculacao_e_informativo(admin_engine):
    tenant, _solic = await _provisionar(admin_engine)
    await _setup_debito(admin_engine, tenant.id, _solic)

    async with _sm(admin_engine)() as s:
        out = await al.montar_alertas(s, tenant_id=tenant.id)

    achados = [a for a in out.itens if a.codigo == "fonte_sem_vinculacao"]
    assert len(achados) == 1
    assert achados[0].severidade == "INFORMATIVO", (
        "lacuna de cadastro não é crítico — não quebra nada hoje")


@pytest.mark.asyncio
async def test_nada_errado_nao_vira_lista_de_alertas(admin_engine):
    """Banco sem pendência e com cadastro completo não inventa aviso."""
    tenant, _solic = await _provisionar(admin_engine)
    await _preencher_vinculacao(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        out = await al.montar_alertas(s, tenant_id=tenant.id)

    assert out.criticos == 0
    assert out.altos == 0
    assert [a.codigo for a in out.itens if a.severidade in ("CRITICO", "ALTO")] == []


@pytest.mark.asyncio
async def test_alerta_de_outro_tenant_nao_vaza(admin_engine):
    tenant_a, solic_a = await _provisionar(admin_engine)
    debito_a = await _setup_debito(admin_engine, tenant_a.id, solic_a)
    await _autorizar(admin_engine, tenant_a.id, debito_a.id, date.today() - timedelta(days=9))

    tenant_b, _ = await _provisionar(admin_engine)
    await _preencher_vinculacao(admin_engine, tenant_b.id)

    async with _sm(admin_engine)() as s:
        out_b = await al.montar_alertas(s, tenant_id=tenant_b.id)

    assert out_b.criticos == 0
    assert not [a for a in out_b.itens if a.codigo == "parcelas_vencidas"]


@pytest.mark.asyncio
async def test_impacto_em_dinheiro_quando_ha_dinheiro_envolvido(admin_engine):
    """Alerta de valor sem valor não deixa o gestor priorizar."""
    tenant, solic = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solic)
    await _autorizar(admin_engine, tenant.id, debito.id, date.today() - timedelta(days=2))

    async with _sm(admin_engine)() as s:
        out = await al.montar_alertas(s, tenant_id=tenant.id)

    com_dinheiro = {"parcelas_vencidas", "vence_7_dias", "conta_sem_lastro"}
    for a in out.itens:
        if a.codigo in com_dinheiro:
            assert a.impacto_valor is not None and a.impacto_valor > Decimal("0")
