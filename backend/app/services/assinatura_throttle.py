"""Throttle de tentativas malsucedidas de assinatura (PR2a).

Limite: 5 falhas por janela de 15 min, escopo (tenant_id, usuario_id, anexo).
Após exceder, bloqueia novas tentativas por 15 min.

Usa Redis (já é dependência do projeto — broker/result do Celery). É
**fail-open**: se o Redis estiver indisponível, NÃO bloqueia uma assinatura
legítima — apenas registra um warning técnico no log estruturado (não no
audit_log probatório). O rate-limit de borda (nginx) é a camada complementar.
"""
from __future__ import annotations

import logging

from ..config import get_settings

logger = logging.getLogger("assinatura.throttle")

LIMITE = 5
JANELA_SEGUNDOS = 15 * 60


def _key(tenant_id: int, usuario_id: int, anexo_id: int) -> str:
    return f"assinatura:falha:{tenant_id}:{usuario_id}:{anexo_id}"


def _client():
    # Import lazy — não paga custo no boot e permite fail-open se faltar libdep.
    import redis.asyncio as aioredis  # type: ignore[import-untyped]

    return aioredis.from_url(get_settings().celery_broker_url)


async def esta_bloqueado(tenant_id: int, usuario_id: int, anexo_id: int) -> bool:
    """True se já atingiu o limite na janela atual. Fail-open (False) se Redis cair."""
    try:
        r = _client()
        try:
            valor = await r.get(_key(tenant_id, usuario_id, anexo_id))
        finally:
            await r.aclose()
        return valor is not None and int(valor) >= LIMITE
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "throttle_redis_indisponivel",
            extra={"op": "esta_bloqueado", "erro": str(e)[:200]},
        )
        return False


async def registrar_falha(tenant_id: int, usuario_id: int, anexo_id: int) -> int:
    """Incrementa o contador da janela (TTL 15 min). Retorna o total atual
    (0 em fail-open)."""
    try:
        r = _client()
        try:
            chave = _key(tenant_id, usuario_id, anexo_id)
            total = await r.incr(chave)
            if total == 1:
                await r.expire(chave, JANELA_SEGUNDOS)
            return int(total)
        finally:
            await r.aclose()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "throttle_redis_indisponivel",
            extra={"op": "registrar_falha", "erro": str(e)[:200]},
        )
        return 0


async def limpar(tenant_id: int, usuario_id: int, anexo_id: int) -> None:
    """Zera o contador (após sucesso). Best-effort."""
    try:
        r = _client()
        try:
            await r.delete(_key(tenant_id, usuario_id, anexo_id))
        finally:
            await r.aclose()
    except Exception:  # noqa: BLE001
        pass
