from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session as _SyncSession
from sqlalchemy.sql import Select

from .config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# Event listener: sempre que uma transação começa numa Session que carrega
# `session.info["tenant_id"]`, faz `SET LOCAL app.tenant_id` na conexão para o
# Postgres avaliar as policies de RLS (Fase 13b). SET LOCAL é por transação,
# então precisa ser reaplicado em cada BEGIN — daí o listener em vez de uma
# chamada única no get_db().
#
# Registrado na classe sync Session base (AsyncSession encapsula uma Session
# síncrona); o callback dispara em ambas. Sessões sem `tenant_id` em info
# (ex.: Alembic) simplesmente passam sem alterar o setting.
@event.listens_for(_SyncSession, "after_begin")
def _set_tenant_on_begin(session, transaction, connection):
    tid = session.info.get("tenant_id")
    if tid is None:
        return
    connection.exec_driver_sql(f"SET LOCAL app.tenant_id = '{int(tid)}'")


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        tid = getattr(request.state, "tenant_id", None)
        if tid is not None:
            session.info["tenant_id"] = int(tid)
        yield session


def tenant_filter(stmt: Select, model: Any, tenant_id: int | None) -> Select:
    """Adiciona `WHERE model.tenant_id = tenant_id` ao SELECT.

    Defesa aplicacional contra esquecer o filtro de tenant em queries.
    Quando `tenant_id is None`, é interpretado como "catálogo global" — passa
    sem filtrar, mas o modelo NÃO pode ter coluna `tenant_id` (senão é bug).

    Regras:
    - Modelo COM `tenant_id` + `tenant_id is None` → ValueError (esqueceu filtro).
    - Modelo COM `tenant_id` + tenant_id int → adiciona WHERE.
    - Modelo SEM `tenant_id` + `tenant_id is None` → ok, retorna stmt original.
    - Modelo SEM `tenant_id` + tenant_id int → ValueError (modelo errado).
    """
    has_col = hasattr(model, "tenant_id")
    if has_col and tenant_id is None:
        raise ValueError(
            f"{model.__name__} tem tenant_id mas chamada usou tenant_id=None. "
            "Passe o tenant_id (require_tenant_id) ou explicite por que é global."
        )
    if not has_col and tenant_id is not None:
        raise ValueError(
            f"{model.__name__} NÃO tem tenant_id mas chamada passou tenant_id={tenant_id}. "
            "Catálogo global deve ser chamado com tenant_id=None."
        )
    if tenant_id is None:
        return stmt
    return stmt.where(model.tenant_id == tenant_id)
