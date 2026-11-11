"""Relatório "Processos no período" (SI-34).

Responde: quantos processos foram abertos (ou arquivados) no período, de que
tipo e assunto, em que unidade, e quais são eles.

Uma consulta-base com todo o recorte (`relatorios_comum.aplicar_filtros_processo`)
alimenta totais, quebras e lista — os quatro contam o MESMO conjunto, e o
total bate com a soma das quebras. A lista tem teto (`max_rows`); os totais,
não, e `cortado` diz quando a lista ficou menor que o total.
"""
from __future__ import annotations

from sqlalchemy import func, select
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
from .relatorios_comum import (
    aplicar_filtros_processo,
    data_arquivamento,
    descrever_filtros,
    hora_local,
    situacao,
)


def _pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100, 1)


def _base(f: RelatorioFiltro, *, tenant_id: int, niveis_permitidos: list[str] | None):
    """Ids, situação e data de arquivamento de cada processo do recorte."""
    arquivado_em = data_arquivamento(tenant_id).label("arquivado_em")
    coluna_data = (
        data_arquivamento(tenant_id)
        if f.data_base == "arquivamento"
        else Processo.data_hora_abertura
    )
    stmt = select(
        Processo.id.label("id"),
        situacao(tenant_id).label("situacao"),
        arquivado_em,
    ).join(Assunto, Assunto.id == Processo.id_assunto)
    return aplicar_filtros_processo(
        stmt, f, tenant_id=tenant_id, niveis_permitidos=niveis_permitidos, coluna_data=coluna_data
    ).subquery("recorte")


async def gerar_relatorio(
    db: AsyncSession,
    f: RelatorioFiltro,
    *,
    tenant_id: int,
    # Sem default de propósito: esquecer o sigilo tem de quebrar a chamada,
    # não liberar tudo em silêncio.
    niveis_permitidos: list[str] | None,
    max_rows: int = 1000,
) -> RelatorioResposta:
    rec = _base(f, tenant_id=tenant_id, niveis_permitidos=niveis_permitidos)

    # Totais — um SELECT sobre o recorte.
    t = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(rec.c.situacao == "em_andamento"),
                func.count().filter(rec.c.situacao == "em_transito"),
                func.count().filter(rec.c.situacao == "arquivado"),
                func.count().filter(Processo.publico.is_(False)),
                func.count().filter(Processo.externo.is_(True)),
            )
            .select_from(rec)
            .join(Processo, Processo.id == rec.c.id)
        )
    ).one()
    total = int(t[0])
    totais = RelatorioTotais(
        total=total,
        em_andamento=int(t[1]),
        em_transito=int(t[2]),
        arquivados=int(t[3]),
        sigilosos=int(t[4]),
        externos=int(t[5]),
    )

    async def _quebra(coluna, *joins) -> list[RelatorioBreakdownItem]:
        stmt = select(coluna.label("label"), func.count().label("count")).select_from(rec).join(
            Processo, Processo.id == rec.c.id
        )
        for alvo, cond in joins:
            stmt = stmt.join(alvo, cond, isouter=True)
        stmt = stmt.group_by(coluna).order_by(func.count().desc(), coluna)
        return [
            RelatorioBreakdownItem(label=r.label or "—", count=int(r.count), pct=_pct(int(r.count), total))
            for r in (await db.execute(stmt)).all()
        ]

    por_tipo = await _quebra(
        TipoProcesso.tipo_processo,
        (Assunto, Assunto.id == Processo.id_assunto),
        (TipoProcesso, TipoProcesso.id == Assunto.id_tipo_processo),
    )
    por_unidade = await _quebra(
        UnidadeTrabalho.unidade_trabalho,
        (UnidadeTrabalho, UnidadeTrabalho.id == Processo.id_unidade_proprietaria),
    )

    # Lista (com teto), mais recente primeiro pela data que define o período.
    LocalAtual = aliased(UnidadeTrabalho, name="la")
    ordem = (
        rec.c.arquivado_em.desc().nulls_last()
        if f.data_base == "arquivamento"
        else Processo.data_hora_abertura.desc()
    )
    list_stmt = (
        select(
            Processo,
            rec.c.situacao,
            rec.c.arquivado_em,
            Assunto.assunto.label("assunto_nome"),
            TipoProcesso.tipo_processo.label("tipo_nome"),
            Manifestante.nome.label("manif_nome"),
            UnidadeTrabalho.unidade_trabalho.label("ut_propr"),
            LocalAtual.unidade_trabalho.label("ut_local"),
        )
        .select_from(rec)
        .join(Processo, Processo.id == rec.c.id)
        .join(Assunto, Assunto.id == Processo.id_assunto)
        .join(TipoProcesso, TipoProcesso.id == Assunto.id_tipo_processo, isouter=True)
        .join(Manifestante, Manifestante.id == Processo.id_manifestante, isouter=True)
        .join(UnidadeTrabalho, UnidadeTrabalho.id == Processo.id_unidade_proprietaria, isouter=True)
        .join(LocalAtual, LocalAtual.id == Processo.id_local_atual, isouter=True)
        .order_by(ordem, Processo.id.desc())
        .limit(max_rows)
    )
    processos = [
        RelatorioProcessoRow(
            id=row[0].id,
            numero_processo=row[0].numero_processo,
            data_hora_abertura=hora_local(row[0].data_hora_abertura),
            data_hora_arquivamento=hora_local(row.arquivado_em),
            situacao=row.situacao,
            manifestante=row.manif_nome,
            tipo_processo=row.tipo_nome,
            assunto=row.assunto_nome,
            unidade_proprietaria=row.ut_propr,
            local_atual=row.ut_local,
            publico=row[0].publico,
            nivel_sigilo=row[0].nivel_sigilo,
            externo=row[0].externo,
        )
        for row in (await db.execute(list_stmt)).all()
    ]

    nome_unidade: str | None = None
    if f.id_unidade:
        nome_unidade = (
            await db.execute(
                select(UnidadeTrabalho.unidade_trabalho).where(
                    UnidadeTrabalho.id == f.id_unidade,
                    UnidadeTrabalho.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

    return RelatorioResposta(
        filtros_aplicados=f,
        descricao_filtros=await descrever_filtros(db, f, tenant_id=tenant_id),
        nome_unidade=nome_unidade,
        totais=totais,
        por_tipo_processo=por_tipo,
        por_unidade_proprietaria=por_unidade,
        processos=processos,
        cortado=len(processos) < total,
    )
