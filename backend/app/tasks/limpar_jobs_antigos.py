"""Task periódica: apaga jobs antigos e seus arquivos de resultado.

Fase 14: limpeza varre `tenants_storage_root` por tenant (modo dispatch manual)
ou globalmente (modo beat agendado). Mantém compat com legacy `jobs_results_dir`
ao tentar remover pastas em ambos os roots.

SEC-RLS-00B (inventário §8.1) — **por que o modo beat itera tenants**:

Até aqui, `tenant_id=None` abria UMA sessão sem `app.tenant_id` e varria
`aprimora_py.job` inteira, contando com o `BYPASSRLS` do papel do runtime.
`aprimora_py.job` tem RLS habilitada e forçada; sob papel sujeito a RLS, a
policy avalia `tenant_id = NULL` e devolve **zero linhas — sem erro**. A
limpeza rodaria todo dia às 03:00, reportaria "0 jobs removidos" e ninguém
notaria por meses; os arquivos ficariam no disco.

Falha silenciosa é pior que falha ruidosa. A correção é dar contexto de tenant
explícito: o modo beat lista os tenants ativos numa sessão sem tenant
(`aprimora_py.tenant` não tem RLS, é catálogo de plataforma) e depois abre
**uma sessão por tenant**, exatamente o desenho que `verificar_sla_workflows`
já usa. Nenhuma leitura cross-tenant sobra, e a task deixa de depender do
bypass.
"""
from __future__ import annotations

import asyncio
import logging
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
logger = logging.getLogger("jobs.limpeza")


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


async def _limpar_tenant(
    Session,
    *,
    tenant_id: int,
    tenant_slug: str | None,
    corte: datetime,
    job_id: int | None,
) -> tuple[int, int]:
    """Apaga jobs anteriores a `corte` de UM tenant. Devolve (jobs, pastas).

    `Session` já vem com `app.tenant_id` instalado pelo caller — a policy de
    `aprimora_py.job` é que garante o escopo, e o `WHERE tenant_id` abaixo é a
    segunda camada (o filtro aplicacional do CLAUDE.md), não a única.
    """
    async with Session() as db:
        stmt = select(Job).where(
            Job.criado_em < corte,
            Job.id != (job_id or -1),
            Job.tenant_id == tenant_id,
        )
        antigos = (await db.execute(stmt)).scalars().all()
        ids = [j.id for j in antigos]

        slug = tenant_slug
        if slug is None and ids:
            slug = (
                await db.execute(select(Tenant.slug).where(Tenant.id == tenant_id))
            ).scalar_one_or_none()

    pastas_removidas = 0
    for jid in ids:
        candidatos: list[Path] = []
        if slug:
            candidatos.append(tenant_jobs_dir(slug) / str(jid))
        candidatos.append(Path(settings.jobs_results_dir) / str(jid))
        for cand in candidatos:
            if cand.exists() and cand.is_dir():
                try:
                    shutil.rmtree(cand)
                    pastas_removidas += 1
                except OSError:
                    pass

    if ids:
        async with Session() as db:
            for jid in ids:
                j = await db.get(Job, jid)
                if j is not None:
                    await db.delete(j)
            await db.commit()

    return len(ids), pastas_removidas


async def _todos_os_tenants() -> list[tuple[int, str]]:
    """Lista `(id, slug)` de **todos** os tenants — inclusive os inativos.

    Sessão SEM `app.tenant_id` de propósito: `aprimora_py.tenant` é catálogo de
    plataforma e não tem RLS. A estrutura é a de `verificar_sla_workflows`, mas
    o filtro **não**: aquela task decide regra de negócio (não faz sentido
    alertar SLA de tenant desligado), esta é higiene de disco.

    Copiar o `ativo.is_(True)` de lá seria trocar uma falha silenciosa por
    outra: antes desta correção a varredura era global, e restringi-la a
    tenants ativos faria os jobs e as pastas de resultado de todo tenant
    desativado ficarem no disco **para sempre**, sem erro e sem log. Tenant
    desativado é justamente o que mais tem lixo acumulado.
    """
    async with task_session_scope() as (_engine, Session):
        async with Session() as db:
            return [
                (int(tid), slug)
                for tid, slug in (
                    await db.execute(select(Tenant.id, Tenant.slug))
                ).all()
            ]


async def _run_async(
    task,
    job_id: int | None,
    dias: int,
    tenant_id: int | None,
    tenant_slug: str | None,
) -> str:
    corte = datetime.utcnow() - timedelta(days=dias)

    # ------------------------------------------------------------------
    # Modo beat: sem tenant. Itera os tenants ativos, um contexto por vez.
    # Falha num tenant não interrompe os demais — mesma política do
    # `verificar_sla_workflows`. A diferença é que aqui a falha é LOGADA e vai
    # para o sumário: limpeza que some sem dizer nada foi exatamente o defeito
    # corrigido.
    # ------------------------------------------------------------------
    if tenant_id is None:
        tenants = await _todos_os_tenants()
        total_jobs = 0
        total_pastas = 0
        falhas: list[str] = []
        for tid, slug in tenants:
            try:
                async with task_session_scope(tenant_id=tid) as (_e, Session):
                    n_jobs, n_pastas = await _limpar_tenant(
                        Session,
                        tenant_id=tid,
                        tenant_slug=slug,
                        corte=corte,
                        job_id=None,
                    )
                total_jobs += n_jobs
                total_pastas += n_pastas
            except Exception as e:  # noqa: BLE001 — um tenant não derruba os outros
                falhas.append(f"{slug}: {e}")
                logger.exception(
                    "limpeza_jobs_falhou_tenant", extra={"tenant_slug": slug}
                )

        sumario = (
            f"Limpeza de jobs anteriores a {corte.strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Critério: mais de {dias} dia(s)\n"
            f"Escopo: {len(tenants)} tenant(s), ativos e inativos\n"
            f"Jobs removidos: {total_jobs}\n"
            f"Pastas de resultado removidas: {total_pastas}\n"
        )
        if falhas:
            sumario += "Tenants com falha: " + "; ".join(falhas) + "\n"
        return sumario

    # ------------------------------------------------------------------
    # Modo dispatch manual: um tenant, possivelmente com um Job de
    # acompanhamento na UI.
    # ------------------------------------------------------------------
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
            n_jobs, n_pastas = await _limpar_tenant(
                Session,
                tenant_id=tenant_id,
                tenant_slug=tenant_slug,
                corte=corte,
                job_id=job_id,
            )

            sumario = (
                f"Limpeza de jobs anteriores a {corte.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"Critério: mais de {dias} dia(s)\n"
                f"Escopo: tenant_id={tenant_id}\n"
                f"Jobs removidos: {n_jobs}\n"
                f"Pastas de resultado removidas: {n_pastas}\n"
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
                            f"Limpeza: {n_jobs} job(s) e "
                            f"{n_pastas} pasta(s) removidos"
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
