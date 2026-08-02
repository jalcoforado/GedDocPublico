"""Sessão SQLAlchemy isolada para uso DENTRO de tasks Celery.

Por que: o engine global do FastAPI tem conexões asyncpg amarradas à event loop
original. Cada `asyncio.run()` cria uma loop nova; reusar essas conexões dispara
RuntimeError "Future attached to a different loop".

Solução: cada task cria um engine novo (NullPool → nenhuma conexão é reaproveitada)
e o descarta no fim. Não compartilhar este engine entre tasks distintas.

Fase 13b: o listener global em `app.database` (registrado em `_SyncSession`)
dispara `SET LOCAL app.tenant_id` em qualquer Session sync que tenha
`session.info["tenant_id"]`. Quando o caller passa `tenant_id` ao scope,
populamos esse info em cada session retornada.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

# Importa o listener global; basta importar para o event handler estar registrado.
from .. import database as _database_ensure_listener  # noqa: F401
from ..config import get_settings


def make_task_engine() -> AsyncEngine:
    # `worker_db_url` (SEC-RLS-00B): `WORKER_DATABASE_URL` quando definida,
    # `DATABASE_URL` caso contrário. O worker é promovido a `aprimora_worker`
    # independentemente da API — se ele quebrar, a API não volta junto.
    return create_async_engine(get_settings().worker_db_url, poolclass=NullPool)


@asynccontextmanager
async def task_session_scope(
    tenant_id: int | None = None,
) -> AsyncIterator[tuple[AsyncEngine, Callable[[], AsyncSession]]]:
    """Gera (engine, SessionFactory) e garante `engine.dispose()` ao final.

    Se `tenant_id` for passado, cada sessão criada via `Session()` terá
    `session.info["tenant_id"]` setado — o listener global em `database.py`
    fará `SET LOCAL app.tenant_id` em cada BEGIN.
    """
    engine = make_task_engine()
    base_maker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    def session_factory() -> AsyncSession:
        s = base_maker()
        if tenant_id is not None:
            s.info["tenant_id"] = int(tenant_id)
        return s

    try:
        yield engine, session_factory
    finally:
        await engine.dispose()
