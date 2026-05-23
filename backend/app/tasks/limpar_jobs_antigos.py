"""Task periódica: apaga jobs antigos e seus arquivos de resultado.

Por padrão considera "antigo" qualquer job com `criado_em` < (now - 30 dias).
O schedule fica em `celery_app.conf.beat_schedule`.

Diferente das outras tasks, esta NÃO cria um registro `Job` próprio (seria
recursivo). Quando disparada manualmente via endpoint, cria um registro
para que o usuário veja o resultado em /jobs; o beat-trigger roda sem registro.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from ..config import get_settings
from ..models import Job
from ._task_db import task_session_scope
from .celery_app import celery_app

settings = get_settings()


@celery_app.task(name="app.tasks.limpar_jobs_antigos.run", bind=True)
def run(self, job_id: int | None = None, dias: int = 30) -> str:
    return asyncio.run(_run_async(self, job_id, dias))


async def _run_async(task, job_id: int | None, dias: int) -> str:
    async with task_session_scope() as (_engine, Session):
        # Se há job tracker, marca como em_andamento
        if job_id is not None:
            async with Session() as db:
                j = await db.get(Job, job_id)
                if j is not None:
                    j.status = "em_andamento"
                    j.iniciado_em = datetime.utcnow()
                    j.celery_task_id = task.request.id
                    await db.commit()

        try:
            corte = datetime.utcnow() - timedelta(days=dias)
            async with Session() as db:
                antigos = (
                    await db.execute(
                        select(Job).where(
                            Job.criado_em < corte,
                            # Não apaga o próprio registro de limpeza em execução
                            Job.id != (job_id or -1),
                        )
                    )
                ).scalars().all()
                ids = [j.id for j in antigos]

            arquivos_removidos = 0
            for jid in ids:
                pasta = Path(settings.jobs_results_dir) / str(jid)
                if pasta.exists() and pasta.is_dir():
                    try:
                        shutil.rmtree(pasta)
                        arquivos_removidos += 1
                    except OSError:
                        pass

            async with Session() as db:
                for jid in ids:
                    j = await db.get(Job, jid)
                    if j is not None:
                        await db.delete(j)
                await db.commit()

            sumario = (
                f"Limpeza de jobs anteriores a {corte.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"Critério: mais de {dias} dia(s)\n"
                f"Jobs removidos: {len(ids)}\n"
                f"Pastas de resultado removidas: {arquivos_removidos}\n"
            )

            if job_id is not None:
                os.makedirs(settings.jobs_results_dir, exist_ok=True)
                out_dir = os.path.join(settings.jobs_results_dir, str(job_id))
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, "limpeza.txt")
                Path(out_path).write_text(sumario, encoding="utf-8")
                rel = os.path.relpath(out_path, settings.jobs_results_dir)

                async with Session() as db:
                    j = await db.get(Job, job_id)
                    if j is not None:
                        j.status = "concluido"
                        j.resultado_path = rel
                        j.descricao = (
                            f"Limpeza: {len(ids)} job(s) e {arquivos_removidos} pasta(s) removidos"
                        )
                        j.concluido_em = datetime.utcnow()
                        await db.commit()
            return sumario
        except Exception as e:
            if job_id is not None:
                async with Session() as db:
                    j = await db.get(Job, job_id)
                    if j is not None:
                        j.status = "falhou"
                        j.erro = f"{e}\n\n{traceback.format_exc()}"
                        j.concluido_em = datetime.utcnow()
                        await db.commit()
            raise
