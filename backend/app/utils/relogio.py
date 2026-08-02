"""Relógio único da fronteira de plataforma — SEC-01A.

Existe por um defeito que não dá erro em lugar nenhum quando acontece.

As colunas de vigência de `aprimora_py.platform_principal` são
`TIMESTAMP WITHOUT TIME ZONE`. Se o default do servidor gravasse `NOW()` (hora
LOCAL do Postgres) e o código gravasse UTC, a mesma coluna passaria a conter
dois relógios. Num host com fuso à frente de UTC, uma linha criada por SQL cru
nasceria com `valid_from` no futuro; `PlatformPrincipal.vigente_em()` devolveria
`False`; e o sintoma seria **um operador cadastrado que não consegue operar**,
sem exceção, sem log e sem nada para procurar. Em dev o Postgres está em UTC,
então isso nunca apareceria aqui — só no ambiente que importa.

A escolha, então, é explícita nos dois lados:

- no banco, `server_default = (NOW() AT TIME ZONE 'utc')` (migration 0076);
- no Python, `agora_utc()`.

**UTC ingênuo**, e não `datetime.now(UTC)` direto, porque a coluna não guarda
offset: entregar um datetime *aware* ao asyncpg para uma coluna sem timezone é
erro em tempo de execução. `.replace(tzinfo=None)` depois de converter para UTC
é o formato que a coluna aceita — e `datetime.utcnow()`, além de depreciado,
esconde essa decisão em vez de declará-la.
"""
from __future__ import annotations

from datetime import UTC, datetime


def agora_utc() -> datetime:
    """Instante atual em UTC, sem `tzinfo` — o formato de `TIMESTAMP` sem fuso."""
    return datetime.now(UTC).replace(tzinfo=None)
