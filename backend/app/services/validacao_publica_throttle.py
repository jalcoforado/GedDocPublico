"""Rate-limit + dedup de auditoria da validação pública de assinatura (PR2e).

Defesa em profundidade no app (a borda dura é o `limit_req` do nginx):

- `esta_bloqueado_ip` / `registrar_consulta_ip`: limita consultas por IP numa
  janela curta. Fail-open (não bloqueia se o Redis cair) — a borda do nginx
  cobre o pior caso.
- `deve_auditar_negativa`: dedup das respostas neutras (token inexistente/
  revogado/sigiloso). Retorna True no máximo 1x por IP por janela, para a
  auditoria NÃO inundar sob enumeração. Fail-**closed** (False) se o Redis
  cair: sob abuso + Redis fora, preferimos não auditar a inundar o audit_log.

Reusa o Redis do Celery (mesma convenção de `assinatura_throttle`).
"""
from __future__ import annotations

import logging

from ..config import get_settings

logger = logging.getLogger("assinatura.validacao_publica")

# Limite de consultas por IP na janela (defesa em profundidade; nginx é a borda).
LIMITE_IP = 30
JANELA_IP_SEGUNDOS = 60
# Janela do dedup de auditoria das respostas neutras (no máx. 1 linha por IP).
JANELA_AUDIT_SEGUNDOS = 300


def _key_ip(ip: str) -> str:
    return f"validacao_publica:ip:{ip}"


def _key_audit(ip: str) -> str:
    return f"validacao_publica:audit_neg:{ip}"


def _client():
    import redis.asyncio as aioredis  # type: ignore[import-untyped]

    return aioredis.from_url(get_settings().celery_broker_url)


async def esta_bloqueado_ip(ip: str | None) -> bool:
    """True se o IP excedeu o limite na janela atual. Fail-open (False)."""
    if not ip:
        return False
    try:
        r = _client()
        try:
            valor = await r.get(_key_ip(ip))
        finally:
            await r.aclose()
        return valor is not None and int(valor) >= LIMITE_IP
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "validacao_publica_redis_indisponivel",
            extra={"op": "esta_bloqueado_ip", "erro": str(e)[:200]},
        )
        return False


async def registrar_consulta_ip(ip: str | None) -> int:
    """Incrementa o contador do IP (TTL da janela). Retorna o total (0 fail-open)."""
    if not ip:
        return 0
    try:
        r = _client()
        try:
            chave = _key_ip(ip)
            total = await r.incr(chave)
            if total == 1:
                await r.expire(chave, JANELA_IP_SEGUNDOS)
            return int(total)
        finally:
            await r.aclose()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "validacao_publica_redis_indisponivel",
            extra={"op": "registrar_consulta_ip", "erro": str(e)[:200]},
        )
        return 0


async def deve_auditar_negativa(ip: str | None) -> bool:
    """True só na 1ª resposta neutra do IP na janela — evita inundar o audit.
    Fail-**closed** (False) se o Redis cair."""
    if not ip:
        return False
    try:
        r = _client()
        try:
            # SET NX: define a flag só se ainda não existe → True 1x por janela.
            criou = await r.set(_key_audit(ip), "1", ex=JANELA_AUDIT_SEGUNDOS, nx=True)
        finally:
            await r.aclose()
        return bool(criou)
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "validacao_publica_redis_indisponivel",
            extra={"op": "deve_auditar_negativa", "erro": str(e)[:200]},
        )
        return False
