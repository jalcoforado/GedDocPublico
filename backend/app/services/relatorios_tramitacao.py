"""Relatório de tramitação: por processo + agregado por unidade.

Algoritmo de "etapas":
  - Etapa 0: processo entra na unidade proprietária em `data_hora_abertura`
  - Cada encaminhamento RECEBIDO encerra a etapa atual e inicia outra na unidade
    destino em `data_hora_recebimento`
  - Encaminhamentos não recebidos viram etapa "em trânsito" sem data de chegada
  - Última etapa fica em aberto (saiu_em=None) se o processo está parado numa unidade

Atraso (SI-34): o prazo do encaminhamento é o compromisso de quem RECEBE o
processo e vale até o FIM do dia marcado, em hora local — a mesma definição de
`prazos.prazo_da_caixa`. A etapa atrasou se o processo saiu da unidade (ou
continua nela) depois disso. Antes comparava a CHEGADA com a meia-noite do
dia do prazo: media a coisa errada e cortava o último dia inteiro.

Datas saem em hora local (`relatorios_comum.hora_local`); o cálculo de
minutos e de atraso roda em UTC, como está no banco.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from .relatorios_comum import (
    aplicar_filtros_processo,
    descrever_filtros,
    hora_local,
    intervalo_utc,
    no_intervalo,
    situacao,
)

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


def _filter_processos(
    stmt, f: RelatorioFiltro, tenant_id: int, niveis_permitidos: list[str] | None
):
    """Recorte comum (`relatorios_comum`) com o período pela abertura ou pela
    chegada. "Chegada" é a abertura na unidade dona ou um recebimento — na
    unidade filtrada, quando há uma; em qualquer unidade, quando não há."""
    if f.data_base != "chegada":
        return aplicar_filtros_processo(
            stmt, f, tenant_id=tenant_id, niveis_permitidos=niveis_permitidos,
            coluna_data=Processo.data_hora_abertura,
        )
    # Pela entrada, a unidade é "onde o processo deu entrada" — e não o sentido
    # do filtro (dona ou onde está): processo que entrou em B e já saiu é
    # entrada de B, e os Gargalos da página contam exatamente isso.
    sem_periodo = f.model_copy(update={"desde": None, "ate": None, "id_unidade": None})
    stmt = aplicar_filtros_processo(
        stmt, sem_periodo, tenant_id=tenant_id, niveis_permitidos=niveis_permitidos,
        coluna_data=Processo.data_hora_abertura,
    )
    if not (f.desde or f.ate or f.id_unidade):
        return stmt
    recebimento = [
        Encaminhamento.id_processo == Processo.id,
        Encaminhamento.tenant_id == tenant_id,
        Encaminhamento.recebido.is_(True),
        Encaminhamento.excluido.is_(False),
        *no_intervalo(Encaminhamento.data_hora_recebimento, f.desde, f.ate),
    ]
    abertura = no_intervalo(Processo.data_hora_abertura, f.desde, f.ate)
    if f.id_unidade:
        recebimento.append(Encaminhamento.id_unidade_destino == f.id_unidade)
        abertura.append(Processo.id_unidade_proprietaria == f.id_unidade)
    return stmt.where(
        or_(and_(*abertura), select(Encaminhamento.id).where(*recebimento).exists())
    )


@dataclass
class ResumoTramitacao:
    """As etapas de um processo e o que se conta delas. Datas em UTC, como no
    banco: quem mostra converte (`hora_local`)."""

    etapas: list[TramitacaoEtapa]
    teve_atraso: bool
    qtd_atrasos: int
    minutos_total: int
    minutos_em_andamento: int
    qtd_encaminhamentos: int
    qtd_unidades_visitadas: int
    ultimo_envio: datetime | None


async def resumir_tramitacao(
    db: AsyncSession,
    processos: list[tuple[int, datetime, int | None, str | None]],
    *,
    tenant_id: int,
    agora: datetime,
) -> dict[int, ResumoTramitacao]:
    """Etapas de cada processo — (id, abertura, id e nome da unidade dona).

    Uma regra só para a Tramitação e para o relatório montado (SI-35): o
    "tem etapa atrasada" de um tem de ser o do outro. Não aplica recorte
    nenhum; quem chama já filtrou os processos (sigilo inclusive).
    """
    processo_ids = [p[0] for p in processos]
    if not processo_ids:
        return {}

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

    now = agora
    resumos: dict[int, ResumoTramitacao] = {}
    for pid, abertura, ut_propr_id, ut_propr in processos:
        movs = movs_por_proc.get(pid, [])

        etapas: list[TramitacaoEtapa] = []
        # Etapa 0
        etapa_atual = TramitacaoEtapa(
            id_unidade=ut_propr_id,
            unidade=ut_propr,
            chegou_em=abertura,
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
                # nova etapa em unidade destino; o prazo (fim do dia local, em
                # UTC) é o dela — `atrasou` só se decide quando ela termina.
                etapa_atual = TramitacaoEtapa(
                    id_unidade=enc.id_unidade_destino,
                    unidade=ud_nome,
                    chegou_em=enc.data_hora_recebimento,
                    saiu_em=None,
                    minutos_no_local=None,
                    prazo_estipulado=(
                        intervalo_utc(None, enc.data_prazo)[1] if enc.data_prazo else None
                    ),
                    atrasou=False,
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

        # Atraso: saiu (ou segue lá) depois do fim do dia do prazo.
        for e in etapas:
            if e.prazo_estipulado is not None and e.chegou_em is not None:
                e.atrasou = (e.saiu_em or now) >= e.prazo_estipulado

        minutos_total = sum(e.minutos_no_local or 0 for e in etapas if e.saiu_em is not None)
        # tempo em aberto na última etapa
        ultima = etapas[-1] if etapas else None
        minutos_em_andamento = 0
        if ultima and ultima.saiu_em is None and ultima.chegou_em is not None:
            minutos_em_andamento = _delta_min(ultima.chegou_em, now) or 0

        envios = [m.data_hora_movimentacao for m, fl in movs if fl == "ENCAMINHAMENTO"]
        resumos[pid] = ResumoTramitacao(
            etapas=etapas,
            teve_atraso=any(e.atrasou for e in etapas),
            qtd_atrasos=sum(1 for e in etapas if e.atrasou),
            minutos_total=minutos_total,
            minutos_em_andamento=minutos_em_andamento,
            qtd_encaminhamentos=len(envios),
            qtd_unidades_visitadas=len({e.id_unidade for e in etapas if e.id_unidade is not None}),
            ultimo_envio=max(envios) if envios else None,
        )
    return resumos


TETO_FILTRO_ATRASO = 10000


class RecorteGrandeDemais(ValueError):
    """O filtro pedido exige analisar mais processos do que o teto."""


def _delta_min(a: datetime | None, b: datetime | None) -> int | None:
    if a is None or b is None:
        return None
    return int(round((b - a).total_seconds() / 60.0))


async def gerar_tramitacao(
    db: AsyncSession,
    f: RelatorioFiltro,
    *,
    tenant_id: int,
    # Sem default: ver `relatorios.gerar_relatorio`.
    niveis_permitidos: list[str] | None,
    max_processos: int = 200,
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
            situacao(tenant_id).label("situacao"),
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
    proc_stmt = _filter_processos(proc_stmt, f, tenant_id, niveis_permitidos)
    # Total do recorte, sem o teto da lista: o relatório diz quantos ficaram
    # de fora em vez de apresentar uma amostra como se fosse o todo.
    total = (
        await db.execute(select(func.count()).select_from(proc_stmt.order_by(None).subquery()))
    ).scalar_one()
    # "Só com atraso": o atraso sai das etapas, calculadas aqui em Python —
    # filtrar depois do teto contaria só os mais recentes. Então analisa o
    # recorte inteiro (até um teto) e corta a lista DEPOIS de filtrar.
    if f.com_atraso:
        if total > TETO_FILTRO_ATRASO:
            raise RecorteGrandeDemais(
                f"O recorte tem {total} processos; o filtro de atraso analisa até "
                f"{TETO_FILTRO_ATRASO}. Diminua o período ou filtre por unidade, tipo, "
                "assunto ou serviço."
            )
        limite = TETO_FILTRO_ATRASO
    else:
        limite = max_processos
    proc_stmt = proc_stmt.order_by(Processo.data_hora_abertura.desc(), Processo.id.desc()).limit(
        limite
    )
    proc_rows = (await db.execute(proc_stmt)).all()
    processo_ids = [row[0].id for row in proc_rows]
    descricao = await descrever_filtros(db, f, tenant_id=tenant_id)
    if not processo_ids:
        return RelatorioTramitacaoResposta(
            filtros_aplicados=f,
            descricao_filtros=descricao,
            nome_unidade=await _nome_unidade(db, f.id_unidade, tenant_id),
            qtd_processos=0,
            qtd_listados=0,
            cortado=False,
            qtd_processos_com_atraso=0,
            minutos_medio_por_processo=0.0,
            por_unidade=[],
            processos=[],
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    resumos = await resumir_tramitacao(
        db,
        [(row[0].id, row[0].data_hora_abertura, row.ut_propr_id, row.ut_propr) for row in proc_rows],
        tenant_id=tenant_id,
        agora=now,
    )

    processos_out: list[TramitacaoProcesso] = []

    for row in proc_rows:
        p: Processo = row[0]
        r = resumos[p.id]
        etapas = r.etapas
        teve_atraso = r.teve_atraso
        qtd_atrasos = r.qtd_atrasos
        minutos_total = r.minutos_total
        minutos_em_andamento = r.minutos_em_andamento
        qtd_encs = r.qtd_encaminhamentos
        qtd_unid = r.qtd_unidades_visitadas

        # Saída em hora local; os minutos já foram contados em UTC.
        for e in etapas:
            e.chegou_em = hora_local(e.chegou_em)
            e.saiu_em = hora_local(e.saiu_em)
            if e.prazo_estipulado is not None:
                # fim exclusivo → último segundo do dia do prazo, para exibir
                e.prazo_estipulado = hora_local(e.prazo_estipulado) - timedelta(seconds=1)

        processos_out.append(
            TramitacaoProcesso(
                id=p.id,
                numero_processo=p.numero_processo,
                data_hora_abertura=hora_local(p.data_hora_abertura),
                situacao=row.situacao,
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

    if f.com_atraso:
        processos_out = [p for p in processos_out if p.teve_atraso]
        total = len(processos_out)
        processos_out = processos_out[:max_processos]

    # Agregados sobre a lista que a tela mostra (os `qtd_listados`).
    por_unidade_acum: dict[
        tuple[int | None, str | None], dict[str, int]
    ] = defaultdict(lambda: {"passagens": 0, "atrasos": 0, "minutos": 0})
    qtd_com_atraso = 0
    soma_minutos = 0
    for p in processos_out:
        qtd_com_atraso += int(p.teve_atraso)
        soma_minutos += p.minutos_total + p.minutos_em_andamento
        for e in p.etapas:
            a = por_unidade_acum[(e.id_unidade, e.unidade)]
            a["passagens"] += 1
            a["atrasos"] += int(e.atrasou)
            if e.minutos_no_local is not None:
                a["minutos"] += e.minutos_no_local

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
        descricao_filtros=descricao,
        nome_unidade=await _nome_unidade(db, f.id_unidade, tenant_id),
        qtd_processos=total,
        qtd_listados=n,
        cortado=n < total,
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
