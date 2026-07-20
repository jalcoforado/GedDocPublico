"""Fixtures compartilhadas para pytest.

Dois engines distintos:
- ``admin_session`` → role ``ged_user`` (SUPERUSER, BYPASSRLS). Usado para
  fixtures/setup/teardown que precisam contornar policies.
- ``app_session`` → role ``aprimora_app`` (NOBYPASSRLS). Usado nos testes
  que validam RLS — sem isso, ``ged_user`` ignoraria as policies e os
  testes passariam incorretamente.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


DB_HOST = os.environ.get("PYTEST_DB_HOST", "ged-saas-project-db-1")
DB_PORT = os.environ.get("PYTEST_DB_PORT", "5432")
DB_NAME = os.environ.get("PYTEST_DB_NAME", "ged_saas_db")
DB_PASS = os.environ.get("PYTEST_DB_PASS", "ged_password_secure_local")

ADMIN_URL = f"postgresql+asyncpg://ged_user:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
APP_URL = f"postgresql+asyncpg://aprimora_app:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


@pytest_asyncio.fixture(scope="function")
async def admin_engine():
    """Engine ged_user (BYPASSRLS) — descartado ao fim do teste."""
    engine = create_async_engine(ADMIN_URL)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def admin_session(admin_engine) -> AsyncIterator[AsyncSession]:
    """Session como ged_user (BYPASSRLS) — só pra setup/teardown."""
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def app_session() -> AsyncIterator[AsyncSession]:
    """Session como aprimora_app (NOBYPASSRLS) — testa RLS de verdade.

    O teste é responsável por chamar ``SET LOCAL app.tenant_id = '<id>'``
    em cada transação. Sem isso, policies USING/WITH CHECK avaliam null
    e nenhuma linha é visível/inserível.
    """
    engine = create_async_engine(APP_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def two_tenants(admin_engine) -> AsyncIterator[tuple[int, int]]:
    """Cria 2 tenants temporários, retorna ``(id_a, id_b)``, limpa no teardown.

    Slugs únicos por execução pra suportar testes paralelos. Setup e teardown
    usam **sessions independentes** — a session do teardown não compartilha
    snapshot REPEATABLE READ com inserts feitos via ``app_session`` durante
    o teste, então enxerga as linhas e consegue limpar.
    """
    suffix = uuid.uuid4().hex[:8]
    slug_a = f"test-rls-a-{suffix}"
    slug_b = f"test-rls-b-{suffix}"
    now = datetime.now()

    Setup = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Setup() as setup_session:
        res_a = await setup_session.execute(
            text(
                "INSERT INTO aprimora_py.tenant (slug, nome, ativo, plano, criado_em) "
                "VALUES (:slug, :nome, true, 'basico', :now) RETURNING id"
            ),
            {"slug": slug_a, "nome": f"Test A {suffix}", "now": now},
        )
        tid_a = int(res_a.scalar_one())
        res_b = await setup_session.execute(
            text(
                "INSERT INTO aprimora_py.tenant (slug, nome, ativo, plano, criado_em) "
                "VALUES (:slug, :nome, true, 'basico', :now) RETURNING id"
            ),
            {"slug": slug_b, "nome": f"Test B {suffix}", "now": now},
        )
        tid_b = int(res_b.scalar_one())
        await setup_session.commit()

    yield (tid_a, tid_b)

    # Teardown em session NOVA — vê dados commitados pelo teste mesmo se
    # rodou via app_session. Tabelas que os testes podem ter populado.
    cleanup_tables = [
        "protocolos.tipo_anexo",
        "protocolos.tipo_manifestante",
        "protocolos.manifestante",
        "protocolos.processo",
        "aprimora_py.nup_sequencia",
        "protocolos.ttd_regra",
        "protocolos.ccd_classe",
        "protocolos.assunto",
        "protocolos.tipo_processo",
    ]
    Teardown = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Teardown() as teardown_session:
        for table in cleanup_tables:
            await teardown_session.execute(
                text(f"DELETE FROM {table} WHERE tenant_id IN (:a, :b)"),
                {"a": tid_a, "b": tid_b},
            )
        await teardown_session.execute(
            text("DELETE FROM aprimora_py.tenant WHERE id IN (:a, :b)"),
            {"a": tid_a, "b": tid_b},
        )
        await teardown_session.commit()


@pytest_asyncio.fixture(scope="function")
async def redis_client():
    """Redis client para testes — usa redis de teste (DB 2)."""
    import redis.asyncio as aioredis

    redis_url = "redis://redis:6379/2"
    client = aioredis.from_url(redis_url)
    yield client
    # Cleanup: flush DB de teste
    await client.flushdb()
    await client.aclose()
