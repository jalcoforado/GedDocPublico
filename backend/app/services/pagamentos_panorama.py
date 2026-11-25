"""Panorama da Visão geral — o que está parado, há quanto tempo, e o ritmo.

Esta tela já mostrava **quantidades** por etapa. As três séries daqui
respondem o que a contagem não responde:

1. **Valor parado por etapa.** Cinco despesas de R$ 2 mil e cinco de R$ 2
   milhões dão a mesma contagem e pedem urgências opostas.
2. **Envelhecimento.** Uma fila com 10 itens parados há 2 dias é saudável; a
   mesma fila com 10 itens parados há 40 dias é um problema — e as duas
   aparecem como "10" num cartão.
3. **Ritmo semanal.** Entradas contra autorizações: a fila cresce, encolhe ou
   está estável? Sem isso, o gestor não sabe se o acúmulo é pontual ou
   tendência.

"Parado desde" é a data da ÚLTIMA transição do débito
(`debito_historico.criado_em`), não `atualizado_em`: esta última muda com
qualquer edição de campo, e um ajuste de descrição faria uma despesa parada há
40 dias parecer recém-chegada.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Debito, DebitoHistorico, Parcela
from ..schemas.pagamentos import (
    EnvelhecimentoItem, EtapaValorItem, FluxoSemanalItem, PanoramaVisaoGeralOut,
)
from . import pagamentos_estados as est

_ABERTAS = ("A_PAGAR", "LIBERADA")
_TEM_RESERVA = and_(Debito.situacao_tramitacao == est.AUTORIZADA,
                    Debito.situacao_pagamento.notin_((est.PAGA, est.CONCILIADA)))

# Etapas do rito, na ordem em que a despesa caminha.
_ETAPAS_DEBITO = [
    ("gestor", "Com o gestor", est.AGUARDANDO_GESTOR),
    ("validacao", "Em validação", est.AGUARDANDO_VALIDACAO),
    ("autoridade", "A autorizar", est.AGUARDANDO_AUTORIDADE),
]

# Faixas de envelhecimento, em dias. A última é aberta.
_FAIXAS = [(0, 3, "Até 3 dias"), (4, 7, "4 a 7 dias"), (8, 15, "8 a 15 dias"),
           (16, 30, "16 a 30 dias"), (31, None, "Mais de 30 dias")]

_SEMANAS = 8


def _utcnow() -> datetime:
    return datetime.utcnow()


def _sq_parado_desde(tenant_id: int):
    """Subconsulta: a data da última transição de cada débito."""
    return (select(DebitoHistorico.id_debito,
                   func.max(DebitoHistorico.criado_em).label("parado_desde"))
            .where(DebitoHistorico.tenant_id == tenant_id)
            .group_by(DebitoHistorico.id_debito)).subquery()


async def montar_panorama(db: AsyncSession, *, tenant_id: int) -> PanoramaVisaoGeralOut:
    agora = _utcnow()
    hoje = agora.date()

    # ---------------------------------------------------- valor por etapa
    etapas: list[EtapaValorItem] = []
    for chave, rotulo, situacao in _ETAPAS_DEBITO:
        valor, qtd = (await db.execute(
            select(func.coalesce(func.sum(Debito.valor_total), 0), func.count(Debito.id))
            .where(Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
                   Debito.situacao_tramitacao == situacao))).one()
        etapas.append(EtapaValorItem(chave=chave, rotulo=rotulo,
                                     qtd=int(qtd), valor=Decimal(valor)))

    # As duas últimas etapas são de PARCELA, não de débito: depois de
    # autorizada, o que anda é a parcela.
    for chave, rotulo, status in (("liberar", "A liberar", "A_PAGAR"),
                                  ("pagar", "Na tesouraria", "LIBERADA")):
        valor, qtd = (await db.execute(
            select(func.coalesce(func.sum(Parcela.valor), 0), func.count(Parcela.id))
            .join(Debito, Debito.id == Parcela.id_debito)
            .where(Parcela.tenant_id == tenant_id, Parcela.excluido.is_(False),
                   Parcela.status == status, Debito.excluido.is_(False), _TEM_RESERVA))).one()
        etapas.append(EtapaValorItem(chave=chave, rotulo=rotulo,
                                     qtd=int(qtd), valor=Decimal(valor)))

    # ------------------------------------------------------ envelhecimento
    sq = _sq_parado_desde(tenant_id)
    em_curso = Debito.situacao_tramitacao.in_(
        (est.AGUARDANDO_GESTOR, est.AGUARDANDO_VALIDACAO, est.AGUARDANDO_AUTORIDADE))
    linhas = (await db.execute(
        select(Debito.valor_total, sq.c.parado_desde)
        .join(sq, sq.c.id_debito == Debito.id)
        .where(Debito.tenant_id == tenant_id, Debito.excluido.is_(False), em_curso))).all()

    baldes: dict[str, tuple[int, Decimal]] = {r: (0, Decimal("0")) for _a, _b, r in _FAIXAS}
    mais_antigo_dias = 0
    for valor, parado_desde in linhas:
        dias = max((agora - parado_desde).days, 0)
        mais_antigo_dias = max(mais_antigo_dias, dias)
        for minimo, maximo, rotulo in _FAIXAS:
            if dias >= minimo and (maximo is None or dias <= maximo):
                q, v = baldes[rotulo]
                baldes[rotulo] = (q + 1, v + (valor or Decimal("0")))
                break
    envelhecimento = [EnvelhecimentoItem(faixa=r, qtd=baldes[r][0], valor=baldes[r][1])
                      for _a, _b, r in _FAIXAS]

    # -------------------------------------------------------- ritmo semanal
    inicio = hoje - timedelta(weeks=_SEMANAS - 1)
    inicio = inicio - timedelta(days=inicio.weekday())  # segunda-feira
    semana = func.to_char(func.date_trunc("week", Debito.criado_em), "YYYY-MM-DD")
    criados = dict((await db.execute(
        select(semana, func.count(Debito.id))
        .where(Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
               Debito.criado_em >= inicio)
        .group_by(semana))).all())

    semana_h = func.to_char(func.date_trunc("week", DebitoHistorico.criado_em), "YYYY-MM-DD")
    autorizados = dict((await db.execute(
        select(semana_h, func.count(DebitoHistorico.id))
        .where(DebitoHistorico.tenant_id == tenant_id,
               DebitoHistorico.acao == "AUTORIZADO",
               DebitoHistorico.criado_em >= inicio)
        .group_by(semana_h))).all())

    fluxo: list[FluxoSemanalItem] = []
    for i in range(_SEMANAS):
        dia = inicio + timedelta(weeks=i)
        chave = dia.isoformat()
        fluxo.append(FluxoSemanalItem(
            semana=chave, rotulo=dia.strftime("%d/%m"),
            entraram=int(criados.get(chave, 0)),
            autorizadas=int(autorizados.get(chave, 0))))

    em_curso_qtd = sum(i.qtd for i in envelhecimento)
    return PanoramaVisaoGeralOut(
        etapas=etapas, envelhecimento=envelhecimento, fluxo_semanal=fluxo,
        em_curso_qtd=em_curso_qtd,
        em_curso_valor=sum((i.valor for i in envelhecimento), Decimal("0")),
        mais_antigo_dias=mais_antigo_dias, apurado_em=agora)
