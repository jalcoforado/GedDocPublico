"""Service de jobs assíncronos.

Cria o registro `aprimora_py.job` antes de enfileirar a task. O Celery pega o
`job_id` resultante e atualiza o status na medida que progride.

Fase 13a: cada criação recebe `tenant_id`; lista/get filtram pelo escopo.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..models import Job, Usuario
from ..schemas.job import JobOut


async def criar_job_processo_completo(
    db: AsyncSession, *, tenant_id: int, processo_id: int, usuario_id: int
) -> Job:
    job = Job(
        tenant_id=tenant_id,
        tipo="processo_completo",
        descricao=f"Processo completo #{processo_id}",
        status="pendente",
        parametros={"id_processo": processo_id},
        id_usuario=usuario_id,
        criado_em=datetime.utcnow(),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def criar_job_carimbar_anexos(
    db: AsyncSession, *, tenant_id: int, processo_id: int, usuario_id: int
) -> Job:
    job = Job(
        tenant_id=tenant_id,
        tipo="carimbar_anexos",
        descricao=f"Pré-carimbar anexos do processo #{processo_id}",
        status="pendente",
        parametros={"id_processo": processo_id},
        id_usuario=usuario_id,
        criado_em=datetime.utcnow(),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def criar_job_limpeza(
    db: AsyncSession, *, tenant_id: int, dias: int, usuario_id: int
) -> Job:
    job = Job(
        tenant_id=tenant_id,
        tipo="limpar_jobs_antigos",
        descricao=f"Limpeza manual: jobs com mais de {dias} dia(s)",
        status="pendente",
        parametros={"dias": dias},
        id_usuario=usuario_id,
        criado_em=datetime.utcnow(),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def criar_job_relatorio_tramitacao(
    db: AsyncSession,
    *,
    tenant_id: int,
    filtros: dict,
    max_processos: int,
    usuario_id: int,
) -> Job:
    job = Job(
        tenant_id=tenant_id,
        tipo="relatorio_tramitacao",
        descricao="Relatório de tramitação (background)",
        status="pendente",
        parametros={"filtros": filtros, "max_processos": max_processos},
        id_usuario=usuario_id,
        criado_em=datetime.utcnow(),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def listar_jobs(
    db: AsyncSession,
    *,
    tenant_id: int,
    usuario_id: int | None = None,
    todos: bool = False,
    limit: int = 50,
) -> list[JobOut]:
    User = aliased(Usuario, name="u")
    stmt = (
        select(Job, User.nome.label("nome_usuario"))
        .join(User, User.id == Job.id_usuario, isouter=True)
        .where(Job.tenant_id == tenant_id)
        .order_by(Job.criado_em.desc())
        .limit(limit)
    )
    if not todos and usuario_id is not None:
        stmt = stmt.where(Job.id_usuario == usuario_id)
    rows = (await db.execute(stmt)).all()
    out: list[JobOut] = []
    for job, nome in rows:
        item = JobOut.model_validate(job)
        item.nome_usuario = nome
        out.append(item)
    return out


async def get_job(
    db: AsyncSession, job_id: int, *, tenant_id: int
) -> tuple[Job, str | None] | None:
    User = aliased(Usuario, name="u")
    row = (
        await db.execute(
            select(Job, User.nome.label("nome_usuario"))
            .join(User, User.id == Job.id_usuario, isouter=True)
            .where(Job.id == job_id, Job.tenant_id == tenant_id)
        )
    ).first()
    if row is None:
        return None
    return row[0], row.nome_usuario
