"""Task beat: snapshot diário dos saldos de contas de pagamentos (RF-SLD-03).

Para cada tenant ativo, grava/atualiza uma linha em pagamentos.saldo_historico
por conta (idempotente por (tenant_id, id_conta, data)). Falha em um tenant não
interrompe o varrimento.
"""
from __future__ import annotations

import asyncio
import logging
import traceback

from sqlalchemy import select

from ..models import Tenant
from ..services import pagamentos_caixa as caixa
from ._task_db import task_session_scope
from .celery_app import celery_app

logger = logging.getLogger("pagamentos.snapshot_saldos")


@celery_app.task(name="app.tasks.snapshot_saldos_pagamentos.run", bind=True)
def run(self, tenant_id: int | None = None) -> str:
    """tenant_id=None → todos os tenants ativos (beat); int → um tenant (manual/testes)."""
    return asyncio.run(_run_async(tenant_id))


async def _run_async(tenant_id_filter: int | None) -> str:
    async with task_session_scope() as (_engine, raw_factory):
        async with raw_factory() as db:
            stmt = select(Tenant.id, Tenant.slug).where(Tenant.ativo.is_(True))
            if tenant_id_filter is not None:
                stmt = stmt.where(Tenant.id == tenant_id_filter)
            tenants = (await db.execute(stmt)).all()

    total_contas = 0
    erros: list[str] = []
    for tid, slug in tenants:
        try:
            async with task_session_scope(tenant_id=tid) as (_e, factory):
                async with factory() as db:
                    n = await caixa.registrar_snapshot_saldos(db, tenant_id=tid)
                    total_contas += n
                    logger.info("snapshot_saldos_tenant",
                                extra={"tenant_id": tid, "tenant_slug": slug, "contas": n})
        except Exception as e:  # noqa: BLE001
            erros.append(f"tenant {slug} ({tid}): {e}")
            logger.warning("snapshot_saldos_falhou_tenant",
                           extra={"tenant_id": tid, "tenant_slug": slug, "erro": str(e)})
            logger.debug(traceback.format_exc())

    sumario = (f"Snapshot de saldos concluído — {len(tenants)} tenant(s), "
               f"{total_contas} conta(s).\n")
    if erros:
        sumario += "Erros:\n" + "\n".join(f"  - {e}" for e in erros) + "\n"
    return sumario
