"""Celery app — usado pelo worker (`celery -A app.tasks.celery_app worker`).

Tarefas são módulos sob `app.tasks.*` e importadas via `include` aqui.
Não rodar o Celery no mesmo processo do FastAPI: o produtor (API) usa
`task.delay()` ou `task.apply_async()` que enfileiram no Redis e retornam imediatamente.

Beat (scheduler): container separado roda `celery -A app.tasks.celery_app beat`,
lê `beat_schedule` abaixo e dispara as tasks periódicas.
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from ..config import get_settings

settings = get_settings()

celery_app = Celery(
    "aprimora",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.processo_completo",
        "app.tasks.carimbar_anexos",
        "app.tasks.relatorio_tramitacao_bg",
        "app.tasks.limpar_jobs_antigos",
        "app.tasks.verificar_sla_workflows",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Fortaleza",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600 * 24,
)

# Schedule periódico. Roda no container `beat`.
celery_app.conf.beat_schedule = {
    "limpar-jobs-antigos-diario": {
        "task": "app.tasks.limpar_jobs_antigos.run",
        "schedule": crontab(hour=3, minute=0),  # 03:00 todos os dias
        "kwargs": {"dias": 30},
    },
    # Fase 21 — varre workflows ativos e cria alertas de SLA estourado.
    # 4x ao dia (06, 12, 18, 00) — granularidade de horas é overkill já
    # que SLA é em dias.
    "verificar-sla-workflows": {
        "task": "app.tasks.verificar_sla_workflows.run",
        "schedule": crontab(hour="0,6,12,18", minute=0),
    },
}
