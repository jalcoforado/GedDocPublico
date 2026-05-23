"""Relatórios agregados de processos.

A query agregadora roda 3 SELECTs: totais, breakdown por tipo_processo,
breakdown por unidade_proprietaria. A lista de processos é a 4ª query e
respeita o limite de `max_rows` para não estourar PDF/CSV.
"""
from __future__ import annotations

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..models import (
    Assunto,
    Manifestante,
    Processo,
    TipoProcesso,
    UnidadeTrabalho,
)
from ..schemas.relatorio import (
    RelatorioBreakdownItem,
    RelatorioFiltro,
    RelatorioProcessoRow,
    RelatorioResposta,
    RelatorioTotais,
)


def _apply_filters(stmt, f: RelatorioFiltro):
    stmt = stmt.where(Processo.excluido.is_(False))
    if f.id_unidade:
        stmt = stmt.where(
            (Processo.id_unidade_proprietaria == f.id_unidade)
            | (Processo.id_local_atual == f.id_unidade)
        )
    if f.id_assunto:
        stmt = stmt.where(Processo.id_assunto == f.id_assunto)
    if f.id_tipo_processo:
        stmt = stmt.where(Assunto.id_tipo_processo == f.id_tipo_processo)
    if f.desde:
        stmt = stmt.where(Processo.data_hora_abertura >= f.desde)
    if f.ate:
        stmt = stmt.where(Processo.data_hora_abertura <= f.ate)
    if f.apenas_ativos:
        stmt = stmt.where(Processo.ativo.is_(True))
    return stmt


def _pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100, 1)


async def gerar_relatorio(
    db: AsyncSession, f: RelatorioFiltro, *, max_rows: int = 1000
) -> RelatorioResposta:
    # Base join (Assunto sempre, pois usado por filtro tipo_processo)
    base = select(Processo).join(Assunto, Assunto.id == Processo.id_assunto)
    base = _apply_filters(base, f)

    # Totais — usar colunas da subquery senão SQLAlchemy cross-joina com a tabela original
    sq = base.subquery()
    totais_stmt = select(
        func.count(sq.c.id),
        func.sum(func.cast(sq.c.ativo, Integer)),
        func.sum(func.cast(~sq.c.publico, Integer)),
        func.sum(func.cast(sq.c.externo, Integer)),
    )
    total_row = (await db.execute(totais_stmt)).one()
    total = int(total_row[0] or 0)
    ativos = int(total_row[1] or 0)
    sigilosos = int(total_row[2] or 0)
    externos = int(total_row[3] or 0)
    totais = RelatorioTotais(
        total=total,
        ativos=ativos,
        inativos=total - ativos,
        sigilosos=sigilosos,
        externos=externos,
    )

    # Breakdown por tipo_processo
    tp_stmt = (
        select(
            TipoProcesso.tipo_processo.label("label"),
            func.count(Processo.id).label("count"),
        )
        .select_from(Processo)
        .join(Assunto, Assunto.id == Processo.id_assunto)
        .join(TipoProcesso, TipoProcesso.id == Assunto.id_tipo_processo, isouter=True)
    )
    tp_stmt = _apply_filters(tp_stmt, f)
    tp_stmt = tp_stmt.group_by(TipoProcesso.tipo_processo).order_by(func.count(Processo.id).desc())
    tp_rows = (await db.execute(tp_stmt)).all()
    por_tipo = [
        RelatorioBreakdownItem(label=r.label or "—", count=int(r.count), pct=_pct(int(r.count), total))
        for r in tp_rows
    ]

    # Breakdown por unidade proprietária
    un_stmt = (
        select(
            UnidadeTrabalho.unidade_trabalho.label("label"),
            func.count(Processo.id).label("count"),
        )
        .select_from(Processo)
        .join(Assunto, Assunto.id == Processo.id_assunto)
        .join(UnidadeTrabalho, UnidadeTrabalho.id == Processo.id_unidade_proprietaria, isouter=True)
    )
    un_stmt = _apply_filters(un_stmt, f)
    un_stmt = un_stmt.group_by(UnidadeTrabalho.unidade_trabalho).order_by(func.count(Processo.id).desc())
    un_rows = (await db.execute(un_stmt)).all()
    por_unidade = [
        RelatorioBreakdownItem(label=r.label or "—", count=int(r.count), pct=_pct(int(r.count), total))
        for r in un_rows
    ]

    # Lista de processos (limitada)
    LocalAtual = aliased(UnidadeTrabalho, name="la")
    list_stmt = (
        select(
            Processo,
            Assunto.assunto.label("assunto_nome"),
            TipoProcesso.tipo_processo.label("tipo_nome"),
            Manifestante.nome.label("manif_nome"),
            UnidadeTrabalho.unidade_trabalho.label("ut_propr"),
            LocalAtual.unidade_trabalho.label("ut_local"),
        )
        .join(Assunto, Assunto.id == Processo.id_assunto)
        .join(TipoProcesso, TipoProcesso.id == Assunto.id_tipo_processo, isouter=True)
        .join(Manifestante, Manifestante.id == Processo.id_manifestante, isouter=True)
        .join(
            UnidadeTrabalho,
            UnidadeTrabalho.id == Processo.id_unidade_proprietaria,
            isouter=True,
        )
        .join(LocalAtual, LocalAtual.id == Processo.id_local_atual, isouter=True)
    )
    list_stmt = _apply_filters(list_stmt, f)
    list_stmt = list_stmt.order_by(Processo.data_hora_abertura.desc()).limit(max_rows)
    list_rows = (await db.execute(list_stmt)).all()
    processos = [
        RelatorioProcessoRow(
            id=row[0].id,
            numero_processo=row[0].numero_processo,
            data_hora_abertura=row[0].data_hora_abertura,
            manifestante=row.manif_nome,
            tipo_processo=row.tipo_nome,
            assunto=row.assunto_nome,
            unidade_proprietaria=row.ut_propr,
            local_atual=row.ut_local,
            ativo=row[0].ativo,
            publico=row[0].publico,
            externo=row[0].externo,
        )
        for row in list_rows
    ]

    nome_unidade: str | None = None
    if f.id_unidade:
        nome_unidade = (
            await db.execute(
                select(UnidadeTrabalho.unidade_trabalho).where(
                    UnidadeTrabalho.id == f.id_unidade
                )
            )
        ).scalar_one_or_none()

    return RelatorioResposta(
        filtros_aplicados=f,
        nome_unidade=nome_unidade,
        totais=totais,
        por_tipo_processo=por_tipo,
        por_unidade_proprietaria=por_unidade,
        processos=processos,
    )
