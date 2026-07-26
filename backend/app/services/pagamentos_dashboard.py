"""Dashboard financeiro de Pagamentos (R2+) — agregações somente leitura sobre
caixa/débitos/parcelas. Decimal fim-a-fim; sem dateutil (não é dependência do
projeto) — janela de meses calculada com aritmética manual de ano/mês."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ContaBancaria, Debito, FonteRecursos, MovimentacaoConta, NaturezaDespesa, Parcela
from ..schemas.pagamentos import (
    ComposicaoItem, ContaAlertaItem, DashboardAlertas, DashboardKpis, DashboardOut,
    DebitoResumoItem, FluxoMensalItem, ParcelaAlertaItem,
)
from . import pagamentos_caixa as caixa
from . import pagamentos_debitos as deb

_STATUS_COMPROMETIDO = deb.COM_RESERVA
_STATUS_MAIORES = (deb.ST_EM_VALIDACAO, deb.ST_VALIDADO, *deb.AUTORIZAVEIS, *deb.COM_RESERVA)
_TOP_NATUREZA_FONTE = 6


def _utcnow() -> datetime:
    return datetime.utcnow()


def _mes_inicial(hoje: date, meses: int) -> date:
    """Primeiro dia do mês `meses - 1` meses antes do mês corrente (aritmética
    manual — sem dateutil)."""
    total = hoje.year * 12 + (hoje.month - 1) - (meses - 1)
    ano, mes0 = divmod(total, 12)
    return date(ano, mes0 + 1, 1)


async def montar_dashboard(db: AsyncSession, *, tenant_id: int, meses: int = 12) -> DashboardOut:
    meses = max(3, min(24, meses))
    hoje = _utcnow().date()
    inicio = _mes_inicial(hoje, meses)

    fluxo_mensal = await _fluxo_mensal(db, tenant_id=tenant_id, inicio=inicio, meses=meses, hoje=hoje)
    kpis = await _kpis(db, tenant_id=tenant_id, hoje=hoje)
    por_natureza = await _composicao_natureza(db, tenant_id=tenant_id, inicio=inicio)
    por_fonte = await _composicao_fonte(db, tenant_id=tenant_id, inicio=inicio)
    maiores_debitos = await _maiores_debitos(db, tenant_id=tenant_id)
    alertas = await _alertas(db, tenant_id=tenant_id, hoje=hoje)

    return DashboardOut(kpis=kpis, fluxo_mensal=fluxo_mensal, por_natureza=por_natureza,
                        por_fonte=por_fonte, maiores_debitos=maiores_debitos, alertas=alertas)


async def _fluxo_mensal(db, *, tenant_id: int, inicio: date, meses: int, hoje: date) -> list[FluxoMensalItem]:
    mes_col = func.to_char(func.date_trunc("month", MovimentacaoConta.data), "YYYY-MM")
    stmt = (select(mes_col, MovimentacaoConta.tipo, func.sum(MovimentacaoConta.valor))
            .where(MovimentacaoConta.tenant_id == tenant_id, MovimentacaoConta.excluido.is_(False),
                   MovimentacaoConta.data >= inicio)
            .group_by(mes_col, MovimentacaoConta.tipo))
    rows = (await db.execute(stmt)).all()
    valores: dict[str, dict[str, Decimal]] = {}
    for mes, tipo, total in rows:
        valores.setdefault(mes, {})[tipo] = total or Decimal("0")

    itens: list[FluxoMensalItem] = []
    total_meses = hoje.year * 12 + (hoje.month - 1)
    for offset in range(meses - 1, -1, -1):
        total = total_meses - offset
        ano, mes0 = divmod(total, 12)
        chave = f"{ano:04d}-{mes0 + 1:02d}"
        dados = valores.get(chave, {})
        itens.append(FluxoMensalItem(
            mes=chave, entradas=dados.get("ENTRADA", Decimal("0")),
            saidas=dados.get("SAIDA", Decimal("0"))))
    return itens


async def _kpis(db, *, tenant_id: int, hoje: date) -> DashboardKpis:
    contas = (await db.execute(select(ContaBancaria).where(
        ContaBancaria.tenant_id == tenant_id, ContaBancaria.excluido.is_(False),
        ContaBancaria.ativa.is_(True)))).scalars().all()
    saldo_total = Decimal("0"); disponivel_total = Decimal("0"); comprometido_total = Decimal("0")
    for conta in contas:
        saldo = await caixa.saldo_conta(db, tenant_id=tenant_id, conta_id=conta.id)
        saldo_total += saldo.saldo_atual
        disponivel_total += saldo.disponivel
        comprometido_total += saldo.comprometido

    pago_no_mes = (await db.execute(select(func.coalesce(func.sum(MovimentacaoConta.valor), 0)).where(
        MovimentacaoConta.tenant_id == tenant_id, MovimentacaoConta.excluido.is_(False),
        MovimentacaoConta.origem == "PAGAMENTO",
        func.date_trunc("month", MovimentacaoConta.data) == func.date_trunc("month", hoje),
    ))).scalar_one()

    limite_30d = hoje + timedelta(days=30)

    def _soma_qtd_parcelas(*extra):
        return (select(func.coalesce(func.sum(Parcela.valor), 0), func.count(Parcela.id))
                .join(Debito, Debito.id == Parcela.id_debito)
                .where(Parcela.tenant_id == tenant_id, Parcela.excluido.is_(False),
                       Parcela.status.in_(("A_PAGAR", "LIBERADA")), Debito.excluido.is_(False),
                       Debito.status.in_(_STATUS_COMPROMETIDO), *extra))

    # prospectivo: só parcelas ainda não vencidas (vencidas têm KPI próprio)
    a_pagar_30d, _qtd_30d = (await db.execute(
        _soma_qtd_parcelas(Parcela.vencimento >= hoje,
                           Parcela.vencimento <= limite_30d))).one()

    vencidas_valor, vencidas_qtd = (await db.execute(
        _soma_qtd_parcelas(Parcela.vencimento < hoje))).one()

    aguardando_aprovacao_qtd = (await db.execute(select(func.count(Debito.id)).where(
        Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
        Debito.status == deb.ST_EM_VALIDACAO))).scalar_one()
    aguardando_autorizacao_qtd = (await db.execute(select(func.count(Debito.id)).where(
        Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
        Debito.status.in_(deb.AUTORIZAVEIS)))).scalar_one()

    return DashboardKpis(
        saldo_total=saldo_total, disponivel_total=disponivel_total,
        comprometido_total=comprometido_total, a_pagar_30d=a_pagar_30d,
        vencidas_qtd=vencidas_qtd, vencidas_valor=vencidas_valor, pago_no_mes=pago_no_mes,
        aguardando_aprovacao_qtd=aguardando_aprovacao_qtd,
        aguardando_autorizacao_qtd=aguardando_autorizacao_qtd,
    )


def _top6_mais_outras(rows: list[tuple[str, str, Decimal]]) -> list[ComposicaoItem]:
    ordenadas = sorted(rows, key=lambda r: r[2], reverse=True)
    top = ordenadas[:_TOP_NATUREZA_FONTE]
    resto = ordenadas[_TOP_NATUREZA_FONTE:]
    itens = [ComposicaoItem(codigo=c, descricao=d, valor=v) for c, d, v in top]
    if resto:
        soma_resto = sum((v for _c, _d, v in resto), Decimal("0"))
        itens.append(ComposicaoItem(codigo="—", descricao="Outras", valor=soma_resto))
    return itens


async def _composicao_natureza(db, *, tenant_id: int, inicio: date) -> list[ComposicaoItem]:
    stmt = (select(NaturezaDespesa.codigo, NaturezaDespesa.descricao,
                   func.sum(MovimentacaoConta.valor))
            .select_from(MovimentacaoConta)
            .join(Debito, Debito.id == MovimentacaoConta.id_debito)
            .join(NaturezaDespesa, NaturezaDespesa.id == Debito.id_natureza)
            .where(MovimentacaoConta.tenant_id == tenant_id, MovimentacaoConta.excluido.is_(False),
                   MovimentacaoConta.origem == "PAGAMENTO", MovimentacaoConta.data >= inicio,
                   Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
                   NaturezaDespesa.tenant_id == tenant_id, NaturezaDespesa.excluido.is_(False))
            .group_by(NaturezaDespesa.codigo, NaturezaDespesa.descricao)
            .order_by(func.sum(MovimentacaoConta.valor).desc()))
    rows = (await db.execute(stmt)).all()
    return _top6_mais_outras(rows)


async def _composicao_fonte(db, *, tenant_id: int, inicio: date) -> list[ComposicaoItem]:
    # Fonte vem direto do débito (v2.0) — não mais derivada da conta.
    stmt = (select(FonteRecursos.codigo, FonteRecursos.descricao,
                   func.sum(MovimentacaoConta.valor))
            .select_from(MovimentacaoConta)
            .join(Debito, Debito.id == MovimentacaoConta.id_debito)
            .join(FonteRecursos, FonteRecursos.id == Debito.id_fonte_recursos)
            .where(MovimentacaoConta.tenant_id == tenant_id, MovimentacaoConta.excluido.is_(False),
                   MovimentacaoConta.origem == "PAGAMENTO", MovimentacaoConta.data >= inicio,
                   Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
                   FonteRecursos.tenant_id == tenant_id, FonteRecursos.excluido.is_(False))
            .group_by(FonteRecursos.codigo, FonteRecursos.descricao)
            .order_by(func.sum(MovimentacaoConta.valor).desc()))
    rows = (await db.execute(stmt)).all()
    return _top6_mais_outras(rows)


async def _maiores_debitos(db, *, tenant_id: int, limite: int = 10) -> list[DebitoResumoItem]:
    stmt = (select(Debito).where(Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
                                 Debito.status.in_(_STATUS_MAIORES))
            .order_by(Debito.valor_total.desc()).limit(limite))
    debitos = list((await db.execute(stmt)).scalars().all())
    nomes = await deb.nomes_fornecedores(db, tenant_id=tenant_id,
                                         ids={d.id_fornecedor for d in debitos})
    return [DebitoResumoItem(id=d.id, nome_fornecedor=nomes.get(d.id_fornecedor, "?"),
                             descricao=d.descricao, valor_total=d.valor_total,
                             status=d.status, competencia=d.competencia) for d in debitos]


async def _alertas(db, *, tenant_id: int, hoje: date, limite: int = 10) -> DashboardAlertas:
    base = (select(Parcela, Debito)
            .join(Debito, Debito.id == Parcela.id_debito)
            .where(Parcela.tenant_id == tenant_id, Parcela.excluido.is_(False),
                   Parcela.status.in_(("A_PAGAR", "LIBERADA")), Debito.excluido.is_(False),
                   Debito.status.in_(_STATUS_COMPROMETIDO)))

    vencidas_rows = (await db.execute(base.where(Parcela.vencimento < hoje)
        .order_by(Parcela.vencimento).limit(limite))).all()
    proximas_rows = (await db.execute(base.where(
        Parcela.vencimento >= hoje, Parcela.vencimento <= hoje + timedelta(days=7))
        .order_by(Parcela.vencimento).limit(limite))).all()

    ids_fornecedor = {d.id_fornecedor for _p, d in vencidas_rows} | {d.id_fornecedor for _p, d in proximas_rows}
    nomes = await deb.nomes_fornecedores(db, tenant_id=tenant_id, ids=ids_fornecedor)

    def _item(p: Parcela, d: Debito) -> ParcelaAlertaItem:
        return ParcelaAlertaItem(id=p.id, id_debito=d.id, nome_fornecedor=nomes.get(d.id_fornecedor, "?"),
                                 valor=p.valor, vencimento=p.vencimento,
                                 dias_atraso=max((hoje - p.vencimento).days, 0))

    parcelas_vencidas = [_item(p, d) for p, d in vencidas_rows]
    parcelas_7dias = [_item(p, d) for p, d in proximas_rows]

    painel = await caixa.painel_caixa(db, tenant_id=tenant_id)
    contas_abaixo_minimo = [ContaAlertaItem(id_conta=c.id_conta, nome=c.nome,
                                            saldo_atual=c.saldo_atual,
                                            saldo_minimo_alerta=c.saldo_minimo_alerta)
                            for c in painel if c.abaixo_minimo]

    return DashboardAlertas(parcelas_vencidas=parcelas_vencidas, parcelas_7dias=parcelas_7dias,
                            contas_abaixo_minimo=contas_abaixo_minimo)
