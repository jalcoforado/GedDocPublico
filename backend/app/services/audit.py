"""Service de auditoria — Fase 24.

Função `log()` insere uma linha em `aprimora_py.audit_log`. Quem chama
deve estar dentro de uma session com `tenant_id` setado no `session.info`
(o listener global de `database.py` cuida do `SET LOCAL app.tenant_id`).

`log()` NÃO faz commit — assume que o caller controla a transação. Isso
permite que a auditoria participe da mesma transação da ação (atômica).
Se o caller fizer rollback, a auditoria também volta — propriedade
desejável.

Convenção de `acao`:
  <entidade>.<verbo>      ex: processo.encaminhado, processo.arquivado,
                              workflow_instance.transicionada,
                              usuario.criado
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog

logger = logging.getLogger("audit")


async def log(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_usuario: int | None,
    acao: str,
    entidade: str,
    id_entidade: int | None,
    payload: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    """Cria entrada de auditoria. Não comita."""
    request_id = None
    ip = None
    if request is not None:
        request_id = getattr(request.state, "request_id", None)
        # X-Forwarded-For (nginx) > client direto
        forwarded = request.headers.get("x-forwarded-for", "")
        ip = forwarded.split(",")[0].strip() if forwarded else (
            request.client.host if request.client else None
        )

    row = AuditLog(
        tenant_id=tenant_id,
        id_usuario=id_usuario,
        acao=acao,
        entidade=entidade,
        id_entidade=id_entidade,
        payload=payload,
        request_id=request_id,
        ip=ip,
        criado_em=datetime.utcnow(),
    )
    db.add(row)
    # Sem commit — caller controla
    try:
        await db.flush()  # gera id pro caso de o caller querer logar referência
    except Exception:  # noqa: BLE001
        # Auditoria não deve quebrar o fluxo principal. Se o flush falhar
        # (FK, etc), loga e segue.
        logger.exception(
            "audit_log_falhou",
            extra={
                "tenant_id": tenant_id,
                "acao": acao,
                "entidade": entidade,
                "id_entidade": id_entidade,
            },
        )
