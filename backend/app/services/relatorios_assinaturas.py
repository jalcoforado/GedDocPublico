"""Relatório agregado de assinaturas.

Status por solicitação:
  - cancelada: `cancelada=true`
  - concluida: `realizada=true and dt_fim is not null`
  - pendente:  caso contrário

Tempo médio considera apenas concluídas: `dt_fim - dt_inicio`.
Pendentes em "minutos_decorridos" são `now - dt_inicio`.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..models import (
    AssinaturaAnexo,
    Processo,
    SolicitacaoAssinatura,
    Usuario,
    UsuarioAssinatura,
)
from ..schemas.relatorio_assinaturas import (
    AssinanteAgregado,
    AssinaturasFiltro,
    AssinaturasTotais,
    RelatorioAssinaturasResposta,
    SolicitacaoRow,
    SolicitanteAgregado,
    StatusSolicitacao,
)


def _status(s: SolicitacaoAssinatura) -> StatusSolicitacao:
    if s.cancelada:
        return "cancelada"
    if s.realizada and s.dt_fim is not None:
        return "concluida"
    return "pendente"


def _delta_min(a: datetime | None, b: datetime | None) -> int | None:
    if a is None or b is None:
        return None
    return int(round((b - a).total_seconds() / 60.0))


async def gerar_assinaturas(
    db: AsyncSession, f: AssinaturasFiltro, *, max_rows: int = 500
) -> RelatorioAssinaturasResposta:
    Solicitante = aliased(Usuario, name="solic")
    sol_stmt = (
        select(
            SolicitacaoAssinatura,
            Processo.numero_processo,
            Solicitante.nome.label("nome_solicitante"),
        )
        .join(Processo, Processo.id == SolicitacaoAssinatura.id_processo)
        .join(Solicitante, Solicitante.id == SolicitacaoAssinatura.id_solicitante, isouter=True)
        .where(SolicitacaoAssinatura.excluido.is_(False))
    )
    if f.desde:
        sol_stmt = sol_stmt.where(SolicitacaoAssinatura.dt_inicio >= f.desde)
    if f.ate:
        sol_stmt = sol_stmt.where(SolicitacaoAssinatura.dt_inicio <= f.ate)
    if f.id_solicitante:
        sol_stmt = sol_stmt.where(SolicitacaoAssinatura.id_solicitante == f.id_solicitante)

    # status precisa ser filtrado em Python (campo derivado), exceto quando podemos otimizar
    if f.status == "cancelada":
        sol_stmt = sol_stmt.where(SolicitacaoAssinatura.cancelada.is_(True))
    elif f.status == "concluida":
        sol_stmt = sol_stmt.where(
            SolicitacaoAssinatura.cancelada.is_(False),
            SolicitacaoAssinatura.realizada.is_(True),
        )
    elif f.status == "pendente":
        sol_stmt = sol_stmt.where(
            SolicitacaoAssinatura.cancelada.is_(False),
            SolicitacaoAssinatura.realizada.is_(False),
        )

    sol_stmt = sol_stmt.order_by(SolicitacaoAssinatura.dt_inicio.desc()).limit(max_rows)
    sol_rows = (await db.execute(sol_stmt)).all()
    solic_ids = [row[0].id for row in sol_rows]

    # Carrega assinantes em batch
    ua_por_sol: dict[int, list[tuple[UsuarioAssinatura, str | None]]] = defaultdict(list)
    if solic_ids:
        ua_stmt = (
            select(UsuarioAssinatura, Usuario.nome)
            .join(Usuario, Usuario.id == UsuarioAssinatura.id_assinante, isouter=True)
            .where(
                UsuarioAssinatura.id_solicitacao_assinatura.in_(solic_ids),
                UsuarioAssinatura.excluido.is_(False),
            )
            .order_by(UsuarioAssinatura.ordem)
        )
        for ua, nome in (await db.execute(ua_stmt)).all():
            ua_por_sol[ua.id_solicitacao_assinatura or 0].append((ua, nome))

    # Carrega anexos vinculados em batch — só para totalizar
    ua_ids = [ua.id for lst in ua_por_sol.values() for ua, _ in lst]
    anexo_por_ua: dict[int, list[AssinaturaAnexo]] = defaultdict(list)
    if ua_ids:
        an_stmt = select(AssinaturaAnexo).where(
            AssinaturaAnexo.id_usuario_assinatura.in_(ua_ids),
            AssinaturaAnexo.excluido.is_(False),
        )
        for aa in (await db.execute(an_stmt)).scalars().all():
            anexo_por_ua[aa.id_usuario_assinatura].append(aa)

    # filtro por id_assinante (precisa estar entre os assinantes da solicitação)
    if f.id_assinante:
        sol_rows = [
            row
            for row in sol_rows
            if any(
                ua.id_assinante == f.id_assinante for ua, _ in ua_por_sol.get(row[0].id, [])
            )
        ]

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Totais
    total = len(sol_rows)
    pendentes = concluidas = canceladas = 0
    soma_min_conclusao = 0
    qtd_concluidas_com_tempo = 0

    # Por assinante / solicitante (acumuladores)
    asg: dict[int, dict] = defaultdict(
        lambda: {"nome": None, "pendentes": 0, "concluidas": 0, "soma_min": 0, "qtd_com_tempo": 0}
    )
    slg: dict[int, dict] = defaultdict(
        lambda: {"nome": None, "total": 0, "pendentes": 0, "concluidas": 0, "canceladas": 0}
    )

    solic_out: list[SolicitacaoRow] = []
    for row in sol_rows:
        s: SolicitacaoAssinatura = row[0]
        status = _status(s)
        if status == "pendente":
            pendentes += 1
        elif status == "concluida":
            concluidas += 1
            d = _delta_min(s.dt_inicio, s.dt_fim)
            if d is not None:
                soma_min_conclusao += d
                qtd_concluidas_com_tempo += 1
        else:
            canceladas += 1

        slg[s.id_solicitante]["nome"] = row.nome_solicitante
        slg[s.id_solicitante]["total"] += 1
        if status == "pendente":
            slg[s.id_solicitante]["pendentes"] += 1
        elif status == "concluida":
            slg[s.id_solicitante]["concluidas"] += 1
        else:
            slg[s.id_solicitante]["canceladas"] += 1

        uas = ua_por_sol.get(s.id, [])
        qtd_assinantes = len(uas)
        qtd_conc = sum(1 for ua, _ in uas if ua.realizada)
        qtd_anexos = sum(len(anexo_por_ua.get(ua.id, [])) for ua, _ in uas)
        qtd_anexos_ok = sum(
            sum(1 for aa in anexo_por_ua.get(ua.id, []) if aa.assinado) for ua, _ in uas
        )
        nomes = [nome or f"#{ua.id_assinante}" for ua, nome in uas]

        minutos = (
            _delta_min(s.dt_inicio, s.dt_fim)
            if s.dt_fim is not None
            else _delta_min(s.dt_inicio, now)
        )

        for ua, nome in uas:
            asg[ua.id_assinante]["nome"] = nome
            if ua.realizada:
                asg[ua.id_assinante]["concluidas"] += 1
                # tempo = entre dt_inicio da solicitação e dt_assinatura mais recente do ua
                anexos = anexo_por_ua.get(ua.id, [])
                dts = [aa.dt_assinatura for aa in anexos if aa.assinado and aa.dt_assinatura]
                if dts:
                    d = _delta_min(s.dt_inicio, max(dts))
                    if d is not None:
                        asg[ua.id_assinante]["soma_min"] += d
                        asg[ua.id_assinante]["qtd_com_tempo"] += 1
            else:
                if not s.cancelada:
                    asg[ua.id_assinante]["pendentes"] += 1

        solic_out.append(
            SolicitacaoRow(
                id=s.id,
                id_processo=s.id_processo,
                numero_processo=row.numero_processo,
                id_solicitante=s.id_solicitante,
                nome_solicitante=row.nome_solicitante,
                status=status,
                dt_inicio=s.dt_inicio,
                dt_fim=s.dt_fim,
                minutos_decorridos=minutos,
                qtd_assinantes=qtd_assinantes,
                qtd_assinantes_concluidos=qtd_conc,
                qtd_anexos=qtd_anexos,
                qtd_anexos_assinados=qtd_anexos_ok,
                assinantes_resumo=nomes,
            )
        )

    media_concl = (
        round(soma_min_conclusao / qtd_concluidas_com_tempo, 1)
        if qtd_concluidas_com_tempo > 0
        else 0.0
    )

    por_assinante = [
        AssinanteAgregado(
            id_assinante=aid,
            nome=v["nome"],
            pendentes=v["pendentes"],
            concluidas=v["concluidas"],
            minutos_medio=round(v["soma_min"] / v["qtd_com_tempo"], 1)
            if v["qtd_com_tempo"] > 0
            else 0.0,
        )
        for aid, v in sorted(asg.items(), key=lambda kv: kv[1]["pendentes"], reverse=True)
    ]

    por_solicitante = [
        SolicitanteAgregado(
            id_solicitante=sid,
            nome=v["nome"],
            total=v["total"],
            pendentes=v["pendentes"],
            concluidas=v["concluidas"],
            canceladas=v["canceladas"],
        )
        for sid, v in sorted(slg.items(), key=lambda kv: kv[1]["total"], reverse=True)
    ]

    return RelatorioAssinaturasResposta(
        filtros_aplicados=f,
        totais=AssinaturasTotais(
            total=total,
            pendentes=pendentes,
            concluidas=concluidas,
            canceladas=canceladas,
            minutos_medio_conclusao=media_concl,
        ),
        por_assinante=por_assinante,
        por_solicitante=por_solicitante,
        solicitacoes=solic_out,
    )
