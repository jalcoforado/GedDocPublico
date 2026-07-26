"""Filas agregadas de Pagamentos (rito): autorização, liberação e tesouraria.
Agrupamento por conta bancária (com saldo/disponível), enriquecimento de
aprovador/liberador via histórico e número da OP mais recente do débito."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    ContaBancaria, Debito, DebitoHistorico, FonteRecursos, NaturezaDespesa, OrdemPagamento,
    OrdemPagamentoDebito, Parcela,
)
from ..schemas.pagamentos import (
    DebitoFilaItem, FilaAutorizacaoFonteGrupo, FilaLiberacaoGrupo, FilaTesourariaOut, GrupoConta,
    ParcelaFilaLibItem, ParcelaTesourariaItem,
)
from . import pagamentos_autorizacao as aut
from . import pagamentos_caixa as caixa
from .pagamentos_debitos import AUTORIZAVEIS, EM_TESOURARIA, ST_AUTORIZADO, ST_ESTORNADO, nomes_fornecedores, nomes_usuarios


async def _contas_by_id(db, *, tenant_id: int, ids: set[int]) -> dict[int, ContaBancaria]:
    if not ids:
        return {}
    rows = (await db.execute(select(ContaBancaria).where(
        ContaBancaria.tenant_id == tenant_id, ContaBancaria.id.in_(ids),
        ContaBancaria.excluido.is_(False)))).scalars().all()
    return {c.id: c for c in rows}


async def _naturezas_by_id(db, *, tenant_id: int, ids: set[int]) -> dict[int, NaturezaDespesa]:
    if not ids:
        return {}
    rows = (await db.execute(select(NaturezaDespesa).where(
        NaturezaDespesa.tenant_id == tenant_id, NaturezaDespesa.id.in_(ids),
        NaturezaDespesa.excluido.is_(False)))).scalars().all()
    return {n.id: n for n in rows}


async def _grupo_conta(db, *, tenant_id: int, conta: ContaBancaria) -> GrupoConta:
    saldo = await caixa.saldo_conta(db, tenant_id=tenant_id, conta_id=conta.id)
    minimo = conta.saldo_minimo_alerta or Decimal("0")
    return GrupoConta(id_conta=conta.id, nome_conta=conta.nome, disponivel=saldo.disponivel,
                      abaixo_minimo=saldo.saldo_atual < minimo)


async def _ultimos_aprovados(db, *, tenant_id: int, debito_ids: set[int]) -> dict[int, DebitoHistorico]:
    """Última validação do histórico, por débito (quem conferiu a documentação)."""
    if not debito_ids:
        return {}
    rows = (await db.execute(select(DebitoHistorico).where(
        DebitoHistorico.tenant_id == tenant_id, DebitoHistorico.id_debito.in_(debito_ids),
        DebitoHistorico.acao == "VALIDADO")
        .order_by(DebitoHistorico.id.desc()))).scalars().all()
    out: dict[int, DebitoHistorico] = {}
    for h in rows:
        out.setdefault(h.id_debito, h)
    return out


async def _ops_recentes(db, *, tenant_id: int, debito_ids: set[int]) -> dict[int, OrdemPagamento]:
    """Ordem de pagamento mais recente que contém o débito."""
    if not debito_ids:
        return {}
    rows = (await db.execute(select(OrdemPagamentoDebito.id_debito, OrdemPagamento)
        .join(OrdemPagamento, OrdemPagamento.id == OrdemPagamentoDebito.id_ordem)
        .where(OrdemPagamentoDebito.tenant_id == tenant_id,
               OrdemPagamentoDebito.id_debito.in_(debito_ids))
        .order_by(OrdemPagamento.id.desc()))).all()
    out: dict[int, OrdemPagamento] = {}
    for id_debito, op in rows:
        out.setdefault(id_debito, op)
    return out


async def _qtd_parcelas_por_debito(db, *, tenant_id: int, debito_ids: set[int]) -> dict[int, int]:
    if not debito_ids:
        return {}
    rows = (await db.execute(select(Parcela.id_debito, Parcela.id).where(
        Parcela.tenant_id == tenant_id, Parcela.id_debito.in_(debito_ids),
        Parcela.excluido.is_(False)))).all()
    out: dict[int, int] = {}
    for id_debito, _pid in rows:
        out[id_debito] = out.get(id_debito, 0) + 1
    return out


def _dias_atraso(vencimento: date, hoje: date) -> tuple[bool, int]:
    vencida = vencimento < hoje
    return vencida, (hoje - vencimento).days if vencida else 0


async def _fontes_by_id(db, *, tenant_id: int, ids: set[int]) -> dict[int, FonteRecursos]:
    if not ids:
        return {}
    rows = (await db.execute(select(FonteRecursos).where(
        FonteRecursos.tenant_id == tenant_id, FonteRecursos.id.in_(ids),
        FonteRecursos.excluido.is_(False)))).scalars().all()
    return {f.id: f for f in rows}


async def fila_autorizacao(db: AsyncSession, *, tenant_id: int) -> list[FilaAutorizacaoFonteGrupo]:
    """Débitos APROVADO agrupados por FONTE (v2.0). Cada grupo traz os débitos e
    as contas elegíveis (ativas da fonte, com saldo) entre as quais o autorizador
    escolhe a conta pagadora. Grupos por código de fonte; dentro do grupo,
    urgentes primeiro, depois competência asc, valor desc."""
    debitos = list((await db.execute(select(Debito).where(
        Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
        Debito.status.in_(AUTORIZAVEIS)))).scalars().all())
    if not debitos:
        return []

    fontes = await _fontes_by_id(db, tenant_id=tenant_id, ids={d.id_fonte_recursos for d in debitos})
    naturezas = await _naturezas_by_id(db, tenant_id=tenant_id, ids={d.id_natureza for d in debitos})
    nomes_f = await nomes_fornecedores(db, tenant_id=tenant_id, ids={d.id_fornecedor for d in debitos})
    aprovados = await _ultimos_aprovados(db, tenant_id=tenant_id, debito_ids={d.id for d in debitos})
    nomes_apr = await nomes_usuarios(
        db, tenant_id=tenant_id,
        ids={h.id_usuario for h in aprovados.values() if h.id_usuario is not None})

    por_fonte: dict[int, list[Debito]] = {}
    for d in debitos:
        por_fonte.setdefault(d.id_fonte_recursos, []).append(d)

    grupos: list[FilaAutorizacaoFonteGrupo] = []
    for fonte_id, ds in por_fonte.items():
        fonte = fontes.get(fonte_id)
        itens: list[DebitoFilaItem] = []
        for d in sorted(ds, key=lambda x: (not x.urgente, x.competencia, -x.valor_total)):
            hist = aprovados.get(d.id)
            nat = naturezas.get(d.id_natureza)
            itens.append(DebitoFilaItem(
                id=d.id, nome_fornecedor=nomes_f.get(d.id_fornecedor, "?"), descricao=d.descricao,
                natureza_codigo=nat.codigo if nat else "?",
                natureza_descricao=nat.descricao if nat else "?",
                competencia=d.competencia, urgente=d.urgente,
                aprovado_por=nomes_apr.get(hist.id_usuario) if hist and hist.id_usuario else None,
                aprovado_em=hist.criado_em if hist else None,
                valor_total=d.valor_total))
        contas = await aut.contas_elegiveis(db, tenant_id=tenant_id, id_fonte=fonte_id)
        grupos.append(FilaAutorizacaoFonteGrupo(
            id_fonte=fonte_id, codigo_fonte=fonte.codigo if fonte else "?",
            descricao_fonte=fonte.descricao if fonte else "?",
            debitos=itens, contas_elegiveis=contas))
    return sorted(grupos, key=lambda g: g.codigo_fonte)


async def fila_liberacao(db: AsyncSession, *, tenant_id: int) -> list[FilaLiberacaoGrupo]:
    """Parcelas A_PAGAR de débitos autorizados/na tesouraria, agrupadas por conta
    (nome asc); dentro do grupo, vencimento asc."""
    debitos = list((await db.execute(select(Debito).where(
        Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
        Debito.status.in_((ST_AUTORIZADO, ST_ESTORNADO, *EM_TESOURARIA))))).scalars().all())
    if not debitos:
        return []
    debitos_por_id = {d.id: d for d in debitos}

    parcelas = list((await db.execute(select(Parcela).where(
        Parcela.tenant_id == tenant_id, Parcela.excluido.is_(False), Parcela.status == "A_PAGAR",
        Parcela.id_debito.in_(debitos_por_id.keys())))).scalars().all())
    if not parcelas:
        return []

    # Liberação/tesouraria operam sobre a conta PAGADORA (reservada na autorização).
    contas = await _contas_by_id(db, tenant_id=tenant_id, ids={d.id_conta_pagadora for d in debitos})
    nomes_f = await nomes_fornecedores(db, tenant_id=tenant_id, ids={d.id_fornecedor for d in debitos})
    ops = await _ops_recentes(db, tenant_id=tenant_id, debito_ids=set(debitos_por_id.keys()))
    qtds = await _qtd_parcelas_por_debito(db, tenant_id=tenant_id, debito_ids=set(debitos_por_id.keys()))
    hoje = datetime.utcnow().date()

    por_conta: dict[int, list[Parcela]] = {}
    for p in parcelas:
        d = debitos_por_id[p.id_debito]
        por_conta.setdefault(d.id_conta_pagadora, []).append(p)

    grupos: list[FilaLiberacaoGrupo] = []
    for conta_id, ps in por_conta.items():
        conta = contas[conta_id]
        base = await _grupo_conta(db, tenant_id=tenant_id, conta=conta)
        itens: list[ParcelaFilaLibItem] = []
        for p in sorted(ps, key=lambda x: x.vencimento):
            d = debitos_por_id[p.id_debito]
            op = ops.get(d.id)
            vencida, atraso = _dias_atraso(p.vencimento, hoje)
            itens.append(ParcelaFilaLibItem(
                id=p.id, id_debito=d.id, nome_fornecedor=nomes_f.get(d.id_fornecedor, "?"),
                descricao_debito=d.descricao, numero=p.numero,
                qtd_parcelas=qtds.get(d.id, 0), valor=p.valor, vencimento=p.vencimento,
                vencida=vencida, dias_atraso=atraso,
                op_numero=op.numero if op else None, op_id=op.id if op else None))
        grupos.append(FilaLiberacaoGrupo(**base.model_dump(), parcelas=itens))
    return sorted(grupos, key=lambda g: g.nome_conta)


async def fila_tesouraria(db: AsyncSession, *, tenant_id: int) -> FilaTesourariaOut:
    """Parcelas LIBERADAS (ordenadas por data prevista ?? vencimento) e as
    últimas 15 pagas (data_pagamento desc)."""
    liberadas = list((await db.execute(select(Parcela).where(
        Parcela.tenant_id == tenant_id, Parcela.excluido.is_(False),
        Parcela.status == "LIBERADA"))).scalars().all())
    pagas = list((await db.execute(select(Parcela).where(
        Parcela.tenant_id == tenant_id, Parcela.excluido.is_(False), Parcela.status == "PAGA")
        .order_by(Parcela.data_pagamento.desc(), Parcela.id.desc()).limit(15))).scalars().all())

    debito_ids = {p.id_debito for p in liberadas} | {p.id_debito for p in pagas}
    debitos_por_id: dict[int, Debito] = {}
    if debito_ids:
        rows = (await db.execute(select(Debito).where(
            Debito.tenant_id == tenant_id, Debito.id.in_(debito_ids),
            Debito.excluido.is_(False)))).scalars().all()
        debitos_por_id = {d.id: d for d in rows}
    # parcelas de débitos soft-deletados ficam fora da fila
    liberadas = [p for p in liberadas if p.id_debito in debitos_por_id]
    pagas = [p for p in pagas if p.id_debito in debitos_por_id]

    nomes_f = await nomes_fornecedores(
        db, tenant_id=tenant_id, ids={d.id_fornecedor for d in debitos_por_id.values()})
    ops = await _ops_recentes(db, tenant_id=tenant_id, debito_ids=debito_ids)
    qtds = await _qtd_parcelas_por_debito(db, tenant_id=tenant_id, debito_ids=debito_ids)
    liberadores = {p.id_usuario_liberacao for p in liberadas if p.id_usuario_liberacao}
    nomes_lib = await nomes_usuarios(db, tenant_id=tenant_id, ids=liberadores)
    hoje = datetime.utcnow().date()

    def _item(p: Parcela, *, para_pagas: bool) -> ParcelaTesourariaItem:
        d = debitos_por_id[p.id_debito]
        op = ops.get(d.id)
        if para_pagas:
            vencida, atraso = False, 0
        else:
            vencida, atraso = _dias_atraso(p.vencimento, hoje)
        return ParcelaTesourariaItem(
            id=p.id, id_debito=d.id, nome_fornecedor=nomes_f.get(d.id_fornecedor, "?"),
            descricao_debito=d.descricao, numero=p.numero, qtd_parcelas=qtds.get(d.id, 0),
            valor=p.valor, vencimento=p.vencimento, vencida=vencida, dias_atraso=atraso,
            op_numero=op.numero if op else None, op_id=op.id if op else None,
            data_liberacao=p.data_liberacao,
            liberado_por=nomes_lib.get(p.id_usuario_liberacao) if p.id_usuario_liberacao else None,
            data_prevista_pagamento=p.data_prevista_pagamento,
            data_pagamento=p.data_pagamento if para_pagas else None)

    liberadas_out = sorted(
        (_item(p, para_pagas=False) for p in liberadas),
        key=lambda it: it.data_prevista_pagamento or it.vencimento)
    pagas_out = [_item(p, para_pagas=True) for p in pagas]
    return FilaTesourariaOut(liberadas=liberadas_out, pagas_recentes=pagas_out)
