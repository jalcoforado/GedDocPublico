from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import (
    anexos,
    assinaturas,
    assuntos,
    auth,
    catalogo,
    cidadao,
    grupos,
    health,
    jobs,
    localizacao,
    manifestantes,
    modulos,
    permissoes,
    processos,
    relatorios,
    unidades,
    usuarios,
)

settings = get_settings()

app = FastAPI(
    title="Aprimora API",
    version="0.1.0",
    description="Backend Python para migração gradual do Aprimora PHP (Strangler Fig).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(anexos.router, prefix="/api/v2")
app.include_router(assinaturas.router, prefix="/api/v2")
app.include_router(relatorios.router, prefix="/api/v2")
app.include_router(jobs.router, prefix="/api/v2")
app.include_router(cidadao.router, prefix="/api/v2")
