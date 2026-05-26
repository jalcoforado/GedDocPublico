"""Endpoints do dashboard executivo — Fases 18a (KPIs) + 18b (filtros/comparativo) + 18c (export)."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..database import get_db
from ..models import Tenant, Usuario
from ..schemas.dashboard import DashboardKpis
from ..services.dashboard import kpis as compute_kpis
from ..services.dashboard_export import to_csv, to_pdf

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=DashboardKpis)
async def get_kpis(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    periodo: int = Query(30, description="Janela em dias (7/30/90/365)"),
    id_unidade: int | None = Query(None),
):
    data = await compute_kpis(
        db,
        tenant_id=tenant_id,
        periodo_dias=periodo,
        id_unidade=id_unidade,
    )
    return DashboardKpis.model_validate(data)


async def _nome_tenant(db: AsyncSession, tenant_id: int) -> str:
    row = (
        await db.execute(select(Tenant.nome).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    return row or ""


@router.get("/export.csv")
async def export_csv(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    periodo: int = Query(30),
    id_unidade: int | None = Query(None),
):
    """CSV multi-seção: cabeçalho `#`, depois seções `[Volume]`, `[Conclusão]`,
    `[SLA]`, breakdowns e série temporal. Encoding utf-8 com BOM pra Excel-PT."""
    data = await compute_kpis(
        db, tenant_id=tenant_id, periodo_dias=periodo, id_unidade=id_unidade
    )
    nome = await _nome_tenant(db, tenant_id)
    csv_str = to_csv(data, nome_tenant=nome)
    # BOM ajuda o Excel a abrir UTF-8 com acentos corretos
    body = ("﻿" + csv_str).encode("utf-8")
    fname = f"dashboard-{datetime.now().strftime('%Y%m%d-%H%M')}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/export.pdf")
async def export_pdf(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    periodo: int = Query(30),
    id_unidade: int | None = Query(None),
    inline: bool = Query(True),
):
    data = await compute_kpis(
        db, tenant_id=tenant_id, periodo_dias=periodo, id_unidade=id_unidade
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
