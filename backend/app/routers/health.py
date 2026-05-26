"""Healthcheck — Fase 33.

Devolve estado mínimo + ping no DB. Não exige tenant resolvido (rota usada
por orquestrador/load-balancer/runbook DR).
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db

router = APIRouter()


@router.get("/health")
async def health(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    db_status = "ok"
    db_latency_ms: int | None = None
    try:
        import time

        t0 = time.perf_counter()
        result = await db.execute(text("SELECT 1"))
        if result.scalar() != 1:
            db_status = "unexpected_result"
        db_latency_ms = int((time.perf_counter() - t0) * 1000)
    except Exception as e:
        db_status = f"error:{type(e).__name__}"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": request.app.version,
        "db": db_status,
        "db_latency_ms": db_latency_ms,
        "tenant": getattr(request.state, "tenant_slug", None),
    }
