"""Auditoria da fronteira de plataforma — decisão **D-a** de SEC-01A.

São **duas** trilhas, e nenhuma é redundância da outra:

1. `aprimora_py.platform_audit_log` — **autoritativa**. Quem operou
   (`platform_principal`), o que fez, sobre qual tenant, com que correlation
   ID. Fica fora da RLS municipal de propósito: o operador não pertence a
   tenant nenhum, e o `id_usuario` de `audit_log` é FK para `utils.usuario.id`,
   onde um `platform_principal.id` não cabe.
2. `aprimora_py.audit_log` — a entrada que o **município** enxerga. Gravada com
   `SET LOCAL app.tenant_id = <tenant ALVO>`, em transação própria,
   `id_usuario` nulo, como já era antes de SEC-01A. Remover esta linha tiraria
   da prefeitura o registro de que seu módulo foi contratado ou seu cadastro
   alterado — regressão de comportamento dentro de um PR de segurança.

**Este módulo não engole exceção.** `services/audit.py` faz `except Exception`
no flush (linhas ~68-70) e troca "operação falha" por "operação sem trilha";
isso é dívida conhecida, endereçada em `SEC-RLS-00B` por sequenciamento. Aqui
não: operação de plataforma sem trilha é pior do que operação recusada, e há
teste provando que a linha foi gravada de verdade.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database_plataforma import sessao_no_tenant_alvo
from ..models import PlatformAuditLog, PlatformPrincipal


async def registrar_operacao(
    db: AsyncSession,
    *,
    principal: PlatformPrincipal,
    acao: str,
    tenant_alvo_id: int | None = None,
    detalhe: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> int:
    """Grava a trilha autoritativa. **Não comita** — participa da transação da
    própria operação, para que rollback da operação leve a trilha junto.

    Sem `try/except`: se o flush falhar, a operação falha. É o comportamento
    desejado, ao contrário de `services/audit.py`.
    """
    linha = PlatformAuditLog(
        platform_principal_id=principal.id,
        issuer=principal.issuer,
        subject=principal.subject,
        acao=acao,
        tenant_alvo_id=tenant_alvo_id,
        detalhe=detalhe,
        correlation_id=correlation_id,
        criado_em=datetime.utcnow(),
    )
    db.add(linha)
    await db.flush()
    return linha.id


async def registrar_tentativa_negada(
    db: AsyncSession,
    *,
    issuer: str,
    subject: str,
    motivo: str,
    principal_id: int | None = None,
    correlation_id: str | None = None,
) -> None:
    """Trilha de acesso negado — `platform_principal_id` nulo quando não há
    principal.

    Comita em seguida, de propósito: quem chama levanta `403` logo depois, e uma
    trilha que some no unwind não serve ao runbook §2, que manda colher
    `(iss, sub)` justamente desta linha para cadastrar o primeiro operador.
    """
    db.add(
        PlatformAuditLog(
            platform_principal_id=principal_id,
            issuer=issuer,
            subject=subject,
            acao="plataforma.acesso_negado",
            tenant_alvo_id=None,
            detalhe={"motivo": motivo},
            correlation_id=correlation_id,
            criado_em=datetime.utcnow(),
        )
    )
    await db.commit()


async def registrar_no_tenant(
    *,
    tenant_alvo_id: int,
    acao: str,
    entidade: str,
    id_entidade: int | None,
    payload: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> None:
    """Entrada visível ao município, em `aprimora_py.audit_log`.

    Transação própria (`sessao_no_tenant_alvo`), com `SET LOCAL app.tenant_id`
    **explícito** no tenant ALVO — jamais o tenant que o `TenantMiddleware`
    resolveu a partir do `Host` de quem chamou. `id_usuario` fica nulo porque o
    operador de plataforma não é um `utils.usuario`, e a coluna é nullable
    exatamente para isso.

    INSERT em SQL cru em vez do ORM `AuditLog`: aqui a sessão é de outro engine
    e de outro papel, e o INSERT precisa acontecer sob o `SET LOCAL` desta
    transação. Passar pelo ORM só acrescentaria identity map e autoflush a um
    caminho que grava uma linha e fecha.
    """
    async with sessao_no_tenant_alvo(tenant_alvo_id) as sessao:
        await sessao.execute(
            text(
                """
                INSERT INTO aprimora_py.audit_log
                    (tenant_id, id_usuario, acao, entidade, id_entidade,
                     payload, request_id, ip, criado_em)
                VALUES
                    (:tenant_id, NULL, :acao, :entidade, :id_entidade,
                     CAST(:payload AS jsonb), :request_id, NULL, :criado_em)
                """
            ),
            {
                "tenant_id": tenant_alvo_id,
                "acao": acao,
                "entidade": entidade,
                "id_entidade": id_entidade,
                "payload": None if payload is None else json.dumps(payload),
                "request_id": correlation_id,
                "criado_em": datetime.utcnow(),
            },
        )
        await sessao.commit()
