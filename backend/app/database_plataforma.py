"""Conexão dedicada da fronteira de plataforma — SEC-01A / ADR-016 §2.3.

Por que não reusar `database.py`:

O engine municipal é aberto com `DATABASE_URL`, hoje o papel `ged_user`
(SUPERUSER, BYPASSRLS — achado F-12), e `get_db` instala na sessão o
`tenant_id` que o `TenantMiddleware` resolveu a partir do header `Host`. As duas
coisas são erradas numa operação cross-tenant: o papel porque contorna toda a
RLS, e o `tenant_id` porque o alvo de uma operação de plataforma vem da
**operação**, nunca do host de quem chamou.

Aqui o engine é aberto com `PLATFORM_DB_URL`, o papel `aprimora_platform`
(`NOBYPASSRLS`, grants cross-tenant enumerados tabela a tabela na migration
0076), e a sessão **nunca** recebe `session.info["tenant_id"]` — o listener
`after_begin` de `database.py` só age quando essa chave existe, então nenhuma
transação de plataforma nasce com `app.tenant_id` herdado.

A única exceção é deliberada e explícita: `sessao_no_tenant_alvo()`, que aplica
`SET LOCAL app.tenant_id = <alvo>` para gravar a entrada de auditoria que o
**município** enxerga (decisão D-a). Ali o tenant é argumento da função, não
herança de middleware.

Configuração ausente ⇒ **500**, nunca fallback para o pool municipal (matriz de
claims §3, linha "Papel de banco"). Cair no pool municipal seria trocar uma
indisponibilidade por um contorno silencioso da fronteira inteira.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings

logger = logging.getLogger("plataforma")

# Engines por URL. A chave é a URL — e não um singleton — porque o teste troca
# `PLATFORM_DB_URL` por `monkeypatch.setenv` + `get_settings.cache_clear()`, e um
# singleton devolveria o engine da configuração anterior. É a mesma armadilha de
# `auth/jwt.py:23` (`_settings = get_settings()` no import), que já produziu
# falso verde neste repositório: configuração se lê POR CHAMADA.
_engines: dict[str, AsyncEngine] = {}


class PlataformaSemBancoError(HTTPException):
    """`PLATFORM_DB_URL` ausente. Erro de configuração, não de credencial."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Fronteira de plataforma sem conexão dedicada: defina "
                "PLATFORM_DB_URL com o papel aprimora_platform. Ver "
                "docs/runbooks/platform-operator-bootstrap.md §1."
            ),
        )


def obter_engine_plataforma() -> AsyncEngine:
    """Engine do papel `aprimora_platform`. Levanta 500 se não configurado."""
    url = get_settings().platform_db_url.strip()
    if not url:
        logger.error(
            "plataforma_sem_platform_db_url",
            extra={"detalhe": "PLATFORM_DB_URL ausente; fronteira de plataforma negando"},
        )
        raise PlataformaSemBancoError()
    engine = _engines.get(url)
    if engine is None:
        # Pool pequeno de propósito: a fronteira de plataforma é operada por
        # um punhado de pessoas, não pelo tráfego do município.
        engine = create_async_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
        _engines[url] = engine
    return engine


async def descartar_engines_plataforma() -> None:
    """Fecha os engines abertos. Usado por teardown de teste."""
    for engine in list(_engines.values()):
        await engine.dispose()
    _engines.clear()


def _sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        obter_engine_plataforma(), expire_on_commit=False, class_=AsyncSession
    )


async def get_platform_db() -> AsyncIterator[AsyncSession | None]:
    """Dependência FastAPI das rotas de plataforma. Substitui `get_db` nelas.

    NÃO grava `tenant_id` em `session.info` — de propósito. Rota de plataforma
    que precisar de um tenant o recebe explicitamente da operação.

    **Devolve `None` em vez de levantar** quando `PLATFORM_DB_URL` está ausente,
    e isso é decisão de desenho, não descuido. O FastAPI resolve as
    dependências de uma rota na ordem em que aparecem na assinatura; se esta
    levantasse, uma requisição **sem token nenhum** poderia receber `500` em vez
    de `401` — e a resposta passaria a depender da ordem dos parâmetros, que é
    exatamente o tipo de acoplamento que ninguém percebe ao refatorar. Quem
    converte o `None` em `500` é `require_platform_admin`, **depois** de validar
    o token (matriz §3, linha "Papel de banco").

    Consequência para quem lê as rotas: elas anotam `AsyncSession`, não
    `AsyncSession | None`, porque só executam depois do gate — e o gate não
    deixa passar com `None`.
    """
    if not get_settings().platform_db_url.strip():
        logger.error(
            "plataforma_sem_platform_db_url",
            extra={"detalhe": "PLATFORM_DB_URL ausente; fronteira de plataforma negando"},
        )
        yield None
        return
    async with _sessionmaker()() as session:
        yield session


@asynccontextmanager
async def sessao_plataforma() -> AsyncIterator[AsyncSession]:
    """Sessão de plataforma fora do ciclo de request (CLI, auditoria fora de
    banda). Mesmo papel, mesma ausência de `app.tenant_id`."""
    async with _sessionmaker()() as session:
        yield session


@asynccontextmanager
async def sessao_no_tenant_alvo(tenant_id: int) -> AsyncIterator[AsyncSession]:
    """Sessão de plataforma com `SET LOCAL app.tenant_id = <tenant ALVO>`.

    Existe para UM caso: gravar em `aprimora_py.audit_log` a entrada que o
    município enxerga (decisão D-a). Essa tabela tem RLS FORCE com
    `WITH CHECK (tenant_id = current_setting('app.tenant_id'))`, e o papel
    `aprimora_platform` é `NOBYPASSRLS` — sem o `SET LOCAL` a policy nega o
    INSERT.

    O `SET LOCAL` é explícito e o tenant é **argumento**, jamais herdado do
    middleware. Hoje ele seria dispensável no runtime municipal, que ainda roda
    com bypass (F-12); é justamente por isso que precisa estar correto **antes**
    de `SEC-RLS-00B` remover o bypass.
    """
    async with _sessionmaker()() as session:
        # `SET LOCAL` vale pela transação; abrir explicitamente garante que o
        # BEGIN aconteceu antes do setting (senão o `SET LOCAL` se perde).
        await session.begin()
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(int(tenant_id))},
        )
        yield session
