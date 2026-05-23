"""Sessão SQLAlchemy isolada para uso DENTRO de tasks Celery.

Por que: o engine global do FastAPI tem conexões asyncpg amarradas à event loop
original. Cada `asyncio.run()` cria uma loop nova; reusar essas conexões dispara
RuntimeError "Future attached to a different loop".

Solução: cada task cria um engine novo (NullPool → nenhuma conexão é reaproveitada)
e o descarta no fim. Não compartilhar este engine entre tasks distintas.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from ..config import get_settings


def make_task_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, poolclass=NullPool)


@asynccontextmanager
async def task_session_scope() -> AsyncIterator[
    tuple[AsyncEngine, async_sessionmaker[AsyncSession]]
]:
    """Gera (engine, Session) e garante `engine.dispose()` ao final."""
    engine = make_task_engine()
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield engine, Session
    finally:
        await engine.dispose()
