"""Endpoints de jobs assíncronos."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id, require_tenant_slug
from ..auth.modulos import require_modulo
from ..auth.perms import require_permission
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


@router.get(
    "",
    response_model=list[JobOut],
    dependencies=[Depends(require_modulo("administracao")), Depends(require_permission("processo"))],
)
async def list_jobs_endpoint(
    todos: bool = Query(False, description="Se True, retorna jobs de todos os usuários do tenant"),
    limit: int = Query(50, ge=1, le=500),
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[JobOut]:
    return await listar_jobs(
        db, tenant_id=tenant_id, usuario_id=current.id, todos=todos, limit=limit
    )


# Efeito colateral aceito (achado no review final, 2026-07-30): este é o caso
# mais forte dos oito endpoints afetados no repo (ver o comentário equivalente
# em `routers/catalogo.py` e `routers/localizacao.py`). Antes da branch, esta
# rota não tocava banco nem tenant algum — só lia `celery_app.conf.beat_schedule`
# in-process. Agora `require_modulo("administracao")` injeta `require_tenant_id`
# (400 possível fora do nginx, com `STRICT_TENANT_RESOLUTION=true` e Host sem
# subdomínio resolvível) E abre uma sessão de banco para dois SELECTs
# (`slugs_contratados`, que resolve contratados + módulos não-contratáveis).
# Aceito por ora; atrás do nginx (produção) o tenant sempre resolve.
@router.get(
    "/agenda",
    response_model=list[AgendaItem],
    dependencies=[Depends(require_modulo("administracao")), Depends(require_permission("processo"))],
)
async def listar_agenda_endpoint(
    _: Usuario = Depends(get_current_user),
) -> list[AgendaItem]:
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


@router.get(
    "/{job_id}",
    response_model=JobOut,
    dependencies=[Depends(require_modulo("administracao")), Depends(require_permission("processo"))],
)
async def get_job_endpoint(
    job_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    row = await get_job(db, job_id, tenant_id=tenant_id)
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
    # Monta o PDF integral de um processo: exige acesso ao próprio processo,
    # o mesmo código que os endpoints síncronos de protocolo exigem.
    current: Usuario = Depends(require_permission("processo")),
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    from ..tasks.processo_completo import run as run_task

    job = await criar_job_processo_completo(
        db, tenant_id=tenant_id, processo_id=payload.id_processo, usuario_id=current.id
    )
    run_task.delay(job.id, payload.id_processo, tenant_id, tenant_slug)
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
    # Reescreve os anexos do processo (carimbo) — é alteração, não leitura.
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    from ..tasks.carimbar_anexos import run as run_task

    job = await criar_job_carimbar_anexos(
        db, tenant_id=tenant_id, processo_id=payload.id_processo, usuario_id=current.id
    )
    run_task.delay(job.id, payload.id_processo, tenant_id, tenant_slug)
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
    # Relatório sobre processos do tenant — leitura de protocolo.
    current: Usuario = Depends(require_permission("processo")),
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
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
        tenant_id=tenant_id,
        filtros=filtros,
        max_processos=payload.max_processos,
        usuario_id=current.id,
    )
    run_task.delay(job.id, filtros, payload.max_processos, tenant_id, tenant_slug)
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
    # Apaga artefatos de jobs antigos — e todo job deste router é de protocolo
    # (PDF de processo, carimbo, relatório de tramitação). Por isso `processo`,
    # como os vizinhos, e não `configuracao`: esse código mora no módulo
    # `administracao`, e um tenant que contratou só `protocolo` levaria 403 ao
    # limpar artefatos do próprio protocolo — sem escapatória, já que o gate
    # de módulo roda antes do bypass de super-usuário.
    #
    # Inconsistência aceita (Task 3, 2026-07-30): os 4 GETs deste mesmo router
    # (listar, agenda, detalhe, resultado) passaram a exigir require_modulo
    # ("administracao") — é o mecanismo de fila que é administracao no mapa
    # de rotas, não o conteúdo dos artefatos. Resultado: um tenant com
    # `protocolo` e sem `administracao` dispara esta limpeza mas não lê o
    # resultado de nenhum job. Decisão humana registrada no escopo da fatia;
    # não "corrigir" trocando o gate de um lado ou de outro sem falar com o
    # Jorge primeiro.
    current: Usuario = Depends(require_permission("processo", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    from ..tasks.limpar_jobs_antigos import run as run_task

    job = await criar_job_limpeza(
        db, tenant_id=tenant_id, dias=payload.dias, usuario_id=current.id
    )
    run_task.delay(job.id, payload.dias, tenant_id, tenant_slug)
    out = JobOut.model_validate(job)
    out.nome_usuario = current.nome
    return out


@router.get(
    "/{job_id}/resultado",
    dependencies=[Depends(require_modulo("administracao")), Depends(require_permission("processo"))],
)
async def baixar_resultado(
    job_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    row = await get_job(db, job_id, tenant_id=tenant_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado")
    job, _ = row
    if job.status != "concluido" or not job.resultado_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job ainda não concluído (status={job.status})",
        )
    # Resolve em ambos os roots: novo (tenants_storage_root) e legacy (jobs_results_dir).
    full_new = os.path.join(settings.tenants_storage_root, job.resultado_path)
    full_legacy = os.path.join(settings.jobs_results_dir, job.resultado_path)
    full = full_new if os.path.exists(full_new) else full_legacy
    if not os.path.exists(full):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Arquivo de resultado não está mais disponível",
        )
    fname = os.path.basename(full)
    media = "application/pdf" if fname.lower().endswith(".pdf") else "text/plain"
    return FileResponse(full, filename=fname, media_type=media)
