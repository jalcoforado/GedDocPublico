"""Orçamento — dotação, créditos e execução (O1, migration 0146).

As três contas que este módulo existe para fazer certo:

    dotação atualizada     = valor_inicial + Σ suplementações/especiais/
                             extraordinários − Σ anulações
    empenhado              = Σ valor_empenhado das despesas ligadas à dotação
    disponível orçamentário = dotação atualizada − empenhado

**A dotação atualizada é derivada, nunca coluna.** Manter um
`valor_atualizado` sincronizado por código é fonte de divergência garantida, e
este módulo já pagou essa lição ao remover o `status` legado do débito (F5).
O custo de somar os créditos na hora é desprezível perto do custo de um
orçamento que não bate com os próprios créditos.

**O empenhado vem do retorno do sistema financeiro** (`Debito.valor_empenhado`,
migration 0144), não do valor solicitado. O Aprimora não empenha: ele registra
o que foi empenhado e confere. Despesa cujo retorno ainda não chegou tem
`valor_empenhado` nulo e **não entra na execução** — e a contagem dessas
despesas sai junto com o número, porque uma execução baixa pode significar
"gastou pouco" ou "o retorno não chegou", e as duas leituras pedem ações
opostas.

**Disponibilidade orçamentária ≠ disponibilidade financeira.** Ter dotação não
é ter dinheiro em conta, e ter dinheiro não autoriza gasto sem dotação. O
catálogo de indicadores tem a ficha das duas, apontando uma para a outra.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CreditoAdicional, Debito, Dotacao, FonteRecursos, UnidadeTrabalho
from ..schemas.pagamentos import (
    DotacaoOut, ExecucaoOrcamentariaOut, PosicaoDotacaoItem,
)

# Tipos que SOMAM à dotação. Anulação subtrai — o sinal é do tipo, nunca do
# valor gravado (a coluna tem CHECK de não-negativo).
_SOMAM = ("SUPLEMENTAR", "ESPECIAL", "EXTRAORDINARIO")


def _utcnow() -> datetime:
    return datetime.utcnow()


def _expr_credito():
    """Σ dos créditos com o sinal do tipo."""
    return func.coalesce(func.sum(
        case((CreditoAdicional.tipo == "ANULACAO", -CreditoAdicional.valor),
             else_=CreditoAdicional.valor)), 0)


async def _creditos_por_dotacao(db, *, tenant_id: int, ids: set[int]) -> dict[int, Decimal]:
    if not ids:
        return {}
    rows = (await db.execute(
        select(CreditoAdicional.id_dotacao, _expr_credito())
        .where(CreditoAdicional.tenant_id == tenant_id,
               CreditoAdicional.excluido.is_(False),
               CreditoAdicional.id_dotacao.in_(ids))
        .group_by(CreditoAdicional.id_dotacao))).all()
    return {r[0]: Decimal(r[1]) for r in rows}


async def _empenhado_por_dotacao(db, *, tenant_id: int, ids: set[int]) -> dict[int, tuple]:
    """(Σ empenhado, nº de despesas com retorno, nº sem retorno) por dotação."""
    if not ids:
        return {}
    rows = (await db.execute(
        select(Debito.id_dotacao,
               func.coalesce(func.sum(Debito.valor_empenhado), 0),
               func.count(Debito.valor_empenhado),
               func.count(Debito.id))
        .where(Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
               Debito.id_dotacao.in_(ids))
        .group_by(Debito.id_dotacao))).all()
    # count(coluna) ignora NULL; count(id) conta todas. A diferença é quantas
    # despesas ainda não receberam o retorno do sistema financeiro.
    return {r[0]: (Decimal(r[1]), int(r[2]), int(r[3]) - int(r[2])) for r in rows}


async def listar_dotacoes(db: AsyncSession, *, tenant_id: int,
                          exercicio: int | None = None) -> list[DotacaoOut]:
    stmt = (select(Dotacao, UnidadeTrabalho.unidade_trabalho, FonteRecursos.codigo)
            .join(UnidadeTrabalho, UnidadeTrabalho.id == Dotacao.id_unidade)
            .join(FonteRecursos, FonteRecursos.id == Dotacao.id_fonte_recursos)
            .where(Dotacao.tenant_id == tenant_id, Dotacao.excluido.is_(False))
            .order_by(Dotacao.exercicio.desc(), Dotacao.funcao, Dotacao.programa))
    if exercicio is not None:
        stmt = stmt.where(Dotacao.exercicio == exercicio)
    rows = (await db.execute(stmt)).all()
    return [DotacaoOut(
        id=d.id, exercicio=d.exercicio, id_unidade=d.id_unidade, nome_unidade=unidade,
        funcao=d.funcao, subfuncao=d.subfuncao, programa=d.programa, acao=d.acao,
        natureza_codigo=d.natureza_codigo, grupo_despesa=d.grupo_despesa,
        id_fonte_recursos=d.id_fonte_recursos, codigo_fonte=fonte,
        descricao=d.descricao, valor_inicial=d.valor_inicial, ativa=d.ativa)
        for d, unidade, fonte in rows]


async def posicao_dotacao(db: AsyncSession, *, tenant_id: int,
                          exercicio: int | None = None) -> list[PosicaoDotacaoItem]:
    """Dotação atualizada, empenhado e disponível, uma linha por dotação."""
    dotacoes = await listar_dotacoes(db, tenant_id=tenant_id, exercicio=exercicio)
    ids = {d.id for d in dotacoes}
    creditos = await _creditos_por_dotacao(db, tenant_id=tenant_id, ids=ids)
    empenhos = await _empenhado_por_dotacao(db, tenant_id=tenant_id, ids=ids)

    itens: list[PosicaoDotacaoItem] = []
    for d in dotacoes:
        credito = creditos.get(d.id, Decimal("0"))
        empenhado, com_retorno, sem_retorno = empenhos.get(d.id, (Decimal("0"), 0, 0))
        atualizada = d.valor_inicial + credito
        itens.append(PosicaoDotacaoItem(
            id_dotacao=d.id, exercicio=d.exercicio, descricao=d.descricao,
            nome_unidade=d.nome_unidade, funcao=d.funcao, programa=d.programa,
            natureza_codigo=d.natureza_codigo, codigo_fonte=d.codigo_fonte,
            valor_inicial=d.valor_inicial, creditos=credito, dotacao_atualizada=atualizada,
            empenhado=empenhado, disponivel=atualizada - empenhado,
            execucao_pct=(float(empenhado / atualizada * 100) if atualizada > 0 else 0.0),
            despesas_com_retorno=com_retorno, despesas_sem_retorno=sem_retorno,
            estourada=empenhado > atualizada))
    itens.sort(key=lambda i: (not i.estourada, -i.execucao_pct))
    return itens


async def execucao_orcamentaria(db: AsyncSession, *, tenant_id: int,
                                exercicio: int | None = None) -> ExecucaoOrcamentariaOut:
    """Consolidado do exercício, com as ressalvas que o número exige."""
    if exercicio is None:
        exercicio = (await db.execute(
            select(func.max(Dotacao.exercicio)).where(
                Dotacao.tenant_id == tenant_id, Dotacao.excluido.is_(False)))).scalar_one_or_none()

    itens = await posicao_dotacao(db, tenant_id=tenant_id, exercicio=exercicio)
    inicial = sum((i.valor_inicial for i in itens), Decimal("0"))
    creditos = sum((i.creditos for i in itens), Decimal("0"))
    atualizada = inicial + creditos
    empenhado = sum((i.empenhado for i in itens), Decimal("0"))

    # Despesa fora do orçamento: paga, mas sem dotação vinculada. Não é rateada
    # nem escondida — é contada e mostrada, porque é o que explica a diferença
    # entre "o que o município gastou" e "o que o orçamento registra".
    sem_dotacao_qtd, sem_dotacao_valor = (await db.execute(
        select(func.count(Debito.id), func.coalesce(func.sum(Debito.valor_total), 0))
        .where(Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
               Debito.id_dotacao.is_(None)))).one()

    return ExecucaoOrcamentariaOut(
        exercicio=exercicio, qtd_dotacoes=len(itens),
        dotacao_inicial=inicial, creditos=creditos, dotacao_atualizada=atualizada,
        empenhado=empenhado, disponivel=atualizada - empenhado,
        execucao_pct=(float(empenhado / atualizada * 100) if atualizada > 0 else 0.0),
        dotacoes_estouradas=sum(1 for i in itens if i.estourada),
        despesas_sem_retorno=sum(i.despesas_sem_retorno for i in itens),
        despesas_sem_dotacao_qtd=int(sem_dotacao_qtd),
        despesas_sem_dotacao_valor=Decimal(sem_dotacao_valor),
        itens=itens, apurado_em=_utcnow())


async def criar_dotacao(db: AsyncSession, *, tenant_id: int, payload) -> Dotacao:
    d = Dotacao(
        tenant_id=tenant_id, exercicio=payload.exercicio, id_unidade=payload.id_unidade,
        funcao=payload.funcao, subfuncao=payload.subfuncao, programa=payload.programa,
        acao=payload.acao, natureza_codigo=payload.natureza_codigo,
        grupo_despesa=payload.grupo_despesa, id_fonte_recursos=payload.id_fonte_recursos,
        descricao=payload.descricao, valor_inicial=payload.valor_inicial,
        criado_em=_utcnow())
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


async def lancar_credito(db: AsyncSession, *, tenant_id: int, usuario_id: int | None,
                         payload) -> CreditoAdicional:
    """Crédito adicional ou anulação. Não altera a dotação: ela é derivada."""
    dot = (await db.execute(select(Dotacao).where(
        Dotacao.id == payload.id_dotacao, Dotacao.tenant_id == tenant_id,
        Dotacao.excluido.is_(False)))).scalar_one_or_none()
    if dot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dotação não encontrada")
    if payload.tipo not in (*_SOMAM, "ANULACAO"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Tipo de crédito inválido")
    if payload.valor < 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "O valor é sempre positivo; quem define o sinal é o tipo.")
    c = CreditoAdicional(
        tenant_id=tenant_id, id_dotacao=payload.id_dotacao, tipo=payload.tipo,
        valor=payload.valor, data=payload.data, ato=payload.ato,
        justificativa=payload.justificativa, id_usuario=usuario_id, criado_em=_utcnow())
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c
