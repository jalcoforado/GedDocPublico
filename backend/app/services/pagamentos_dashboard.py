"""Dashboard financeiro de Pagamentos (R2+) — agregações somente leitura sobre
caixa/débitos/parcelas. Decimal fim-a-fim; sem dateutil (não é dependência do
projeto) — janela de meses calculada com aritmética manual de ano/mês."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    ContaBancaria, Contrato, Debito, FonteRecursos, Fornecedor, MovimentacaoConta,
    NaturezaDespesa, Parcela, UnidadeTrabalho,
)
from ..schemas.pagamentos import (
    ComposicaoItem, ContaAlertaItem, ContaDesatualizadaItem, DashboardAlertas, DashboardKpis, DashboardOut,
    ContaDisponibilidadeItem, DebitoResumoItem, FluxoMensalItem, ParcelaAlertaItem,
)
from . import pagamentos_caixa as caixa
from . import pagamentos_debitos as deb
from . import pagamentos_estados as est

# Traduções de status legado (§4.5) para as três dimensões — F5.
# "Tem reserva na conta pagadora": autorizada e nem paga nem conciliada
# (o ex-COM_RESERVA não continha ST_PAGO nem ST_CONCILIADO; a conciliação
# muda só a dimensão pagamento, a tramitação fica AUTORIZADA para sempre) (mesmo
# predicado de pagamentos_autorizacao.py/pagamentos_filas.py) — inclui
# ESTORNADA de propósito (ex-COM_RESERVA continha ST_ESTORNADO).
_TEM_RESERVA = and_(Debito.situacao_tramitacao == est.AUTORIZADA,
                    Debito.situacao_pagamento.notin_((est.PAGA, est.CONCILIADA)))
# Pré-autorização em curso (ex-ST_EM_VALIDACAO/ST_VALIDADO/AUTORIZAVEIS).
_PRE_AUTORIZACAO_EM_CURSO = Debito.situacao_tramitacao.in_(
    (est.AGUARDANDO_GESTOR, est.AGUARDANDO_VALIDACAO, est.AGUARDANDO_AUTORIDADE))
_CONDICAO_MAIORES = _PRE_AUTORIZACAO_EM_CURSO | _TEM_RESERVA
_TOP_NATUREZA_FONTE = 6
# Rankings (fornecedor/contrato) mostram mais linhas que as composições: a
# pergunta ali é "quem são os maiores", e 6 corta cedo demais numa
# prefeitura com dezenas de fornecedores ativos.
_TOP_RANKING = 10


def _utcnow() -> datetime:
    return datetime.utcnow()


def _mes_inicial(hoje: date, meses: int) -> date:
    """Primeiro dia do mês `meses - 1` meses antes do mês corrente (aritmética
    manual — sem dateutil)."""
    total = hoje.year * 12 + (hoje.month - 1) - (meses - 1)
    ano, mes0 = divmod(total, 12)
    return date(ano, mes0 + 1, 1)


async def montar_dashboard(db: AsyncSession, *, tenant_id: int, meses: int = 12,
                           filtros: dict[str, int] | None = None) -> DashboardOut:
    meses = max(3, min(24, meses))
    hoje = _utcnow().date()
    inicio = _mes_inicial(hoje, meses)

    fluxo_mensal = await _fluxo_mensal(db, tenant_id=tenant_id, inicio=inicio, meses=meses, hoje=hoje)
    kpis = await _kpis(db, tenant_id=tenant_id, hoje=hoje)
    filtros = {k: v for k, v in (filtros or {}).items() if v is not None}
    por_natureza = await _composicao_natureza(db, tenant_id=tenant_id, inicio=inicio, filtros=filtros)
    por_fonte = await _composicao_fonte(db, tenant_id=tenant_id, inicio=inicio, filtros=filtros)
    por_secretaria = await _por_secretaria(db, tenant_id=tenant_id, inicio=inicio, filtros=filtros)
    top_fornecedores = await _top_fornecedores(db, tenant_id=tenant_id, inicio=inicio, filtros=filtros)
    top_contratos = await _top_contratos(db, tenant_id=tenant_id, inicio=inicio, filtros=filtros)
    # Total do recorte: é o número que fecha com a soma das barras. Os KPIs de
    # SALDO não são recortáveis (saldo é da conta, não da secretaria), e por
    # isso a resposta diz quais dimensões estão ativas — a tela precisa avisar
    # que aqueles cartões continuam consolidados.
    total_filtrado = (await db.execute(
        select(func.coalesce(func.sum(MovimentacaoConta.valor), 0))
        .select_from(MovimentacaoConta)
        .join(Debito, Debito.id == MovimentacaoConta.id_debito)
        .where(*_filtro_pago(tenant_id, inicio, filtros)))).scalar_one()
    maiores_debitos = await _maiores_debitos(db, tenant_id=tenant_id)
    # Um cálculo só de saldo por conta, servindo alertas e disponibilidade.
    # (`_kpis` ainda faz a própria passada, de propósito: ele conta só contas
    # ATIVAS e o painel traz todas as não-excluídas — unificar mudaria os KPIs
    # em silêncio, que é outra fatia e outra conversa.)
    painel = await caixa.painel_caixa(db, tenant_id=tenant_id)
    disponibilidade_contas = await _disponibilidade_contas(db, tenant_id=tenant_id, painel=painel)
    alertas = await _alertas(db, tenant_id=tenant_id, hoje=hoje, painel=painel)

    return DashboardOut(kpis=kpis, fluxo_mensal=fluxo_mensal, por_natureza=por_natureza,
                        por_fonte=por_fonte, por_secretaria=por_secretaria,
                        top_fornecedores=top_fornecedores, top_contratos=top_contratos,
                        disponibilidade_contas=disponibilidade_contas,
                        maiores_debitos=maiores_debitos, alertas=alertas,
                        # Toda tela do painel precisa dizer de quando é o número
                        # que mostra (§5.1 do brief). O instante é o da APURAÇÃO,
                        # não o do dado: as agregações são calculadas na hora.
                        periodo_inicio=inicio, apurado_em=_utcnow(),
                        filtros_ativos=filtros, total_filtrado=Decimal(total_filtrado))


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
                       _TEM_RESERVA, *extra))

    # prospectivo: só parcelas ainda não vencidas (vencidas têm KPI próprio)
    a_pagar_30d, _qtd_30d = (await db.execute(
        _soma_qtd_parcelas(Parcela.vencimento >= hoje,
                           Parcela.vencimento <= limite_30d))).one()

    vencidas_valor, vencidas_qtd = (await db.execute(
        _soma_qtd_parcelas(Parcela.vencimento < hoje))).one()

    aguardando_aprovacao_qtd = (await db.execute(select(func.count(Debito.id)).where(
        Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
        Debito.situacao_tramitacao.in_((est.AGUARDANDO_GESTOR, est.AGUARDANDO_VALIDACAO)),
    ))).scalar_one()
    aguardando_autorizacao_qtd = (await db.execute(select(func.count(Debito.id)).where(
        Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
        Debito.situacao_tramitacao == est.AGUARDANDO_AUTORIDADE,
    ))).scalar_one()

    return DashboardKpis(
        saldo_total=saldo_total, disponivel_total=disponivel_total,
        comprometido_total=comprometido_total, a_pagar_30d=a_pagar_30d,
        vencidas_qtd=vencidas_qtd, vencidas_valor=vencidas_valor, pago_no_mes=pago_no_mes,
        aguardando_aprovacao_qtd=aguardando_aprovacao_qtd,
        aguardando_autorizacao_qtd=aguardando_autorizacao_qtd,
    )


def _top6_mais_outras(rows) -> list[ComposicaoItem]:
    return _top_mais_outras(rows, limite=_TOP_NATUREZA_FONTE)


def _top_mais_outras(rows, *, limite: int,
                     rotulo_resto: str = "Outras") -> list[ComposicaoItem]:
    """Top `limite` por valor, e o resto somado numa linha só.

    A linha "Outras" não é enfeite: sem ela o gráfico mostra uma fatia do
    gasto com cara de total, e quem lê conclui que a prefeitura gastou menos
    do que gastou. Com ela, a soma das barras fecha com o período.
    """
    ordenadas = sorted(rows, key=lambda r: r[2], reverse=True)
    top = ordenadas[:limite]
    resto = ordenadas[limite:]
    # `id` é o que torna a barra clicável. A linha agregada ("Outras") NÃO
    # recebe id de propósito: ela junta várias dimensões, e clicar nela não
    # significaria um recorte, significaria vários ao mesmo tempo.
    itens = [ComposicaoItem(codigo=r[0], descricao=r[1], valor=r[2],
                            id=(r[3] if len(r) > 3 else None)) for r in top]
    if resto:
        soma_resto = sum((r[2] for r in resto), Decimal("0"))
        itens.append(ComposicaoItem(codigo="—", descricao=rotulo_resto, valor=soma_resto))
    return itens


# Base comum das composições e rankings: o que SAIU da conta como pagamento no
# período. Mesma medida de `_composicao_natureza`/`_composicao_fonte` de
# propósito — duas medidas diferentes no mesmo painel fariam dois gráficos
# discordarem sobre quanto a prefeitura gastou, e não há como o leitor saber
# qual acreditar.
# Dimensões pelas quais o painel deixa recortar. Chave → coluna do débito.
# Só entram dimensões que o débito carrega de verdade: filtrar por algo que
# não está na linha exigiria inferência, e inferência silenciosa é como se
# erra o número de um painel.
_DIMENSOES = {
    "unidade": Debito.id_unidade,
    "fornecedor": Debito.id_fornecedor,
    "contrato": Debito.id_contrato,
    "natureza": Debito.id_natureza,
    "fonte": Debito.id_fonte_recursos,
}


def _filtro_pago(tenant_id: int, inicio: date, filtros: dict[str, int] | None = None):
    """Condições da medida "pago no período", mais o recorte ativo.

    O MESMO filtro vale para todas as agregações, de propósito: se o recorte
    valesse para uns gráficos e não para outros, o leitor somaria barras de
    escopos diferentes sem ter como perceber.
    """
    cond = [MovimentacaoConta.tenant_id == tenant_id, MovimentacaoConta.excluido.is_(False),
            MovimentacaoConta.origem == "PAGAMENTO", MovimentacaoConta.data >= inicio,
            Debito.tenant_id == tenant_id, Debito.excluido.is_(False)]
    for chave, valor in (filtros or {}).items():
        coluna = _DIMENSOES.get(chave)
        if coluna is not None and valor is not None:
            cond.append(coluna == valor)
    return tuple(cond)


async def _por_secretaria(db, *, tenant_id: int, inicio: date,
                          filtros: dict | None = None) -> list[ComposicaoItem]:
    """Quanto cada secretaria/unidade gastou no período (pergunta nº 10 do prefeito).

    A unidade vem de `Debito.id_unidade`, que é NOT NULL desde a F1 — antes
    dela só existia via contrato, e débito sem contrato não tinha unidade
    nenhuma. É por isso que esta agregação só foi possível agora.
    """
    soma = func.sum(MovimentacaoConta.valor)
    stmt = (select(func.coalesce(UnidadeTrabalho.sigla, "—"),
                   UnidadeTrabalho.unidade_trabalho, soma, UnidadeTrabalho.id)
            .select_from(MovimentacaoConta)
            .join(Debito, Debito.id == MovimentacaoConta.id_debito)
            .join(UnidadeTrabalho, UnidadeTrabalho.id == Debito.id_unidade)
            .where(*_filtro_pago(tenant_id, inicio, filtros),
                   UnidadeTrabalho.tenant_id == tenant_id)
            .group_by(UnidadeTrabalho.sigla, UnidadeTrabalho.unidade_trabalho, UnidadeTrabalho.id)
            .order_by(soma.desc()))
    return _top6_mais_outras((await db.execute(stmt)).all())


async def _top_fornecedores(db, *, tenant_id: int, inicio: date,
                            filtros: dict | None = None,
                            limite: int = _TOP_RANKING) -> list[ComposicaoItem]:
    """Com quem o município está gastando (pergunta nº 11)."""
    soma = func.sum(MovimentacaoConta.valor)
    stmt = (select(Fornecedor.cnpj_cpf, Fornecedor.nome, soma, Fornecedor.id)
            .select_from(MovimentacaoConta)
            .join(Debito, Debito.id == MovimentacaoConta.id_debito)
            .join(Fornecedor, Fornecedor.id == Debito.id_fornecedor)
            .where(*_filtro_pago(tenant_id, inicio, filtros),
                   Fornecedor.tenant_id == tenant_id, Fornecedor.excluido.is_(False))
            .group_by(Fornecedor.cnpj_cpf, Fornecedor.nome, Fornecedor.id)
            .order_by(soma.desc()))
    return _top_mais_outras((await db.execute(stmt)).all(), limite=limite,
                            rotulo_resto="Demais fornecedores")


async def _top_contratos(db, *, tenant_id: int, inicio: date,
                         filtros: dict | None = None,
                         limite: int = _TOP_RANKING) -> list[ComposicaoItem]:
    """Quais contratos mais pesam na despesa (pergunta nº 12).

    `Debito.id_contrato` é nulo em despesa sem contrato, e o `outerjoin` a
    mantém no ranking sob "Sem contrato". Deixá-la de fora daria um ranking
    que não fecha com o total pago do período — o leitor somaria as barras,
    acharia menos do que o painel diz no KPI, e não teria como saber por quê.
    """
    soma = func.sum(MovimentacaoConta.valor)
    rotulo = func.coalesce(Contrato.numero, "Sem contrato")
    stmt = (select(rotulo, func.coalesce(Contrato.objeto, "Despesa sem contrato"), soma,
                   Contrato.id)
            .select_from(MovimentacaoConta)
            .join(Debito, Debito.id == MovimentacaoConta.id_debito)
            .outerjoin(Contrato, and_(Contrato.id == Debito.id_contrato,
                                      Contrato.tenant_id == tenant_id,
                                      Contrato.excluido.is_(False)))
            .where(*_filtro_pago(tenant_id, inicio, filtros))
            .group_by(rotulo, Contrato.objeto, Contrato.id)
            .order_by(soma.desc()))
    return _top_mais_outras((await db.execute(stmt)).all(), limite=limite,
                            rotulo_resto="Demais contratos")


async def _composicao_natureza(db, *, tenant_id: int, inicio: date,
                               filtros: dict | None = None) -> list[ComposicaoItem]:
    soma = func.sum(MovimentacaoConta.valor)
    stmt = (select(NaturezaDespesa.codigo, NaturezaDespesa.descricao, soma, NaturezaDespesa.id)
            .select_from(MovimentacaoConta)
            .join(Debito, Debito.id == MovimentacaoConta.id_debito)
            .join(NaturezaDespesa, NaturezaDespesa.id == Debito.id_natureza)
            .where(*_filtro_pago(tenant_id, inicio, filtros),
                   NaturezaDespesa.tenant_id == tenant_id, NaturezaDespesa.excluido.is_(False))
            .group_by(NaturezaDespesa.codigo, NaturezaDespesa.descricao, NaturezaDespesa.id)
            .order_by(soma.desc()))
    return _top6_mais_outras((await db.execute(stmt)).all())


async def _composicao_fonte(db, *, tenant_id: int, inicio: date,
                            filtros: dict | None = None) -> list[ComposicaoItem]:
    # Fonte vem direto do débito (v2.0) — não mais derivada da conta.
    soma = func.sum(MovimentacaoConta.valor)
    stmt = (select(FonteRecursos.codigo, FonteRecursos.descricao, soma, FonteRecursos.id)
            .select_from(MovimentacaoConta)
            .join(Debito, Debito.id == MovimentacaoConta.id_debito)
            .join(FonteRecursos, FonteRecursos.id == Debito.id_fonte_recursos)
            .where(*_filtro_pago(tenant_id, inicio, filtros),
                   FonteRecursos.tenant_id == tenant_id, FonteRecursos.excluido.is_(False))
            .group_by(FonteRecursos.codigo, FonteRecursos.descricao, FonteRecursos.id)
            .order_by(soma.desc()))
    return _top6_mais_outras((await db.execute(stmt)).all())


async def _maiores_debitos(db, *, tenant_id: int, limite: int = 10) -> list[DebitoResumoItem]:
    stmt = (select(Debito).where(Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
                                 _CONDICAO_MAIORES)
            .order_by(Debito.valor_total.desc()).limit(limite))
    debitos = list((await db.execute(stmt)).scalars().all())
    nomes = await deb.nomes_fornecedores(db, tenant_id=tenant_id,
                                         ids={d.id_fornecedor for d in debitos})
    return [DebitoResumoItem(
        id=d.id, nome_fornecedor=nomes.get(d.id_fornecedor, "?"),
        descricao=d.descricao, valor_total=d.valor_total,
        # Calculado, não lido de coluna (F5) — mesmo valor que o legado dava.
        status=est.status_legado(d.situacao_tramitacao, d.situacao_fila, d.situacao_pagamento),
        competencia=d.competencia, situacao_tramitacao=d.situacao_tramitacao,
        situacao_pagamento=d.situacao_pagamento) for d in debitos]


async def _disponibilidade_contas(db, *, tenant_id: int,
                                  painel: list) -> list[ContaDisponibilidadeItem]:
    """Monta a barra empilhada de cada conta a partir do painel de caixa.

    Não recalcula saldo: recebe o `painel_caixa` que o dashboard já pediu uma
    vez. Dois cálculos do mesmo saldo na mesma resposta podem divergir se
    alguém pagar no meio, e o painel mostraria dois números para a mesma
    conta.

    A fonte de recursos entra aqui por uma razão de leitura, não de enfeite:
    saldo em conta de FUNDEB não é dinheiro que a prefeitura possa usar para
    qualquer coisa, e uma barra verde sem a destinação ao lado convida
    exatamente esse erro (§5.2 do brief: "não trate recursos vinculados como
    dinheiro disponível").
    """
    if not painel:
        return []
    ids = [c.id_conta for c in painel]
    stmt = (select(ContaBancaria.id, FonteRecursos.codigo, FonteRecursos.descricao,
                   ContaBancaria.finalidade, FonteRecursos.tipo_vinculacao)
            .select_from(ContaBancaria)
            .outerjoin(FonteRecursos, and_(FonteRecursos.id == ContaBancaria.id_fonte_recursos,
                                           FonteRecursos.tenant_id == tenant_id))
            .where(ContaBancaria.tenant_id == tenant_id, ContaBancaria.id.in_(ids)))
    fontes = {row[0]: (row[1], row[2], row[3], row[4]) for row in (await db.execute(stmt)).all()}

    itens: list[ContaDisponibilidadeItem] = []
    for c in painel:
        codigo, descricao, finalidade, vinculacao = fontes.get(
            c.id_conta, (None, None, None, None))
        itens.append(ContaDisponibilidadeItem(
            id_conta=c.id_conta, nome=c.nome, banco=c.banco,
            grupo_despesa=c.grupo_despesa,
            fonte_codigo=codigo, fonte_descricao=descricao, finalidade=finalidade,
            fonte_vinculacao=vinculacao,
            saldo_atual=c.saldo_atual, disponivel=c.disponivel,
            comprometido=c.comprometido, bloqueado=c.bloqueado,
            insuficiencia=max(Decimal("0"), -c.disponivel),
            abaixo_minimo=c.abaixo_minimo,
        ))
    # Menor disponibilidade primeiro: a conta em risco é a que o gestor
    # precisa ver, e ela é justamente a que um "maior saldo primeiro"
    # empurraria para o fim da lista. A tela deixa reordenar.
    itens.sort(key=lambda i: i.disponivel)
    return itens


async def _alertas(db, *, tenant_id: int, hoje: date, limite: int = 10,
                   painel: list | None = None) -> DashboardAlertas:
    base = (select(Parcela, Debito)
            .join(Debito, Debito.id == Parcela.id_debito)
            .where(Parcela.tenant_id == tenant_id, Parcela.excluido.is_(False),
                   Parcela.status.in_(("A_PAGAR", "LIBERADA")), Debito.excluido.is_(False),
                   _TEM_RESERVA))

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

    painel = painel if painel is not None else await caixa.painel_caixa(db, tenant_id=tenant_id)
    contas_abaixo_minimo = [ContaAlertaItem(id_conta=c.id_conta, nome=c.nome,
                                            saldo_atual=c.saldo_atual,
                                            saldo_minimo_alerta=c.saldo_minimo_alerta)
                            for c in painel if c.abaixo_minimo]

    # RF-SLD-06: contas sem movimentação/atualização de saldo no dia corrente.
    contas_desatualizadas: list[ContaDesatualizadaItem] = []
    for c in painel:
        atualizado = await caixa.ultima_atualizacao_conta(db, tenant_id=tenant_id, conta_id=c.id_conta)
        if atualizado is None or atualizado.date() < hoje:
            contas_desatualizadas.append(ContaDesatualizadaItem(
                id_conta=c.id_conta, nome=c.nome, atualizado_em=atualizado))

    return DashboardAlertas(parcelas_vencidas=parcelas_vencidas, parcelas_7dias=parcelas_7dias,
                            contas_abaixo_minimo=contas_abaixo_minimo,
                            contas_desatualizadas=contas_desatualizadas)
