"""Retorno do sistema financeiro: `valor_empenhado`, `valor_liquidado`, `revisado` (0144).

O que estas provas travam, e por quê cada uma:

1. **NULL não é zero.** Débito que o sistema financeiro nunca tocou tem os dois
   valores nulos. Se algum dia alguém "melhorar" isso para zero, o painel passa
   a afirmar "empenhado R$ 0,00" para a prefeitura inteira — uma afirmação
   falsa com cara de dado.
2. **O saldo não muda.** O comprometido é do solicitado e autorizado (decisão do
   Jorge, 2026-11-24); empenho e liquidação entram como informação. Este é o
   teste que pega o dia em que alguém ligar os dois por engano.
3. **`revisado` cai quando o débito muda por baixo do retorno** — é o que faz a
   divergência com a origem aparecer em vez de passar calada.

Padrão de arreio emprestado de `test_pagamentos_f2_versionamento.py`
(provisionar tenant + atores reais; FKs de ator não aceitam id fixo).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.schemas.pagamentos import DebitoUpdate
from app.services import pagamentos_caixa as caixa
from app.services import pagamentos_debitos as svc
from app.services.pagamentos_debitos import PagamentoDebitoError
from tests.test_pagamentos_f2_versionamento import (
    _criar_usuario, _provisionar, _setup_debito, _sm,
)


@pytest.mark.asyncio
async def test_debito_novo_nasce_sem_retorno_e_nao_revisado(admin_engine):
    """NULL = "o sistema financeiro ainda não devolveu". Diferente de zero."""
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        d = await svc.obter_debito(s, tenant_id=tenant.id, debito_id=debito.id)
        assert d.valor_empenhado is None
        assert d.valor_liquidado is None
        assert d.revisado is False


@pytest.mark.asyncio
async def test_empenho_grava_valor_marca_revisado_e_deixa_trilha(admin_engine):
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        d = await svc.registrar_empenho(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
            valor_empenhado=Decimal("980.00"), numero_ne="2026NE000123",
        )
        assert d.valor_empenhado == Decimal("980.00")
        assert d.numero_ne == "2026NE000123"
        assert d.revisado is True

    async with _sm(admin_engine)() as s:
        hist = await svc.listar_historico(s, tenant_id=tenant.id, debito_id=debito.id)
        acoes = [h.acao for h in hist]
        assert "EMPENHO_REGISTRADO" in acoes, acoes


@pytest.mark.asyncio
async def test_empenho_nao_muda_nenhuma_das_tres_dimensoes(admin_engine):
    """Registrar empenho é informação, não ato de rito."""
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    antes = (debito.situacao_tramitacao, debito.situacao_fila, debito.situacao_pagamento)

    async with _sm(admin_engine)() as s:
        d = await svc.registrar_empenho(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
            valor_empenhado=Decimal("500.00"),
        )
    assert (d.situacao_tramitacao, d.situacao_fila, d.situacao_pagamento) == antes


@pytest.mark.asyncio
async def test_empenho_nao_altera_comprometido_da_conta(admin_engine):
    """O comprometido é do solicitado e autorizado — empenho não entra nele.

    O débito deste arreio está em RASCUNHO (não autorizado), então o
    comprometido é zero antes E depois. O que a prova trava é que registrar
    empenho não cria reserva nenhuma por tabela — o dia em que alguém ligar
    `valor_empenhado` ao cálculo de saldo, este teste fica vermelho.
    """
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    from sqlalchemy import select

    from app.models import ContaBancaria
    async with _sm(admin_engine)() as s:
        conta_id = (await s.execute(
            select(ContaBancaria.id).where(ContaBancaria.tenant_id == tenant.id,
                                           ContaBancaria.excluido.is_(False))
        )).scalars().first()
    assert conta_id is not None, "o arreio cria uma conta; sem ela a prova não vale"

    async with _sm(admin_engine)() as s:
        antes = await caixa.saldo_conta(s, tenant_id=tenant.id, conta_id=conta_id)

    async with _sm(admin_engine)() as s:
        await svc.registrar_empenho(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
            valor_empenhado=Decimal("999.00"),
        )

    async with _sm(admin_engine)() as s:
        depois = await caixa.saldo_conta(s, tenant_id=tenant.id, conta_id=conta_id)

    assert depois.comprometido == antes.comprometido
    assert depois.disponivel == antes.disponivel
    assert depois.saldo_atual == antes.saldo_atual


@pytest.mark.asyncio
async def test_reempenho_com_valor_novo_sobrescreve(admin_engine):
    """"Se mudar na conciliação vai vir o novo falar e a gente atualiza"."""
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        await svc.registrar_empenho(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
            valor_empenhado=Decimal("100.00"),
        )
    async with _sm(admin_engine)() as s:
        d = await svc.registrar_empenho(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
            valor_empenhado=Decimal("250.00"),
        )
    assert d.valor_empenhado == Decimal("250.00")


@pytest.mark.asyncio
async def test_reempenho_com_mesmo_valor_nao_polui_a_trilha(admin_engine):
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        await svc.registrar_empenho(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
            valor_empenhado=Decimal("100.00"),
        )
    async with _sm(admin_engine)() as s:
        hist = await svc.listar_historico(s, tenant_id=tenant.id, debito_id=debito.id)
        uma_vez = [h for h in hist if h.acao == "EMPENHO_REGISTRADO"]

    async with _sm(admin_engine)() as s:
        await svc.registrar_empenho(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
            valor_empenhado=Decimal("100.00"),
        )
    async with _sm(admin_engine)() as s:
        hist2 = await svc.listar_historico(s, tenant_id=tenant.id, debito_id=debito.id)
        de_novo = [h for h in hist2 if h.acao == "EMPENHO_REGISTRADO"]

    assert len(de_novo) == len(uma_vez) == 1


@pytest.mark.asyncio
async def test_empenho_negativo_e_recusado(admin_engine):
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        with pytest.raises(PagamentoDebitoError):
            await svc.registrar_empenho(
                s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
                valor_empenhado=Decimal("-1.00"),
            )


@pytest.mark.asyncio
async def test_liquidar_com_valor_grava_e_marca_revisado(admin_engine):
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        d = await svc.confirmar_liquidacao(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
            valor_liquidado=Decimal("980.00"),
        )
    assert d.liquidacao_confirmada is True
    assert d.valor_liquidado == Decimal("980.00")
    assert d.revisado is True


@pytest.mark.asyncio
async def test_liquidar_sem_valor_continua_valendo(admin_engine):
    """Compatibilidade: a porta que já existia não passa valor nenhum."""
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        d = await svc.confirmar_liquidacao(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
        )
    assert d.liquidacao_confirmada is True
    assert d.valor_liquidado is None
    assert d.revisado is False


@pytest.mark.asyncio
async def test_edicao_material_derruba_revisado_sem_apagar_os_valores(admin_engine):
    """Mexer no valor pedido invalida a conferência, mas não apaga o que a
    origem disse — senão a divergência some junto com a prova dela."""
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        await svc.registrar_empenho(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
            valor_empenhado=Decimal("1000.00"),
        )

    # Débito está em RASCUNHO, onde a edição é permitida. Mudar o valor total
    # exige reenviar as parcelas (a soma tem de bater).
    from app.schemas.pagamentos import ParcelaCreate
    async with _sm(admin_engine)() as s:
        d = await svc.atualizar_debito(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
            payload=DebitoUpdate(
                valor_total=Decimal("1200.00"),
                parcelas=[ParcelaCreate(numero=1, valor=Decimal("1200.00"),
                                        vencimento="2026-02-01")],
            ),
        )

    assert d.revisado is False, "edição material tem de derrubar a marca de conferido"
    assert d.valor_empenhado == Decimal("1000.00"), "o valor da origem não se apaga"


@pytest.mark.asyncio
async def test_debito_out_expoe_os_tres_campos(admin_engine):
    """A porta M2M devolve o que gravou — senão o sistema financeiro não tem
    como conferir que o retorno chegou."""
    tenant, solicitante_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        d = await svc.registrar_empenho(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
            valor_empenhado=Decimal("777.00"),
        )
        corpo = svc.debito_out(d, nome_fornecedor="Empresa LTDA")

    assert corpo["valor_empenhado"] == Decimal("777.00")
    assert corpo["valor_liquidado"] is None
    assert corpo["revisado"] is True
