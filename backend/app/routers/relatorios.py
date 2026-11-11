"""Endpoints de relatórios.

Três formatos compartilham os mesmos filtros via query string:
- GET /relatorios/processos.json   → JSON (para a UI mostrar os cards + tabela)
- GET /relatorios/processos.csv    → CSV (download direto)
- GET /relatorios/processos.pdf    → PDF (download/inline)
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from io import StringIO
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.modulos import require_modulo
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.relatorio import ModoUnidade, RelatorioFiltro, RelatorioResposta, Situacao
from ..schemas.relatorio_assinaturas import (
    AssinaturasFiltro,
    RelatorioAssinaturasResposta,
    StatusSolicitacao,
)
from ..schemas.relatorio_gerencial import GerencialResposta
from ..schemas.relatorio_tramitacao import RelatorioTramitacaoResposta
from ..services.pdf_relatorio import gerar_relatorio_pdf
from ..services.pdf_relatorio_assinaturas import gerar_assinaturas_pdf
from ..services.pdf_relatorio_gerencial import gerar_gerencial_pdf
from ..services.pdf_relatorio_tramitacao import gerar_tramitacao_pdf
from ..services.relatorios import gerar_relatorio
from ..services.relatorios_assinaturas import gerar_assinaturas
from ..services.relatorios_comum import ROTULO_SITUACAO
from ..services.relatorios_gerencial import gerar_gerencial
from ..services.relatorios_tramitacao import gerar_tramitacao
from ..services.sigilo import niveis_acesso_usuario

router = APIRouter(prefix="/relatorios", tags=["relatorios"])


# Por qual data o período conta, por relatório (SI-34). O schema aceita as
# três; cada rota estreita para as que fazem sentido nela.
DataBaseProcessos = Literal["abertura", "arquivamento"]
DataBaseTramitacao = Literal["abertura", "chegada"]


def _filtro(
    id_unidade: int | None,
    modo_unidade: ModoUnidade,
    id_assunto: int | None,
    id_tipo_processo: int | None,
    desde: date | None,
    ate: date | None,
    data_base: str,
) -> RelatorioFiltro:
    if desde and ate and desde > ate:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A data inicial do período é posterior à final.",
        )
    return RelatorioFiltro(
        id_unidade=id_unidade,
        modo_unidade=modo_unidade,
        id_assunto=id_assunto,
        id_tipo_processo=id_tipo_processo,
        desde=desde,
        ate=ate,
        data_base=data_base,
    )


def _exige_completo(cortado: bool, total: int, teto: int, formato: str) -> None:
    """Exportação não corta em silêncio: acima do teto, recusa e diz por quê.

    Um CSV com 10 mil linhas de um recorte de 12 mil parece o recorte inteiro
    — quem soma a planilha erra sem saber.
    """
    if cortado:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"O recorte tem {total} processos e o {formato} vai até {teto}. "
                "Diminua o período ou filtre por unidade, tipo ou assunto."
            ),
        )


def _cabecalho_csv(w, descricao: list[str]) -> None:
    """O recorte no topo do CSV, como na tela e no PDF, e uma linha em branco."""
    for linha in descricao:
        w.writerow([linha])
    w.writerow([])


@router.get(
    "/processos.json",
    response_model=RelatorioResposta,
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("processo"))],
)
async def relatorio_json(
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    modo_unidade: ModoUnidade = "envolvida",
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: date | None = None,
    ate: date | None = None,
    data_base: DataBaseProcessos = "abertura",
    situacao: Situacao | None = None,
    parado_ha_dias: int | None = Query(None, ge=1, le=3650),
    max_rows: int = Query(1000, ge=1, le=10000),
) -> RelatorioResposta:
    f = _filtro(id_unidade, modo_unidade, id_assunto, id_tipo_processo, desde, ate, data_base)
    f = f.model_copy(update={"situacao": situacao, "parado_ha_dias": parado_ha_dias})
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    return await gerar_relatorio(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )


@router.get(
    "/processos.csv",
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("processo"))],
)
async def relatorio_csv(
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    modo_unidade: ModoUnidade = "envolvida",
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: date | None = None,
    ate: date | None = None,
    data_base: DataBaseProcessos = "abertura",
    situacao: Situacao | None = None,
    parado_ha_dias: int | None = Query(None, ge=1, le=3650),
    max_rows: int = Query(50000, ge=1, le=50000),
):
    f = _filtro(id_unidade, modo_unidade, id_assunto, id_tipo_processo, desde, ate, data_base)
    f = f.model_copy(update={"situacao": situacao, "parado_ha_dias": parado_ha_dias})
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    r = await gerar_relatorio(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )

    _exige_completo(r.cortado, r.totais.total, max_rows, "CSV")

    buf = StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    _cabecalho_csv(w, r.descricao_filtros)
    w.writerow(
        [
            "id",
            "numero_processo",
            "data_hora_abertura",
            "data_hora_arquivamento",
            "situacao",
            "manifestante",
            "tipo_processo",
            "assunto",
            "unidade_proprietaria",
            "local_atual",
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
                p.data_hora_arquivamento.strftime("%Y-%m-%d %H:%M:%S")
                if p.data_hora_arquivamento
                else "",
                ROTULO_SITUACAO[p.situacao],
                p.manifestante or "",
                p.tipo_processo or "",
                p.assunto or "",
                p.unidade_proprietaria or "",
                p.local_atual or "",
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


@router.get(
    "/processos.pdf",
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("processo"))],
)
async def relatorio_pdf(
    inline: bool = Query(True),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    modo_unidade: ModoUnidade = "envolvida",
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: date | None = None,
    ate: date | None = None,
    data_base: DataBaseProcessos = "abertura",
    situacao: Situacao | None = None,
    parado_ha_dias: int | None = Query(None, ge=1, le=3650),
    max_rows: int = Query(1000, ge=1, le=5000),
):
    f = _filtro(id_unidade, modo_unidade, id_assunto, id_tipo_processo, desde, ate, data_base)
    f = f.model_copy(update={"situacao": situacao, "parado_ha_dias": parado_ha_dias})
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    r = await gerar_relatorio(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )
    pdf_bytes = gerar_relatorio_pdf(r)
    fname = f"relatorio-processos-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
    )


# ---------- Página gerencial (SI-34) ----------


async def _gerencial(db, user, tenant_id, id_unidade, modo_unidade, id_assunto,
                     id_tipo_processo, desde, ate, dias_parado) -> GerencialResposta:
    f = _filtro(id_unidade, modo_unidade, id_assunto, id_tipo_processo, desde, ate, "abertura")
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    return await gerar_gerencial(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, dias_parado=dias_parado
    )


@router.get(
    "/gerencial.json",
    response_model=GerencialResposta,
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("processo"))],
)
async def gerencial_json(
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    modo_unidade: ModoUnidade = "envolvida",
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: date | None = None,
    ate: date | None = None,
    dias_parado: int = Query(15, ge=1, le=3650),
) -> GerencialResposta:
    return await _gerencial(db, user, tenant_id, id_unidade, modo_unidade, id_assunto,
                            id_tipo_processo, desde, ate, dias_parado)


@router.get(
    "/gerencial.pdf",
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("processo"))],
)
async def gerencial_pdf(
    inline: bool = Query(True),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    modo_unidade: ModoUnidade = "envolvida",
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: date | None = None,
    ate: date | None = None,
    dias_parado: int = Query(15, ge=1, le=3650),
):
    r = await _gerencial(db, user, tenant_id, id_unidade, modo_unidade, id_assunto,
                         id_tipo_processo, desde, ate, dias_parado)
    fname = f"relatorio-gerencial-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=gerar_gerencial_pdf(r),
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
    )


# ---------- Tramitação ----------


@router.get(
    "/tramitacao.json",
    response_model=RelatorioTramitacaoResposta,
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("processo"))],
)
async def tramitacao_json(
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    modo_unidade: ModoUnidade = "envolvida",
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: date | None = None,
    ate: date | None = None,
    data_base: DataBaseTramitacao = "abertura",
    max_processos: int = Query(200, ge=1, le=2000),
) -> RelatorioTramitacaoResposta:
    f = _filtro(id_unidade, modo_unidade, id_assunto, id_tipo_processo, desde, ate, data_base)
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    return await gerar_tramitacao(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_processos=max_processos
    )


@router.get(
    "/tramitacao.csv",
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("processo"))],
)
async def tramitacao_csv(
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    modo_unidade: ModoUnidade = "envolvida",
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: date | None = None,
    ate: date | None = None,
    data_base: DataBaseTramitacao = "abertura",
    max_processos: int = Query(10000, ge=1, le=10000),
):
    f = _filtro(id_unidade, modo_unidade, id_assunto, id_tipo_processo, desde, ate, data_base)
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    r = await gerar_tramitacao(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_processos=max_processos
    )

    _exige_completo(r.cortado, r.qtd_processos, max_processos, "CSV")

    buf = StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    _cabecalho_csv(w, r.descricao_filtros)
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


@router.get(
    "/tramitacao.pdf",
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("processo"))],
)
async def tramitacao_pdf(
    inline: bool = Query(True),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    modo_unidade: ModoUnidade = "envolvida",
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: date | None = None,
    ate: date | None = None,
    data_base: DataBaseTramitacao = "abertura",
    max_processos: int = Query(200, ge=1, le=1000),
):
    f = _filtro(id_unidade, modo_unidade, id_assunto, id_tipo_processo, desde, ate, data_base)
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    r = await gerar_tramitacao(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_processos=max_processos
    )
    pdf_bytes = gerar_tramitacao_pdf(r)
    fname = f"tramitacao-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
    )


# ---------- Assinaturas ----------


def _filtro_assinaturas(
    id_unidade: int | None,
    modo_unidade: ModoUnidade,
    id_assunto: int | None,
    id_tipo_processo: int | None,
    desde: date | None,
    ate: date | None,
    data_base: str,
    id_solicitante: int | None,
    id_assinante: int | None,
    status: StatusSolicitacao | None,
) -> AssinaturasFiltro:
    # Mesma validação de período e mesmos campos do recorte comum.
    comum = _filtro(id_unidade, modo_unidade, id_assunto, id_tipo_processo, desde, ate, "abertura")
    return AssinaturasFiltro(
        **comum.model_dump(exclude={"data_base"}),
        data_base=data_base,
        id_solicitante=id_solicitante,
        id_assinante=id_assinante,
        status=status,
    )


@router.get(
    "/assinaturas.json",
    response_model=RelatorioAssinaturasResposta,
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("processo"))],
)
async def assinaturas_json(
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    modo_unidade: ModoUnidade = "envolvida",
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: date | None = None,
    ate: date | None = None,
    data_base: Literal["pedido", "conclusao"] = "pedido",
    id_solicitante: int | None = None,
    id_assinante: int | None = None,
    status: StatusSolicitacao | None = None,
    max_rows: int = Query(500, ge=1, le=5000),
) -> RelatorioAssinaturasResposta:
    f = _filtro_assinaturas(
        id_unidade, modo_unidade, id_assunto, id_tipo_processo, desde, ate, data_base,
        id_solicitante, id_assinante, status,
    )
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    return await gerar_assinaturas(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )


@router.get(
    "/assinaturas.csv",
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("processo"))],
)
async def assinaturas_csv(
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    modo_unidade: ModoUnidade = "envolvida",
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: date | None = None,
    ate: date | None = None,
    data_base: Literal["pedido", "conclusao"] = "pedido",
    id_solicitante: int | None = None,
    id_assinante: int | None = None,
    status: StatusSolicitacao | None = None,
    max_rows: int = Query(50000, ge=1, le=50000),
):
    f = _filtro_assinaturas(
        id_unidade, modo_unidade, id_assunto, id_tipo_processo, desde, ate, data_base,
        id_solicitante, id_assinante, status,
    )
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    r = await gerar_assinaturas(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )

    _exige_completo(r.cortado, r.totais.total, max_rows, "CSV")

    buf = StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    _cabecalho_csv(w, r.descricao_filtros)
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
                {"pendente": "Pendente", "concluida": "Concluída", "cancelada": "Cancelada"}[s.status],
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


@router.get(
    "/assinaturas.pdf",
    dependencies=[Depends(require_modulo("protocolo")), Depends(require_permission("processo"))],
)
async def assinaturas_pdf(
    inline: bool = Query(True),
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    id_unidade: int | None = None,
    modo_unidade: ModoUnidade = "envolvida",
    id_assunto: int | None = None,
    id_tipo_processo: int | None = None,
    desde: date | None = None,
    ate: date | None = None,
    data_base: Literal["pedido", "conclusao"] = "pedido",
    id_solicitante: int | None = None,
    id_assinante: int | None = None,
    status: StatusSolicitacao | None = None,
    max_rows: int = Query(500, ge=1, le=5000),
):
    f = _filtro_assinaturas(
        id_unidade, modo_unidade, id_assunto, id_tipo_processo, desde, ate, data_base,
        id_solicitante, id_assinante, status,
    )
    niveis = await niveis_acesso_usuario(db, user, tenant_id=tenant_id)
    r = await gerar_assinaturas(
        db, f, tenant_id=tenant_id, niveis_permitidos=niveis, max_rows=max_rows
    )
    pdf_bytes = gerar_assinaturas_pdf(r)
    fname = f"assinaturas-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
    )
