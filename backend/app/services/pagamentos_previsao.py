"""Previsão financeira de SAÍDA — 7/15/30/60/90 dias (fatia 5).

**A armadilha que este módulo existe para não cair.** `saldo_conta().disponivel`
já é `saldo_atual − comprometido − bloqueado`, e `comprometido` é a soma das
parcelas em aberto de débitos autorizados — as MESMAS parcelas que a projeção
percorre por data de vencimento. Projetar "disponível menos o que vence" conta
cada parcela duas vezes e produz um caixa futuro menor que o real, às vezes
negativo sem nenhum motivo. O ponto de partida correto é o **saldo bancário**:

    saldo projetado em D = saldo_atual − bloqueado − Σ(parcelas vencendo até D)

Com D no infinito essa conta chega exatamente em `disponivel`, que é a prova de
que as duas visões falam do mesmo dinheiro.

Uma diferença deliberada entre as duas: `comprometido_conta` soma por **conta
pagadora**, então um débito autorizado sem conta atribuída não entra nela. A
projeção soma TODAS as parcelas em aberto de débitos autorizados, com conta ou
sem. É a escolha conservadora — dinheiro que vai sair é dinheiro que vai sair —
e na prática não há divergência, porque a conta pagadora é gravada no ato de
autorizar e é imutável depois. Se um dia aparecer débito autorizado sem conta,
a projeção o mostra e o `disponivel` não: aí o certo é investigar o débito, não
"alinhar" os dois números.

**O que esta previsão NÃO tem: receita.** O Aprimora não tem módulo de receita,
então não há previsão de entrada — nem repasse, nem arrecadação, nem convênio.
A projeção é só do lado da saída, e `considera_receita=False` existe para a
tela ser obrigada a dizer isso. Um saldo projetado negativo aqui significa "as
obrigações conhecidas passam do dinheiro em caixa hoje", não "o município vai
quebrar": a entrada que ainda vai acontecer não está na conta.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ContaBancaria, Debito, Parcela
from ..schemas.pagamentos import (
    PrevisaoContaRisco, PrevisaoFinanceiraOut, PrevisaoHorizonteItem,
)
from . import pagamentos_caixa as caixa
from . import pagamentos_estados as est

# Os horizontes do §10 do brief. Cumulativos: 30 dias inclui o que vence em 7.
HORIZONTES = (7, 15, 30, 60, 90)

# Mesma condição de reserva de `pagamentos_caixa`/`pagamentos_dashboard`: só
# conta como obrigação o que já foi autorizado e ainda não foi pago.
_TEM_RESERVA = and_(Debito.situacao_tramitacao == est.AUTORIZADA,
                    Debito.situacao_pagamento.notin_((est.PAGA, est.CONCILIADA)))

_ABERTAS = ("A_PAGAR", "LIBERADA")


def _utcnow() -> datetime:
    return datetime.utcnow()


async def _vence_ate(db, *, tenant_id: int, limite: date,
                     conta_id: int | None = None) -> tuple[Decimal, int]:
    """Σ e contagem das parcelas em aberto que vencem ATÉ `limite`.

    Inclui as já vencidas de propósito: uma obrigação vencida e não paga
    continua sendo dinheiro que vai sair, e tirá-la da projeção mostraria um
    caixa futuro melhor do que é.
    """
    stmt = (select(func.coalesce(func.sum(Parcela.valor), 0), func.count(Parcela.id))
            .join(Debito, Debito.id == Parcela.id_debito)
            .where(Parcela.tenant_id == tenant_id, Parcela.excluido.is_(False),
                   Parcela.status.in_(_ABERTAS), Debito.excluido.is_(False),
                   _TEM_RESERVA, Parcela.vencimento <= limite))
    if conta_id is not None:
        stmt = stmt.where(Debito.id_conta_pagadora == conta_id)
    valor, qtd = (await db.execute(stmt)).one()
    return Decimal(valor), int(qtd)


async def montar_previsao(db: AsyncSession, *, tenant_id: int) -> PrevisaoFinanceiraOut:
    hoje = _utcnow().date()
    painel = await caixa.painel_caixa(db, tenant_id=tenant_id)
    saldo_atual = sum((c.saldo_atual for c in painel), Decimal("0"))
    bloqueado = sum((c.bloqueado for c in painel), Decimal("0"))
    base = saldo_atual - bloqueado

    # Vencidas: já deviam ter saído. Ficam separadas porque não são previsão,
    # são atraso — e misturá-las com "o que vem" esconde o problema de hoje.
    vencidas_valor, vencidas_qtd = (await db.execute(
        select(func.coalesce(func.sum(Parcela.valor), 0), func.count(Parcela.id))
        .join(Debito, Debito.id == Parcela.id_debito)
        .where(Parcela.tenant_id == tenant_id, Parcela.excluido.is_(False),
               Parcela.status.in_(_ABERTAS), Debito.excluido.is_(False),
               _TEM_RESERVA, Parcela.vencimento < hoje))).one()

    horizontes: list[PrevisaoHorizonteItem] = []
    anterior = Decimal("0")
    for dias in HORIZONTES:
        ate = hoje + timedelta(days=dias)
        acumulado, qtd = await _vence_ate(db, tenant_id=tenant_id, limite=ate)
        projetado = base - acumulado
        horizontes.append(PrevisaoHorizonteItem(
            dias=dias, ate=ate, vence_acumulado=acumulado,
            vence_na_janela=acumulado - anterior, qtd_parcelas=qtd,
            saldo_projetado=projetado, suficiente=projetado >= 0))
        anterior = acumulado

    # Risco por conta no horizonte mais longo: a vinculação de fonte vale aqui
    # como vale na autorização — saldo de uma conta não cobre obrigação de
    # outra, então um total saudável pode esconder uma conta no vermelho.
    limite_90 = hoje + timedelta(days=HORIZONTES[-1])
    contas_em_risco: list[PrevisaoContaRisco] = []
    for c in painel:
        vence, qtd = await _vence_ate(db, tenant_id=tenant_id, limite=limite_90,
                                      conta_id=c.id_conta)
        if qtd == 0:
            continue
        projetado = c.saldo_atual - c.bloqueado - vence
        if projetado >= 0:
            continue
        contas_em_risco.append(PrevisaoContaRisco(
            id_conta=c.id_conta, nome=c.nome, saldo_atual=c.saldo_atual,
            vence_no_horizonte=vence, qtd_parcelas=qtd,
            saldo_projetado=projetado, falta=-projetado))
    contas_em_risco.sort(key=lambda i: i.saldo_projetado)

    return PrevisaoFinanceiraOut(
        saldo_atual=saldo_atual, bloqueado=bloqueado, base_projecao=base,
        vencidas_valor=Decimal(vencidas_valor), vencidas_qtd=int(vencidas_qtd),
        horizontes=horizontes, contas_em_risco=contas_em_risco,
        considera_receita=False, apurado_em=_utcnow())
