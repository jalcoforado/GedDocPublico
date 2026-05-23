"""Task assíncrona que gera o PDF 'processo completo' em background."""
from __future__ import annotations

import asyncio
import os
import traceback
from datetime import datetime

from ..config import get_settings
from ..models import Job
from ..services.pdf_montagem import gerar_processo_completo_pdf
from ..services.processos import get_processo_detail
from ._task_db import task_session_scope
from .celery_app import celery_app

settings = get_settings()


@celery_app.task(name="app.tasks.processo_completo.run", bind=True)
def run(self, job_id: int, processo_id: int) -> str | None:
    return asyncio.run(_run_async(self, job_id, processo_id))


async def _run_async(task, job_id: int, processo_id: int) -> str | None:
    async with task_session_scope() as (_engine, Session):
        async with Session() as db:
            job = await db.get(Job, job_id)
            if job is None:
                return None
            job.status = "em_andamento"
            job.iniciado_em = datetime.utcnow()
            job.celery_task_id = task.request.id
            await db.commit()

        try:
            async with Session() as db:
                detail = await get_processo_detail(db, processo_id)
                if detail is None:
                    raise RuntimeError(f"Processo {processo_id} não encontrado")
                pdf_bytes = gerar_processo_completo_pdf(detail)
                numero_safe = detail.numero_processo.replace("/", "_")

            os.makedirs(settings.jobs_results_dir, exist_ok=True)
            out_dir = os.path.join(settings.jobs_results_dir, str(job_id))
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"processo-completo-{numero_safe}.pdf")
            with open(out_path, "wb") as f:
                f.write(pdf_bytes)

            rel_path = os.path.relpath(out_path, settings.jobs_results_dir)

            async with Session() as db:
                job = await db.get(Job, job_id)
                if job is not None:
                    job.status = "concluido"
                    job.resultado_path = rel_path
                    job.concluido_em = datetime.utcnow()
                    await db.commit()
            return rel_path
        except Exception as e:
            async with Session() as db:
                job = await db.get(Job, job_id)
                if job is not None:
                    job.status = "falhou"
                    job.erro = f"{e}\n\n{traceback.format_exc()}"
                    job.concluido_em = datetime.utcnow()
                    await db.commit()
            raise
