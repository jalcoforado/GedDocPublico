"""Task periódica: apaga jobs antigos e seus arquivos de resultado.

Fase 14: limpeza varre `tenants_storage_root` por tenant (modo dispatch manual)
ou globalmente (modo beat agendado). Mantém compat com legacy `jobs_results_dir`
ao tentar remover pastas em ambos os roots.
"""
from __future__ import annotations

import asyncio
import shutil
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from ..config import get_settings, tenant_jobs_dir
from ..models import Job, Tenant
from ._task_db import task_session_scope
from .celery_app import celery_app

settings = get_settings()


@celery_app.task(name="app.tasks.limpar_jobs_antigos.run", bind=True)
def run(
    self,
    job_id: int | None = None,
    dias: int = 30,
    tenant_id: int | None = None,
    tenant_slug: str | None = None,
) -> str:
    """tenant_id=None → limpa jobs de TODOS os tenants (modo beat agendado).
    tenant_id=int + tenant_slug → restringe a um tenant (modo dispatch manual).
    """
    return asyncio.run(
        _run_async(self, job_id, dias, tenant_id, tenant_slug)
    )


async def _run_async(
    task,
    job_id: int | None,
    dias: int,
    tenant_id: int | None,
    tenant_slug: str | None,
) -> str:
    async with task_session_scope(tenant_id=tenant_id) as (_engine, Session):
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
                stmt = select(Job).where(
                    Job.criado_em < corte,
                    Job.id != (job_id or -1),
                )
                if tenant_id is not None:
                    stmt = stmt.where(Job.tenant_id == tenant_id)
                antigos = (await db.execute(stmt)).scalars().all()
                # (job_id, tenant_id) — para resolver pasta correta no fs
                ids_with_tid = [(j.id, j.tenant_id) for j in antigos]

                # Lookup de slugs (cache local)
                tenant_slugs: dict[int, str] = {}
                if tenant_slug and tenant_id:
                    tenant_slugs[tenant_id] = tenant_slug
                tids_to_lookup = {tid for _, tid in ids_with_tid if tid not in tenant_slugs}
                if tids_to_lookup:
                    tslugs = (
                        await db.execute(
                            select(Tenant.id, Tenant.slug).where(
                                Tenant.id.in_(tids_to_lookup)
                            )
                        )
                    ).all()
                    for tid, slug in tslugs:
                        tenant_slugs[tid] = slug

            arquivos_removidos = 0
            for jid, tid in ids_with_tid:
                slug = tenant_slugs.get(tid)
                candidatos: list[Path] = []
                if slug:
                    candidatos.append(tenant_jobs_dir(slug) / str(jid))
                candidatos.append(Path(settings.jobs_results_dir) / str(jid))
                for cand in candidatos:
                    if cand.exists() and cand.is_dir():
                        try:
                            shutil.rmtree(cand)
                            arquivos_removidos += 1
                        except OSError:
                            pass

            async with Session() as db:
                for jid, _ in ids_with_tid:
                    j = await db.get(Job, jid)
                    if j is not None:
                        await db.delete(j)
                await db.commit()

            sumario = (
                f"Limpeza de jobs anteriores a {corte.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"Critério: mais de {dias} dia(s)\n"
                f"Escopo: {'tenant_id=' + str(tenant_id) if tenant_id else 'todos os tenants'}\n"
                f"Jobs removidos: {len(ids_with_tid)}\n"
                f"Pastas de resultado removidas: {arquivos_removidos}\n"
            )

            if job_id is not None and tenant_slug:
                out_dir = tenant_jobs_dir(tenant_slug) / str(job_id)
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / "limpeza.txt"
                out_path.write_text(sumario, encoding="utf-8")
                rel = str(out_path.relative_to(settings.tenants_storage_root))

                async with Session() as db:
                    j = await db.get(Job, job_id)
                    if j is not None:
                        j.status = "concluido"
                        j.resultado_path = rel
                        j.descricao = (
                            f"Limpeza: {len(ids_with_tid)} job(s) e "
                            f"{arquivos_removidos} pasta(s) removidos"
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
