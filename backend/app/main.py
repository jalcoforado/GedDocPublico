from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .middleware.request_logging import RequestLoggingMiddleware
from .middleware.tenant import TenantMiddleware
from .observability.logging import configure_logging
from .observability.sentry import init_sentry
from .routers import (
    anexos,
    assinaturas,
    assuntos,
    audit,
    auth,
    branding,
    busca,
    catalogo,
    cidadao,
    dashboard,
    grupos,
    health,
    jobs,
    localizacao,
    manifestantes,
    modulos,
    notificacoes,
    organograma,
    permissoes,
    processos,
    protocolo,
    relatorios,
    tenant,
    unidades,
    usuarios,
    validacao_publica,
    workflow,
)

settings = get_settings()

# Fase 33 — logging JSON estruturado em todo o app. Idempotente.
configure_logging(settings.log_level)

# Fase 33 — Sentry opcional (só ativa se SENTRY_DSN setado).
init_sentry()

app = FastAPI(
    title="Aprimora API",
    version="0.1.0",
    description="Backend Python para migração gradual do Aprimora PHP (Strangler Fig).",
)

# Ordem da pilha (Starlette envolve do último ao primeiro, então a ordem de
# EXECUÇÃO é reversa da ordem de add_middleware):
#   add_middleware(A) → A é mais interno (executa por último, mais perto do app)
#   add_middleware(Z) → Z é mais externo (executa primeiro na entrada do request)
#
# Queremos: RequestLogging (externo, loga até OPTIONS) → CORS → Tenant → app.
# Logo, ordem de add: Tenant, CORS, RequestLogging.
app.add_middleware(TenantMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(health.router, prefix="/api/v2", tags=["health"])
app.include_router(auth.router, prefix="/api/v2")
app.include_router(permissoes.router, prefix="/api/v2")
app.include_router(modulos.router, prefix="/api/v2")
app.include_router(catalogo.router, prefix="/api/v2")
app.include_router(usuarios.router, prefix="/api/v2")
app.include_router(unidades.router, prefix="/api/v2")
app.include_router(grupos.router, prefix="/api/v2")
app.include_router(localizacao.router, prefix="/api/v2")
app.include_router(manifestantes.router, prefix="/api/v2")
app.include_router(assuntos.router, prefix="/api/v2")
app.include_router(processos.router, prefix="/api/v2")
app.include_router(protocolo.router, prefix="/api/v2")
app.include_router(anexos.router, prefix="/api/v2")
app.include_router(assinaturas.router, prefix="/api/v2")
app.include_router(validacao_publica.router, prefix="/api/v2")
app.include_router(relatorios.router, prefix="/api/v2")
app.include_router(jobs.router, prefix="/api/v2")
app.include_router(notificacoes.router, prefix="/api/v2")
app.include_router(dashboard.router, prefix="/api/v2")
app.include_router(organograma.router, prefix="/api/v2")
app.include_router(audit.router, prefix="/api/v2")
app.include_router(busca.router, prefix="/api/v2")
app.include_router(cidadao.router, prefix="/api/v2")
app.include_router(tenant.router, prefix="/api/v2")
app.include_router(branding.router, prefix="/api/v2")
app.include_router(workflow.router, prefix="/api/v2")
app.include_router(workflow.instances_router, prefix="/api/v2")
app.include_router(workflow.mapeamento_router, prefix="/api/v2")
app.include_router(workflow.processos_workflow_router, prefix="/api/v2")
app.include_router(workflow.alertas_router, prefix="/api/v2")
