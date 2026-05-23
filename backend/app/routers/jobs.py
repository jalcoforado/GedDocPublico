"""Endpoints de jobs assíncronos."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..config import get_settings
from ..database import get_db
from ..models import Usuario
from ..schemas.job import (
    AgendaItem,
    DispararCarimbarAnexosRequest,
    DispararLimpezaRequest,
    DispararProcessoCompletoRequest,
    DispararRelatorioTramitacaoRequest,
    JobOut,
)
from ..services.jobs import (
    criar_job_carimbar_anexos,
    criar_job_limpeza,
    criar_job_processo_completo,
    criar_job_relatorio_tramitacao,
    get_job,
    listar_jobs,
)

settings = get_settings()
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
async def list_jobs_endpoint(
    todos: bool = Query(False, description="Se True, retorna jobs de todos os usuários"),
    limit: int = Query(50, ge=1, le=500),
    current: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[JobOut]:
    return await listar_jobs(db, usuario_id=current.id, todos=todos, limit=limit)


@router.get("/agenda", response_model=list[AgendaItem])
async def listar_agenda_endpoint(
    _: Usuario = Depends(get_current_user),
) -> list[AgendaItem]:
    # Import tardio para não exigir o broker no startup da API.
    from ..tasks.celery_app import celery_app

    items: list[AgendaItem] = []
    for nome, cfg in (celery_app.conf.beat_schedule or {}).items():
        items.append(
            AgendaItem(
                nome=nome,
                task=cfg.get("task", ""),
                schedule=str(cfg.get("schedule")),
                kwargs=cfg.get("kwargs"),
            )
        )
    return items


@router.get("/{job_id}", response_model=JobOut)
async def get_job_endpoint(
    job_id: int,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    row = await get_job(db, job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado")
    job, nome = row
    out = JobOut.model_validate(job)
    out.nome_usuario = nome
    return out


@router.post(
    "/processo-completo",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def disparar_processo_completo(
    payload: DispararProcessoCompletoRequest,
    current: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    # Import tardio para não puxar Celery no startup da API caso o worker esteja fora.
    from ..tasks.processo_completo import run as run_task

    job = await criar_job_processo_completo(
        db, processo_id=payload.id_processo, usuario_id=current.id
    )
    run_task.delay(job.id, payload.id_processo)
    out = JobOut.model_validate(job)
    out.nome_usuario = current.nome
    return out


@router.post(
    "/carimbar-anexos",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def disparar_carimbar_anexos(
    payload: DispararCarimbarAnexosRequest,
    current: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    from ..tasks.carimbar_anexos import run as run_task

    job = await criar_job_carimbar_anexos(
        db, processo_id=payload.id_processo, usuario_id=current.id
    )
    run_task.delay(job.id, payload.id_processo)
    out = JobOut.model_validate(job)
    out.nome_usuario = current.nome
    return out


@router.post(
    "/relatorio-tramitacao",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def disparar_relatorio_tramitacao(
    payload: DispararRelatorioTramitacaoRequest,
    current: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    from ..tasks.relatorio_tramitacao_bg import run as run_task

    filtros = {
        "id_unidade": payload.id_unidade,
        "id_assunto": payload.id_assunto,
        "id_tipo_processo": payload.id_tipo_processo,
        "desde": payload.desde.isoformat() if payload.desde else None,
        "ate": payload.ate.isoformat() if payload.ate else None,
        "apenas_ativos": payload.apenas_ativos,
    }
    job = await criar_job_relatorio_tramitacao(
        db,
        filtros=filtros,
        max_processos=payload.max_processos,
        usuario_id=current.id,
    )
    run_task.delay(job.id, filtros, payload.max_processos)
    out = JobOut.model_validate(job)
    out.nome_usuario = current.nome
    return out


@router.post(
    "/limpar-antigos",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def disparar_limpeza(
    payload: DispararLimpezaRequest,
    current: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    from ..tasks.limpar_jobs_antigos import run as run_task

    job = await criar_job_limpeza(db, dias=payload.dias, usuario_id=current.id)
    run_task.delay(job.id, payload.dias)
    out = JobOut.model_validate(job)
    out.nome_usuario = current.nome
    return out


@router.get("/{job_id}/resultado")
async def baixar_resultado(
    job_id: int,
    current: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await get_job(db, job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado")
    job, _ = row
    if job.status != "concluido" or not job.resultado_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job ainda não concluído (status={job.status})",
        )
    full = os.path.join(settings.jobs_results_dir, job.resultado_path)
    if not os.path.exists(full):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Arquivo de resultado não está mais disponível",
        )
    fname = os.path.basename(full)
    media = "application/pdf" if fname.lower().endswith(".pdf") else "text/plain"
    return FileResponse(full, filename=fname, media_type=media)
