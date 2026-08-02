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

from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog


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
) -> int | None:
    """Cria entrada de auditoria. Não comita. Retorna o id criado — útil para
    vincular a entrada a outra entidade.

    **Levanta** se o flush falhar (SEC-RLS-00B). O tipo de retorno continua
    `int | None` porque o `None` do `row.id` só some depois do flush; na
    prática, ou volta um id ou a chamada levanta.
    """
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
    # Sem commit — caller controla.
    #
    # SEC-RLS-00B (inventário §8.7, plano item 8): este `flush` NÃO tem mais
    # `try/except`, e a remoção é a mudança.
    #
    # A versão anterior engolia a exceção "para não quebrar o fluxo principal".
    # O efeito real era trocar *operação falha* por *operação sem trilha*, com
    # o erro só no log — e como o `except` não fazia rollback, a sessão ficava
    # em estado inconsistente e o caller quebrava adiante, longe da causa.
    # Enquanto o runtime tinha BYPASSRLS isso quase nunca disparava. Sem
    # bypass, `new row violates row-level security policy` passa a ser o modo
    # de falha PADRÃO de qualquer rota que audite com o tenant errado na
    # sessão: exatamente o caso em que concluir a operação calado é o pior
    # resultado possível.
    #
    # A mudança vem AQUI e não antes de propósito: só faz sentido falhar alto
    # depois que todos os caminhos de auditoria estiverem provadamente
    # corretos — a trilha de plataforma ganhou sessão e papel próprios em
    # `SEC-01A` (`services/plataforma_auditoria.py`, migration 0077), e o
    # arreio de teste que escondia o tenant errado foi corrigido no começo
    # deste PR. Feito antes disso, o resultado seria 500 em massa.
    #
    # A propriedade que passa a valer: **ou a ação e a trilha acontecem, ou
    # nenhuma das duas.** É o que o docstring do módulo já prometia.
    await db.flush()  # gera id pro caso de o caller querer logar referência
    return row.id
