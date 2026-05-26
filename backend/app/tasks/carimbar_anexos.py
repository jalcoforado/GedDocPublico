"""Task: pré-carimba todos os anexos PDF de um processo (aquece cache).

Fase 14: cache de carimbados e arquivos lidos vão por tenant
(tenant_carimbados_dir + resolve_anexo_path).
"""
from __future__ import annotations

import asyncio
import traceback
from datetime import datetime
from pathlib import Path

from sqlalchemy import and_, select

from ..config import (
    get_settings,
    resolve_anexo_path,
    tenant_carimbados_dir,
    tenant_jobs_dir,
)
from ..models import Anexo, AnexoProcesso, Job, Processo
from ..services.pdf_carimbo import carimbar_pdf_bytes
from ._task_db import task_session_scope
from .celery_app import celery_app

settings = get_settings()


@celery_app.task(name="app.tasks.carimbar_anexos.run", bind=True)
def run(
    self, job_id: int, processo_id: int, tenant_id: int, tenant_slug: str
) -> str | None:
    return asyncio.run(
        _run_async(self, job_id, processo_id, tenant_id, tenant_slug)
    )


async def _run_async(
    task, job_id: int, processo_id: int, tenant_id: int, tenant_slug: str
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
            async with Session() as db:
                proc = (
                    await db.execute(
                        select(Processo).where(
                            Processo.id == processo_id,
                            Processo.tenant_id == tenant_id,
                        )
                    )
                ).scalar_one_or_none()
                if proc is None:
                    raise RuntimeError(f"Processo {processo_id} não encontrado")
                numero = proc.numero_processo

                rows = (
                    await db.execute(
                        select(Anexo)
                        .join(AnexoProcesso, AnexoProcesso.id_anexo == Anexo.id)
                        .where(
                            AnexoProcesso.id_processo == processo_id,
                            AnexoProcesso.tenant_id == tenant_id,
                            AnexoProcesso.excluido.is_(False),
                            and_(Anexo.excluido.is_(False), Anexo.ativo.is_(True)),
                            Anexo.tenant_id == tenant_id,
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

            carimbados_dir = tenant_carimbados_dir(tenant_slug)
            for anexo in rows:
                cache = carimbados_dir / f"{anexo.id}.pdf"
                if cache.exists():
                    cacheados += 1
                    continue
                if not anexo.e_doc or not anexo.e_doc.lower().endswith(".pdf"):
                    nao_pdf += 1
                    continue
                src = resolve_anexo_path(tenant_slug, anexo.e_doc)
                if src is None:
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

            out_dir = tenant_jobs_dir(tenant_slug) / str(job_id)
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"carimbar-anexos-{processo_id}.txt"
            Path(out_path).write_text(sumario, encoding="utf-8")
            rel = str(out_path.relative_to(settings.tenants_storage_root))

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
