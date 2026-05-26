"""Relatório de tramitação: por processo + agregado por unidade.

Algoritmo de "etapas":
  - Etapa 0: processo entra na unidade proprietária em `data_hora_abertura`
  - Cada encaminhamento RECEBIDO encerra a etapa atual e inicia outra na unidade
    destino em `data_hora_recebimento`
  - Encaminhamentos não recebidos viram etapa "em trânsito" sem data de chegada
  - Última etapa fica em aberto (saiu_em=None) se o processo está parado numa unidade

Atrasos: comparação `data_hora_recebimento > data_prazo` do encaminhamento que
trouxe o processo para aquela unidade.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..models import (
    Acao,
    Assunto,
    Encaminhamento,
    Manifestante,
    Movimentacao,
    Processo,
    UnidadeTrabalho,
)
from ..schemas.relatorio import RelatorioFiltro
from ..schemas.relatorio_tramitacao import (
    RelatorioTramitacaoResposta,
    TramitacaoEtapa,
    TramitacaoPorUnidade,
    TramitacaoProcesso,
)


def _filter_processos(stmt, f: RelatorioFiltro, tenant_id: int):
    stmt = stmt.where(Processo.excluido.is_(False), Processo.tenant_id == tenant_id)
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


def _delta_min(a: datetime | None, b: datetime | None) -> int | None:
    if a is None or b is None:
        return None
    return int(round((b - a).total_seconds() / 60.0))


async def gerar_tramitacao(
    db: AsyncSession, f: RelatorioFiltro, *, tenant_id: int, max_processos: int = 200
) -> RelatorioTramitacaoResposta:
    LocalAtual = aliased(UnidadeTrabalho, name="la")

    proc_stmt = (
        select(
            Processo,
            Assunto.assunto.label("assunto_nome"),
            Manifestante.nome.label("manif_nome"),
            UnidadeTrabalho.unidade_trabalho.label("ut_propr"),
            UnidadeTrabalho.id.label("ut_propr_id"),
            LocalAtual.unidade_trabalho.label("ut_local"),
        )
        .join(Assunto, Assunto.id == Processo.id_assunto)
        .join(Manifestante, Manifestante.id == Processo.id_manifestante, isouter=True)
        .join(
            UnidadeTrabalho,
            UnidadeTrabalho.id == Processo.id_unidade_proprietaria,
            isouter=True,
        )
        .join(LocalAtual, LocalAtual.id == Processo.id_local_atual, isouter=True)
    )
    proc_stmt = _filter_processos(proc_stmt, f, tenant_id)
    proc_stmt = proc_stmt.order_by(Processo.data_hora_abertura.desc()).limit(max_processos)
    proc_rows = (await db.execute(proc_stmt)).all()
    processo_ids = [row[0].id for row in proc_rows]
    if not processo_ids:
        return RelatorioTramitacaoResposta(
            filtros_aplicados=f,
            nome_unidade=await _nome_unidade(db, f.id_unidade, tenant_id),
            qtd_processos=0,
            qtd_processos_com_atraso=0,
            minutos_medio_por_processo=0.0,
            por_unidade=[],
            processos=[],
        )

    # Carrega movimentações + acao em batch
    mov_stmt = (
        select(Movimentacao, Acao.flag)
        .join(Acao, Acao.id == Movimentacao.id_acao)
        .where(
            Movimentacao.id_processo.in_(processo_ids),
            Movimentacao.tenant_id == tenant_id,
            Movimentacao.excluido.is_(False),
        )
        .order_by(Movimentacao.data_hora_movimentacao.asc())
    )
    mov_rows = (await db.execute(mov_stmt)).all()
    movs_por_proc: dict[int, list[tuple[Movimentacao, str]]] = defaultdict(list)
    for mov, flag in mov_rows:
        movs_por_proc[mov.id_processo].append((mov, flag))

    # Carrega encaminhamentos por processo + nomes unidades
    UDest = aliased(UnidadeTrabalho, name="udest")
    enc_stmt = (
        select(Encaminhamento, UDest.unidade_trabalho)
        .join(UDest, UDest.id == Encaminhamento.id_unidade_destino)
        .where(
            Encaminhamento.id_processo.in_(processo_ids),
            Encaminhamento.tenant_id == tenant_id,
            Encaminhamento.excluido.is_(False),
            Encaminhamento.cancelado.is_(False),
        )
        .order_by(Encaminhamento.id_movimentacao.asc())
    )
    enc_rows = (await db.execute(enc_stmt)).all()
    enc_por_mov: dict[int, tuple[Encaminhamento, str]] = {}
    for enc, ud_nome in enc_rows:
        if enc.id_movimentacao is not None:
            enc_por_mov[enc.id_movimentacao] = (enc, ud_nome)

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Agregado por unidade
    por_unidade_acum: dict[
        tuple[int | None, str | None], dict[str, int]
    ] = defaultdict(lambda: {"passagens": 0, "atrasos": 0, "minutos": 0})

    processos_out: list[TramitacaoProcesso] = []
    qtd_com_atraso = 0
    soma_minutos = 0

    for row in proc_rows:
        p: Processo = row[0]
        movs = movs_por_proc.get(p.id, [])

        etapas: list[TramitacaoEtapa] = []
        # Etapa 0
        prazo_pendente: datetime | None = None
        etapa_atual = TramitacaoEtapa(
            id_unidade=row.ut_propr_id,
            unidade=row.ut_propr,
            chegou_em=p.data_hora_abertura,
            saiu_em=None,
            minutos_no_local=None,
            prazo_estipulado=None,
            atrasou=False,
        )

        for mov, flag in movs:
            if flag != "ENCAMINHAMENTO":
                continue
            enc_info = enc_por_mov.get(mov.id)
            if enc_info is None:
                continue
            enc, ud_nome = enc_info

            # encerra etapa atual
            etapa_atual.saiu_em = mov.data_hora_movimentacao
            etapa_atual.minutos_no_local = _delta_min(
                etapa_atual.chegou_em, etapa_atual.saiu_em
            )
            etapas.append(etapa_atual)

            if enc.recebido and enc.data_hora_recebimento is not None:
                # nova etapa em unidade destino
                prazo = (
                    datetime.combine(enc.data_prazo, datetime.min.time())
                    if enc.data_prazo
                    else None
                )
                atrasou = bool(prazo and enc.data_hora_recebimento > prazo)
                etapa_atual = TramitacaoEtapa(
                    id_unidade=enc.id_unidade_destino,
                    unidade=ud_nome,
                    chegou_em=enc.data_hora_recebimento,
                    saiu_em=None,
                    minutos_no_local=None,
                    prazo_estipulado=prazo,
                    atrasou=atrasou,
                )
            else:
                # em trânsito; cria etapa aberta sem chegada e sai
                etapas.append(
                    TramitacaoEtapa(
                        id_unidade=enc.id_unidade_destino,
                        unidade=f"(em trânsito → {ud_nome})",
                        chegou_em=None,
                        saiu_em=None,
                        minutos_no_local=None,
                        prazo_estipulado=None,
                        atrasou=False,
                    )
                )
                etapa_atual = None  # type: ignore
                break

        if etapa_atual is not None:
            etapas.append(etapa_atual)

        # Agregar
        teve_atraso = any(e.atrasou for e in etapas)
        qtd_atrasos = sum(1 for e in etapas if e.atrasou)
        if teve_atraso:
            qtd_com_atraso += 1

        minutos_total = sum(e.minutos_no_local or 0 for e in etapas if e.saiu_em is not None)
        # tempo em aberto na última etapa
        ultima = etapas[-1] if etapas else None
        minutos_em_andamento = 0
        if ultima and ultima.saiu_em is None and ultima.chegou_em is not None:
            minutos_em_andamento = _delta_min(ultima.chegou_em, now) or 0

        soma_minutos += minutos_total + minutos_em_andamento

        # Agregar por unidade
        for e in etapas:
            key = (e.id_unidade, e.unidade)
            por_unidade_acum[key]["passagens"] += 1
            if e.atrasou:
                por_unidade_acum[key]["atrasos"] += 1
            if e.minutos_no_local is not None:
                por_unidade_acum[key]["minutos"] += e.minutos_no_local

        qtd_encs = sum(1 for _, fl in movs if fl == "ENCAMINHAMENTO")
        qtd_unid = len({e.id_unidade for e in etapas if e.id_unidade is not None})

        processos_out.append(
            TramitacaoProcesso(
                id=p.id,
                numero_processo=p.numero_processo,
                data_hora_abertura=p.data_hora_abertura,
                ativo=p.ativo,
                manifestante=row.manif_nome,
                assunto=row.assunto_nome,
                qtd_encaminhamentos=qtd_encs,
                qtd_unidades_visitadas=qtd_unid,
                minutos_total=minutos_total,
                minutos_em_andamento=minutos_em_andamento,
                teve_atraso=teve_atraso,
                qtd_atrasos=qtd_atrasos,
                local_atual=row.ut_local,
                etapas=etapas,
            )
        )

    por_unidade_out = [
        TramitacaoPorUnidade(
            id_unidade=k[0],
            unidade=k[1],
            qtd_passagens=v["passagens"],
            qtd_atrasos=v["atrasos"],
            minutos_total=v["minutos"],
            minutos_medio=round(v["minutos"] / v["passagens"], 1)
            if v["passagens"] > 0
            else 0.0,
        )
        for k, v in sorted(
            por_unidade_acum.items(), key=lambda kv: kv[1]["passagens"], reverse=True
        )
    ]

    n = len(processos_out)
    media = round(soma_minutos / n, 1) if n > 0 else 0.0

    return RelatorioTramitacaoResposta(
        filtros_aplicados=f,
        nome_unidade=await _nome_unidade(db, f.id_unidade, tenant_id),
        qtd_processos=n,
        qtd_processos_com_atraso=qtd_com_atraso,
        minutos_medio_por_processo=media,
        por_unidade=por_unidade_out,
        processos=processos_out,
    )


async def _nome_unidade(
    db: AsyncSession, id_unidade: int | None, tenant_id: int
) -> str | None:
    if not id_unidade:
        return None
    return (
        await db.execute(
            select(UnidadeTrabalho.unidade_trabalho).where(
                UnidadeTrabalho.id == id_unidade,
                UnidadeTrabalho.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
