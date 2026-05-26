"""Task: gera o PDF do Relatório de Tramitação em background.

Fase 14: storage por tenant (tenant_jobs_dir).
"""
from __future__ import annotations

import asyncio
import traceback
from datetime import datetime
from typing import Any

from ..config import get_settings, tenant_jobs_dir
from ..models import Job
from ..schemas.relatorio import RelatorioFiltro
from ..services.pdf_relatorio_tramitacao import gerar_tramitacao_pdf
from ..services.relatorios_tramitacao import gerar_tramitacao
from ._task_db import task_session_scope
from .celery_app import celery_app

settings = get_settings()


@celery_app.task(name="app.tasks.relatorio_tramitacao_bg.run", bind=True)
def run(
    self,
    job_id: int,
    filtros: dict[str, Any],
    max_processos: int,
    tenant_id: int,
    tenant_slug: str,
) -> str | None:
    return asyncio.run(
        _run_async(self, job_id, filtros, max_processos, tenant_id, tenant_slug)
    )


async def _run_async(
    task,
    job_id: int,
    filtros: dict[str, Any],
    max_processos: int,
    tenant_id: int,
    tenant_slug: str,
) -> str | None:
    async with task_session_scope(tenant_id=tenant_id) as (_engine, Session):
        async with Session() as db:
            job = await db.get(Job, job_id)
            if job is None:
                return None
            job.status = "em_andamento"
            job.iniciado_em = datetime.utcnow()
            job.celery_task_id = task.request.id
            await db.commit()

        try:
            f = RelatorioFiltro.model_validate(filtros)
            async with Session() as db:
                resposta = await gerar_tramitacao(
                    db, f, tenant_id=tenant_id, max_processos=max_processos
                )
            pdf_bytes = gerar_tramitacao_pdf(resposta)

            out_dir = tenant_jobs_dir(tenant_slug) / str(job_id)
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = (
                out_dir / f"tramitacao-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf"
            )
            out_path.write_bytes(pdf_bytes)
            rel = str(out_path.relative_to(settings.tenants_storage_root))

            async with Session() as db:
                job = await db.get(Job, job_id)
                if job is not None:
                    job.status = "concluido"
                    job.resultado_path = rel
                    job.descricao = (
                        f"Relatório tramitação: {resposta.qtd_processos} processo(s)"
                    )
                    job.concluido_em = datetime.utcnow()
                    await db.commit()
            return rel
        except Exception as e:
            async with Session() as db:
                job = await db.get(Job, job_id)
                if job is not None:
                    job.status = "falhou"
                    job.erro = f"{e}\n\n{traceback.format_exc()}"
                    job.concluido_em = datetime.utcnow()
                    await db.commit()
            raise
