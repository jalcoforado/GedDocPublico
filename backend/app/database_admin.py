"""Conexão das operações ADMINISTRATIVAS — seeds, backup, restore.

Por que não reusar `app.database.SessionLocal` (SEC-RLS-00B, inventário §8.2,
§8.6 e §10 itens 6 e 8):

- `seed_bootstrap` **escreve** em `aprimora_py.modulo` e `modulo_transacao`, o
  catálogo global do produto, onde `aprimora_app` só tem `SELECT`;
- `seed_demo reset` **apaga** as linhas de `aprimora_py.audit_log` dos processos
  de demonstração, e a 0076 tornou a trilha append-only para o papel municipal;
- o `backup` lê tabela de todos os cantos e precisa de contexto de tenant
  explícito.

Nada disso é operação de runtime. Rodá-las com a credencial da API só funciona
hoje porque a credencial da API pode tudo — que é o achado **F-12**.

O papel alvo é `aprimora_migrator` (migration 0078), `NOSUPERUSER` e
`NOBYPASSRLS`: ele **continua sujeito à RLS**. Sessão administrativa que toque
tabela tenanted precisa instalar `app.tenant_id` do mesmo jeito que a API — o
que muda é o conjunto de grants, não a existência da barreira.

Enquanto `MIGRATOR_DATABASE_URL` estiver vazia, `admin_database_url` cai em
`DATABASE_URL` e este módulo abre exatamente a mesma conexão de antes.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Importar `database` registra o listener `after_begin` que emite o
# `SET LOCAL app.tenant_id` a partir de `session.info["tenant_id"]`. Sem este
# import, uma sessão administrativa com `info["tenant_id"]` setado NÃO instalaria
# a GUC, e a falha seria silenciosa: zero linhas, sem erro.
from . import database as _registra_listener  # noqa: F401
from .config import get_settings

_engine = None
_SessionMaker = None


def _garantir_engine():
    """Engine preguiçoso e memoizado.

    Preguiçoso porque um engine criado no import abriria pool em todo processo
    que importa o módulo — inclusive a API, que jamais deve usar esta conexão.
    `NullPool` porque os CLIs são de vida curta e frequentemente rodam sob
    `asyncio.run()` próprio.
    """
    global _engine, _SessionMaker
    if _engine is None:
        _engine = create_async_engine(
            get_settings().admin_database_url, poolclass=NullPool
        )
        _SessionMaker = async_sessionmaker(
            _engine, expire_on_commit=False, class_=AsyncSession
        )
    return _SessionMaker


def AdminSessionLocal(tenant_id: int | None = None) -> AsyncSession:
    """Sessão administrativa. Com `tenant_id`, instala a GUC de RLS.

    Assinatura deliberadamente igual à de `SessionLocal()` para que a troca nos
    CLIs seja de uma linha — com o parâmetro extra que torna o contexto de
    tenant **visível na chamada** em vez de implícito.
    """
    maker = _garantir_engine()
    sessao = maker()
    if tenant_id is not None:
        sessao.info["tenant_id"] = int(tenant_id)
    return sessao


@asynccontextmanager
async def admin_session(tenant_id: int | None = None) -> AsyncIterator[AsyncSession]:
    async with AdminSessionLocal(tenant_id) as sessao:
        yield sessao


async def descartar_engine_admin() -> None:
    """Descarta o engine memoizado. Usado pelos testes entre event loops."""
    global _engine, _SessionMaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _SessionMaker = None
