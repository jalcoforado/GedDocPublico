"""F6 (benchmark SUiTE) — cota de anexação por processo, por nível de sigilo.

Mostrar o orçamento ANTES de tentar anexar, em vez de recusar depois — a
resposta direta ao que a ata de benchmark registra sobre erro de tamanho de
arquivo sem aviso prévio.

Limite por SIGILO, não por tipo de processo nem por órgão — decisão do
Jorge em 2026-09-17: processo mais sigiloso tende a reunir mais documento
técnico anexado. Os valores em MB também são dessa decisão; não são
deriváveis do domínio, então mudam só aqui.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Anexo, AnexoProcesso

COTA_MB_POR_SIGILO: dict[str, int] = {
    "ostensivo": 200,
    "interno": 400,
    "reservado": 800,
    "secreto": 1200,
    "ultrassecreto": 2000,
}
_COTA_PADRAO_MB = COTA_MB_POR_SIGILO["ostensivo"]


def limite_bytes(nivel_sigilo: str) -> int:
    """Nível desconhecido (dado sujo, nunca deveria acontecer) cai no piso —
    conservador, na dúvida cobra o limite mais apertado, não o mais largo."""
    return COTA_MB_POR_SIGILO.get(nivel_sigilo, _COTA_PADRAO_MB) * 1024 * 1024


async def usado_bytes(db: AsyncSession, processo_id: int, tenant_id: int) -> int:
    """Soma `tamanho_bytes` dos anexos ativos e não desentranhados do processo.

    Anexo com `tamanho_bytes IS NULL` (upload anterior a esta fatia) não
    entra na soma — a cota fica otimista nesse caso, em vez de bloquear por
    um número que não temos.
    """
    total = (
        await db.execute(
            select(func.coalesce(func.sum(Anexo.tamanho_bytes), 0))
            .select_from(Anexo)
            .join(AnexoProcesso, AnexoProcesso.id_anexo == Anexo.id)
            .where(
                AnexoProcesso.id_processo == processo_id,
                AnexoProcesso.tenant_id == tenant_id,
                AnexoProcesso.excluido.is_(False),
                AnexoProcesso.desentranhado_em.is_(None),
                Anexo.excluido.is_(False),
                Anexo.ativo.is_(True),
            )
        )
    ).scalar_one()
    return int(total)
