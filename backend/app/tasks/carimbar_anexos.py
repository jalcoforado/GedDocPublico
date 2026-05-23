"""Task: pré-carimba todos os anexos PDF de um processo (aquece cache).

Útil quando o processo tem dezenas de anexos novos: faz numa só rodada em
background em vez de carimbar on-demand na 1ª visualização do "processo completo".

Resultado: relatório de quantos foram carimbados, pulados ou falharam.
A task NÃO produz um arquivo PDF — o `resultado_path` aponta para um `.txt`
com o sumário.
"""
from __future__ import annotations

import asyncio
import os
import traceback
from datetime import datetime
from pathlib import Path

from sqlalchemy import and_, select

from ..config import get_settings
from ..models import Anexo, AnexoProcesso, Job, Processo
from ..services.pdf_carimbo import _cache_path, carimbar_pdf_bytes
from ._task_db import task_session_scope
from .celery_app import celery_app

settings = get_settings()


@celery_app.task(name="app.tasks.carimbar_anexos.run", bind=True)
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
                proc = await db.get(Processo, processo_id)
                if proc is None:
                    raise RuntimeError(f"Processo {processo_id} não encontrado")
                numero = proc.numero_processo

                rows = (
                    await db.execute(
                        select(Anexo)
                        .join(AnexoProcesso, AnexoProcesso.id_anexo == Anexo.id)
                        .where(
                            AnexoProcesso.id_processo == processo_id,
                            AnexoProcesso.excluido.is_(False),
                            and_(Anexo.excluido.is_(False), Anexo.ativo.is_(True)),
                            Anexo.e_doc.isnot(None),
                        )
                        .order_by(AnexoProcesso.ordem.nulls_last(), Anexo.id)
                    )
                ).scalars().all()

            carimbados = 0
            cacheados = 0
            sem_arquivo = 0
            nao_pdf = 0
            falhas: list[str] = []

            uploads = Path(settings.uploads_dir)
            for anexo in rows:
                cache = _cache_path(anexo.id)
                if cache.exists():
                    cacheados += 1
                    continue
                if not anexo.e_doc or not anexo.e_doc.lower().endswith(".pdf"):
                    nao_pdf += 1
                    continue
                src = uploads / anexo.e_doc
                if not src.exists():
                    sem_arquivo += 1
                    continue
                try:
                    stamped = carimbar_pdf_bytes(
                        src.read_bytes(),
                        numero_processo=numero,
                        e_doc=anexo.e_doc,
                    )
                    cache.write_bytes(stamped)
                    carimbados += 1
                except Exception as e:
                    falhas.append(f"#{anexo.id}: {type(e).__name__}: {e}")

            sumario = (
                f"Processo: {numero} (#{processo_id})\n"
                f"Total de anexos elegíveis: {len(rows)}\n"
                f"Carimbados agora: {carimbados}\n"
                f"Já estavam em cache: {cacheados}\n"
                f"Não-PDF (pulados): {nao_pdf}\n"
                f"Sem arquivo no storage: {sem_arquivo}\n"
                f"Falhas: {len(falhas)}\n"
            )
            if falhas:
                sumario += "\nDetalhes das falhas:\n" + "\n".join(f"  - {f}" for f in falhas)

            os.makedirs(settings.jobs_results_dir, exist_ok=True)
            out_dir = os.path.join(settings.jobs_results_dir, str(job_id))
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"carimbar-anexos-{processo_id}.txt")
            Path(out_path).write_text(sumario, encoding="utf-8")
            rel = os.path.relpath(out_path, settings.jobs_results_dir)

            async with Session() as db:
                job = await db.get(Job, job_id)
                if job is not None:
                    job.status = "concluido"
                    job.resultado_path = rel
                    job.descricao = (
                        f"Carimbar anexos #{processo_id}: "
                        f"{carimbados} novos, {cacheados} já cacheados, "
                        f"{len(falhas)} falha(s)"
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
