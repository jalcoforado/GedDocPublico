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
# SEC-01A — papel da fronteira de plataforma (migration 0076). NOBYPASSRLS,
# grants cross-tenant explícitos e enumerados (ADR-016 §2.3).
PLATFORM_URL = f"postgresql+asyncpg://aprimora_platform:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


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
async def platform_session() -> AsyncIterator[AsyncSession]:
    """Session como ``aprimora_platform`` (SEC-01A, migration 0076).

    É o papel da fronteira de plataforma: ``NOBYPASSRLS``, com grants
    cross-tenant **explícitos e enumerados** (ADR-016 §2.3) — entitlement e
    identidade de plataforma, nada de tabela de negócio de tenant.

    Serve de **controle positivo** para os testes de grant: sem provar que este
    papel escreve em ``platform_principal``, o "permission denied" de
    ``aprimora_app`` provaria apenas que a tabela está quebrada.
    """
    engine = create_async_engine(PLATFORM_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# SEC-01A — arreio da fronteira de plataforma
#
# Um teste da fronteira precisa de quatro coisas ao mesmo tempo: identificadores
# de realm configurados, um JWKS que resolva sem rede, uma conexão pelo papel
# `aprimora_platform` e um principal no banco. Montar isso em cada arquivo
# produziria quatro cópias divergentes — e a que esquecesse o
# `get_settings.cache_clear()` viraria falso verde silencioso, porque o
# `lru_cache` devolveria a configuração de antes do `monkeypatch`.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def emissor_operador():
    """`OperatorTokenFactory` com par RSA efêmero (fixtures de SEC-00)."""
    from tests.fixtures.platform_operator_tokens import OperatorTokenFactory

    return OperatorTokenFactory()


@pytest_asyncio.fixture(scope="function")
async def plataforma_configurada(monkeypatch, emissor_operador):
    """Configura a fronteira de plataforma e serve o JWKS em memória.

    O JWKS é injetado substituindo `app.auth.plataforma._buscar_jwks`: teste que
    fosse buscar o JWKS de verdade dependeria de rede e do IdP estar de pé.

    Devolve o emissor de tokens já casado com a configuração aplicada.
    """
    from tests.fixtures.platform_operator_tokens import (
        TEST_AUDIENCE,
        TEST_HOSTED_DOMAIN,
        TEST_ISSUER,
    )

    from app import database_plataforma
    from app.auth import plataforma as validador
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("PLATFORM_OIDC_ISSUER", TEST_ISSUER)
    monkeypatch.setenv("PLATFORM_OIDC_AUDIENCE", TEST_AUDIENCE)
    monkeypatch.setenv("PLATFORM_OIDC_JWKS_URL", "https://operator.test.local/jwks")
    monkeypatch.setenv("PLATFORM_OIDC_HOSTED_DOMAIN", TEST_HOSTED_DOMAIN)
    monkeypatch.setenv("PLATFORM_DB_URL", PLATFORM_URL)
    get_settings.cache_clear()

    async def _jwks_em_memoria(url: str):
        return emissor_operador.keys.jwks, 600

    monkeypatch.setattr(validador, "_buscar_jwks", _jwks_em_memoria)
    validador.limpar_cache_jwks()

    yield emissor_operador

    validador.limpar_cache_jwks()
    await database_plataforma.descartar_engines_plataforma()
    get_settings.cache_clear()


@pytest_asyncio.fixture(scope="function")
async def principal_ativo(admin_engine, plataforma_configurada):
    """Cria um `platform_principal` ativo e devolve `(subject, id)`.

    Setup/teardown por `ged_user` (o padrão de `admin_session`): o que se testa
    aqui é a fronteira HTTP, não o grant — esse já tem teste próprio em
    `test_platform_admin_identity.py`.
    """
    from tests.fixtures.platform_operator_tokens import TEST_ISSUER

    subject = f"sec01a-operador-{uuid.uuid4().hex[:8]}"
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        principal_id = int(
            (
                await s.execute(
                    text(
                        """
                        INSERT INTO aprimora_py.platform_principal
                            (issuer, subject, display_label, ativo,
                             concedido_por, motivo_concessao)
                        VALUES (:iss, :sub, :label, true, 'teste', 'arreio de teste')
                        RETURNING id
                        """
                    ),
                    {
                        "iss": TEST_ISSUER,
                        "sub": subject,
                        "label": "operador@test.local",
                    },
                )
            ).scalar_one()
        )
        await s.commit()

    yield subject, principal_id

    async with Session() as s:
        await s.execute(
            text("DELETE FROM aprimora_py.platform_audit_log WHERE platform_principal_id = :p"),
            {"p": principal_id},
        )
        await s.execute(
            text("DELETE FROM aprimora_py.platform_principal WHERE id = :p"),
            {"p": principal_id},
        )
        await s.commit()


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
        # Sem lock_timeout, um teste que falhou segurando transação aberta faz
        # este DELETE esperar PARA SEMPRE, e a suíte inteira pendura — o job do
        # CI morre por timeout sem nunca dizer qual teste falhou. Aconteceu em
        # 2026-07-30: dois runs mortos, em tetos de 15 e de 30 min, e o
        # diagnóstico só saiu de `pg_stat_activity` (uma sessão
        # `idle in transaction` contra um DELETE em `wait_event_type = Lock`).
        # Com o timeout, o teardown falha em 15s dizendo o que houve.
        await teardown_session.execute(text("SET lock_timeout = '15s'"))
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

    # Host parametrizável, como PYTEST_DB_HOST: no compose o serviço se chama
    # `redis`; fora dele (CI) o service container responde em localhost.
    redis_url = os.environ.get("PYTEST_REDIS_URL", "redis://redis:6379/2")
    client = aioredis.from_url(redis_url)
    yield client
    # Cleanup: flush DB de teste
    await client.flushdb()
    await client.aclose()
