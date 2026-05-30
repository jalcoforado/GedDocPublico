"""Endpoints do dashboard executivo — Fases 18a (KPIs) + 18b (filtros/comparativo) + 18c (export) + PR 5a (dimensão serviço).

PR 5a — D-PERMISSAO: os três endpoints passam a exigir a transação
`dashboard` (semeada pela migration 0028). Super-usuário continua
bypassando (via `services/permissoes.py::load_permissions`).
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Tenant, Usuario
from ..schemas.dashboard import DashboardKpis
from ..services.dashboard import kpis as compute_kpis
from ..services.dashboard_export import to_csv, to_pdf

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=DashboardKpis)
async def get_kpis(
    _: Usuario = Depends(require_permission("dashboard")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    periodo: int = Query(30, description="Janela em dias (7/30/90/365)"),
    id_unidade: int | None = Query(None),
    id_servico: int | None = Query(None, description="PR 5a — isola contadores ao serviço"),
    incluir_legado: bool = Query(True, description="PR 5a — incluir processos sem id_servico"),
):
    data = await compute_kpis(
        db,
        tenant_id=tenant_id,
        periodo_dias=periodo,
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )
    return DashboardKpis.model_validate(data)


async def _nome_tenant(db: AsyncSession, tenant_id: int) -> str:
    row = (
        await db.execute(select(Tenant.nome).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    return row or ""


@router.get("/export.csv")
async def export_csv(
    _: Usuario = Depends(require_permission("dashboard")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    periodo: int = Query(30),
    id_unidade: int | None = Query(None),
    id_servico: int | None = Query(None),
    incluir_legado: bool = Query(True),
):
    """CSV multi-seção: cabeçalho `#`, depois seções `[Volume]`, `[Conclusão]`,
    `[SLA]`, breakdowns, série temporal e (PR 5a) `[Documental]`,
    `[Complementação]`, `[Por serviço]`. Encoding utf-8 com BOM pra Excel-PT."""
    data = await compute_kpis(
        db,
        tenant_id=tenant_id,
        periodo_dias=periodo,
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )
    nome = await _nome_tenant(db, tenant_id)
    csv_str = to_csv(data, nome_tenant=nome)
    body = ("﻿" + csv_str).encode("utf-8")
    fname = f"dashboard-{datetime.now().strftime('%Y%m%d-%H%M')}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/export.pdf")
async def export_pdf(
    _: Usuario = Depends(require_permission("dashboard")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    periodo: int = Query(30),
    id_unidade: int | None = Query(None),
    id_servico: int | None = Query(None),
    incluir_legado: bool = Query(True),
    inline: bool = Query(True),
):
    data = await compute_kpis(
        db,
        tenant_id=tenant_id,
        periodo_dias=periodo,
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )
    nome = await _nome_tenant(db, tenant_id)
    pdf_bytes = to_pdf(data, nome_tenant=nome)
    fname = f"dashboard-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
    )
