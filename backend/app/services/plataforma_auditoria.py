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
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database_plataforma import sessao_no_tenant_alvo
from ..models.plataforma import PlatformAuditLog, PlatformPrincipal
from ..utils.relogio import agora_utc


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
        criado_em=agora_utc(),
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
            criado_em=agora_utc(),
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

    **Isto reimplementa `services/audit.py::log`, e a duplicação é consciente.**
    O efeito colateral é real — `aprimora_py.audit_log` passa a ter dois
    escritores independentes —, então o motivo tem de ser bom o bastante para
    quem vier depois julgar se ainda vale:

    1. `audit.py::log` **engole a exceção do flush** (`except Exception` nas
       linhas ~68-70). Chamá-lo aqui importaria exatamente o silêncio que a
       decisão D-a existe para evitar, e a falha de projeção deixaria de ser
       detectável — ver `registrar_falha_de_projecao`.
    2. Ele monta um `AuditLog` do ORM, cuja `Session` teria de ser esta, de
       outro engine e outro papel. O objeto entraria no identity map e ficaria
       sujeito a autoflush em qualquer `execute` posterior desta transação —
       comportamento que não se quer num caminho que grava uma linha e fecha.

    O que NÃO é motivo, embora pareça: "é outra sessão, outro papel". Isso
    sozinho não impede reusar `log()`; ele recebe a sessão por parâmetro.

    Se algum dia `audit.py::log` parar de engolir a exceção (item de
    `SEC-RLS-00B`), reunificar os dois passa a ser a coisa certa.
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
                "criado_em": agora_utc(),
            },
        )
        await sessao.commit()


async def registrar_falha_de_projecao(
    db: AsyncSession,
    *,
    principal: PlatformPrincipal,
    tenant_alvo_id: int,
    acao: str,
    erro: str,
    correlation_id: str | None = None,
) -> None:
    """Grava, na trilha AUTORITATIVA, que a projeção municipal falhou.

    Chamado quando `registrar_no_tenant` estoura **depois** de a operação já
    ter comitado. Nesse ponto propagar a exceção não protege nada: a alteração
    está feita, e um `500` sobre operação bem-sucedida mente sobre o resultado
    e convida o operador a repetir.

    A diferença para o `except Exception` de `services/audit.py`, que este PR
    critica, é qual trilha se perde. Lá, a engolida é a **única** — a operação
    fica sem rastro nenhum. Aqui a autoritativa já participou da transação e
    está gravada; o que falhou é uma **projeção secundária**, e a própria falha
    vira uma linha auditável, com o `correlation_id` que casa as duas pontas.
    Silêncio seria engolir; isto é registrar.

    **Não use isto como precedente para capturar o que não pode falhar.** O
    critério é estreito: só vale depois do commit, e só quando existe outra
    trilha, íntegra, dizendo o que aconteceu.

    Comita em transação própria — a da operação já fechou.
    """
    db.add(
        PlatformAuditLog(
            platform_principal_id=principal.id,
            issuer=principal.issuer,
            subject=principal.subject,
            acao="plataforma.projecao_municipal_falhou",
            tenant_alvo_id=tenant_alvo_id,
            detalhe={"acao_original": acao, "erro": erro},
            correlation_id=correlation_id,
            criado_em=agora_utc(),
        )
    )
    await db.commit()
