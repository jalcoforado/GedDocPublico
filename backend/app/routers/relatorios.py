"""Endpoints de relatórios.

Três formatos compartilham os mesmos filtros via query string:
- GET /relatorios/processos.json   → JSON (para a UI mostrar os cards + tabela)
- GET /relatorios/processos.csv    → CSV (download direto)
- GET /relatorios/processos.pdf    → PDF (download/inline)
"""
from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..database import get_db
from ..models import Usuario
from ..schemas.relatorio import RelatorioFiltro, RelatorioResposta
from ..schemas.relatorio_assinaturas import (
    AssinaturasFiltro,
    RelatorioAssinaturasResposta,
    StatusSolicitacao,
)
from ..schemas.relatorio_tramitacao import RelatorioTramitacaoResposta
from ..services.pdf_relatorio import gerar_relatorio_pdf
from ..services.pdf_relatorio_assinaturas import gerar_assinaturas_pdf
from ..services.pdf_relatorio_tramitacao import gerar_tramitacao_pdf
from ..services.relatorios import gerar_relatorio
from ..services.relatorios_assinaturas import gerar_assinaturas
from ..services.relatorios_tramitacao import gerar_tramitacao

router = APIRouter(prefix="/relatorios", tags=["relatorios"])


def _filtro(
    id_unidade: int | None,
    id_assunto: int | None,
    id_tipo_processo: int | None,
    desde: datetime | None,
    ate: datetime | None,
    apenas_ativos: bool,
) -> RelatorioFiltro:
    return RelatorioFiltro(
        id_unidade=id_unidade,
        id_assunto=id_assunto,
        id_tipo_processo=id_tipo_processo,
        desde=desde,
        ate=ate,
        apenas_ativos=apenas_ativos,
    )


@router.get("/processos.json", response_model=RelatorioResposta)
async def relatorio_json(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: datetime | None = None,
    ate: datetime | None = None,
    apenas_ativos: bool = False,
    max_rows: int = Query(1000, ge=1, le=10000),
) -> RelatorioResposta:
    f = _filtro(id_unidade, id_assunto, id_tipo_processo, desde, ate, apenas_ativos)
    return await gerar_relatorio(db, f, max_rows=max_rows)


@router.get("/processos.csv")
async def relatorio_csv(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: datetime | None = None,
    ate: datetime | None = None,
    apenas_ativos: bool = False,
    max_rows: int = Query(10000, ge=1, le=50000),
):
    f = _filtro(id_unidade, id_assunto, id_tipo_processo, desde, ate, apenas_ativos)
    r = await gerar_relatorio(db, f, max_rows=max_rows)

    buf = StringIO()
    buf.write("﻿")  # BOM para Excel reconhecer UTF-8
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    w.writerow(
        [
            "id",
            "numero_processo",
            "data_hora_abertura",
            "manifestante",
            "tipo_processo",
            "assunto",
            "unidade_proprietaria",
            "local_atual",
            "ativo",
            "publico",
            "externo",
        ]
    )
    for p in r.processos:
        w.writerow(
            [
                p.id,
                p.numero_processo,
                p.data_hora_abertura.strftime("%Y-%m-%d %H:%M:%S"),
                p.manifestante or "",
                p.tipo_processo or "",
                p.assunto or "",
                p.unidade_proprietaria or "",
                p.local_atual or "",
                "1" if p.ativo else "0",
                "1" if p.publico else "0",
                "1" if p.externo else "0",
            ]
        )
    fname = f"relatorio-processos-{datetime.now().strftime('%Y%m%d-%H%M')}.csv"
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/processos.pdf")
async def relatorio_pdf(
    inline: bool = Query(True),
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: datetime | None = None,
    ate: datetime | None = None,
    apenas_ativos: bool = False,
    max_rows: int = Query(1000, ge=1, le=5000),
):
    f = _filtro(id_unidade, id_assunto, id_tipo_processo, desde, ate, apenas_ativos)
    r = await gerar_relatorio(db, f, max_rows=max_rows)
    pdf_bytes = gerar_relatorio_pdf(r)
    fname = f"relatorio-processos-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
    )


# ---------- Tramitação (Fatia 6.2) ----------


@router.get("/tramitacao.json", response_model=RelatorioTramitacaoResposta)
async def tramitacao_json(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: datetime | None = None,
    ate: datetime | None = None,
    apenas_ativos: bool = False,
    max_processos: int = Query(200, ge=1, le=2000),
) -> RelatorioTramitacaoResposta:
    f = _filtro(id_unidade, id_assunto, id_tipo_processo, desde, ate, apenas_ativos)
    return await gerar_tramitacao(db, f, max_processos=max_processos)


@router.get("/tramitacao.csv")
async def tramitacao_csv(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: datetime | None = None,
    ate: datetime | None = None,
    apenas_ativos: bool = False,
    max_processos: int = Query(2000, ge=1, le=10000),
):
    f = _filtro(id_unidade, id_assunto, id_tipo_processo, desde, ate, apenas_ativos)
    r = await gerar_tramitacao(db, f, max_processos=max_processos)

    buf = StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    w.writerow(
        [
            "id_processo",
            "numero_processo",
            "data_hora_abertura",
            "manifestante",
            "assunto",
            "local_atual",
            "qtd_encaminhamentos",
            "qtd_unidades_visitadas",
            "minutos_total",
            "minutos_em_andamento",
            "teve_atraso",
            "qtd_atrasos",
            "etapa_unidade",
            "etapa_chegou_em",
            "etapa_saiu_em",
            "etapa_minutos_no_local",
            "etapa_prazo",
            "etapa_atrasou",
        ]
    )
    for p in r.processos:
        if not p.etapas:
            w.writerow(
                [
                    p.id,
                    p.numero_processo,
                    p.data_hora_abertura.strftime("%Y-%m-%d %H:%M"),
                    p.manifestante or "",
                    p.assunto or "",
                    p.local_atual or "",
                    p.qtd_encaminhamentos,
                    p.qtd_unidades_visitadas,
                    p.minutos_total,
                    p.minutos_em_andamento,
                    "1" if p.teve_atraso else "0",
                    p.qtd_atrasos,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
        for e in p.etapas:
            w.writerow(
                [
                    p.id,
                    p.numero_processo,
                    p.data_hora_abertura.strftime("%Y-%m-%d %H:%M"),
                    p.manifestante or "",
                    p.assunto or "",
                    p.local_atual or "",
                    p.qtd_encaminhamentos,
                    p.qtd_unidades_visitadas,
                    p.minutos_total,
                    p.minutos_em_andamento,
                    "1" if p.teve_atraso else "0",
                    p.qtd_atrasos,
                    e.unidade or "",
                    e.chegou_em.strftime("%Y-%m-%d %H:%M") if e.chegou_em else "",
                    e.saiu_em.strftime("%Y-%m-%d %H:%M") if e.saiu_em else "",
                    e.minutos_no_local if e.minutos_no_local is not None else "",
                    e.prazo_estipulado.strftime("%Y-%m-%d") if e.prazo_estipulado else "",
                    "1" if e.atrasou else "0",
                ]
            )
    fname = f"tramitacao-{datetime.now().strftime('%Y%m%d-%H%M')}.csv"
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/tramitacao.pdf")
async def tramitacao_pdf(
    inline: bool = Query(True),
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: datetime | None = None,
    ate: datetime | None = None,
    apenas_ativos: bool = False,
    max_processos: int = Query(200, ge=1, le=1000),
):
    f = _filtro(id_unidade, id_assunto, id_tipo_processo, desde, ate, apenas_ativos)
    r = await gerar_tramitacao(db, f, max_processos=max_processos)
    pdf_bytes = gerar_tramitacao_pdf(r)
    fname = f"tramitacao-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
    )


# ---------- Assinaturas (Fatia 6.3) ----------


def _filtro_assinaturas(
    desde: datetime | None,
    ate: datetime | None,
    id_solicitante: int | None,
    id_assinante: int | None,
    status: StatusSolicitacao | None,
) -> AssinaturasFiltro:
    return AssinaturasFiltro(
        desde=desde,
        ate=ate,
        id_solicitante=id_solicitante,
        id_assinante=id_assinante,
        status=status,
    )


@router.get("/assinaturas.json", response_model=RelatorioAssinaturasResposta)
async def assinaturas_json(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    desde: datetime | None = None,
    ate: datetime | None = None,
    id_solicitante: int | None = None,
    id_assinante: int | None = None,
    status: StatusSolicitacao | None = None,
    max_rows: int = Query(500, ge=1, le=5000),
) -> RelatorioAssinaturasResposta:
    f = _filtro_assinaturas(desde, ate, id_solicitante, id_assinante, status)
    return await gerar_assinaturas(db, f, max_rows=max_rows)


@router.get("/assinaturas.csv")
async def assinaturas_csv(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    desde: datetime | None = None,
    ate: datetime | None = None,
    id_solicitante: int | None = None,
    id_assinante: int | None = None,
    status: StatusSolicitacao | None = None,
    max_rows: int = Query(5000, ge=1, le=50000),
):
    f = _filtro_assinaturas(desde, ate, id_solicitante, id_assinante, status)
    r = await gerar_assinaturas(db, f, max_rows=max_rows)

    buf = StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    w.writerow(
        [
            "id_solicitacao",
            "id_processo",
            "numero_processo",
            "solicitante",
            "status",
            "iniciada_em",
            "concluida_em",
            "minutos_decorridos",
            "qtd_assinantes",
            "qtd_assinantes_concluidos",
            "qtd_anexos",
            "qtd_anexos_assinados",
            "assinantes",
        ]
    )
    for s in r.solicitacoes:
        w.writerow(
            [
                s.id,
                s.id_processo,
                s.numero_processo or "",
                s.nome_solicitante or "",
                s.status,
                s.dt_inicio.strftime("%Y-%m-%d %H:%M"),
                s.dt_fim.strftime("%Y-%m-%d %H:%M") if s.dt_fim else "",
                s.minutos_decorridos if s.minutos_decorridos is not None else "",
                s.qtd_assinantes,
                s.qtd_assinantes_concluidos,
                s.qtd_anexos,
                s.qtd_anexos_assinados,
                " · ".join(s.assinantes_resumo),
            ]
        )
    fname = f"assinaturas-{datetime.now().strftime('%Y%m%d-%H%M')}.csv"
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/assinaturas.pdf")
async def assinaturas_pdf(
    inline: bool = Query(True),
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    desde: datetime | None = None,
    ate: datetime | None = None,
    id_solicitante: int | None = None,
    id_assinante: int | None = None,
    status: StatusSolicitacao | None = None,
    max_rows: int = Query(500, ge=1, le=5000),
):
    f = _filtro_assinaturas(desde, ate, id_solicitante, id_assinante, status)
    r = await gerar_assinaturas(db, f, max_rows=max_rows)
    pdf_bytes = gerar_assinaturas_pdf(r)
    fname = f"assinaturas-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
    )
