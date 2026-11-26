"""Trilha de auditoria do módulo de pagamentos.

`GET /audit` (Administração) já lista o `audit_log` inteiro, mas exige a
transação `auditoria`, do módulo administração — o auditor de pagamentos
(`pagamento_auditar`) não a tem, e nem deveria ver o que é de outros módulos.

Esta rota é a mesma tabela com dois recortes fixos no servidor: só o tenant da
sessão e só as ações de pagamentos (`PREFIXOS`). O filtro de `acao` que vem do
cliente escolhe DENTRO desse conjunto; não há como pedir ação de fora dele.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import AuditLog, Usuario
from ..schemas.audit import AuditLogOut, AuditLogPage

router = APIRouter(prefix="/pagamentos", tags=["pagamentos-auditoria"])

# Prefixos de `audit_log.acao` gravados pelo módulo. Ação nova de pagamentos
# com outro prefixo precisa entrar aqui para aparecer na tela —
# `tests/test_pagamentos_auditoria_consulta.py` varre o código e reprova quem
# esquecer.
PREFIXOS = ("pagamento.", "debito.", "anexo_debito.", "excecao_cronologica.", "fornecedor.")


@router.get("/auditoria", response_model=AuditLogPage)
async def trilha_de_auditoria(
    _: Usuario = Depends(require_permission("pagamento_auditar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    acao: str | None = Query(None, max_length=80),
    id_usuario: int | None = Query(None),
    desde: datetime | None = Query(None),
    ate: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    filtros = [
        AuditLog.tenant_id == tenant_id,
        or_(*[AuditLog.acao.like(f"{p}%") for p in PREFIXOS]),
    ]
    if acao:
        # Igualdade, não prefixo: o cliente escolhe um ato da lista. Valor de
        # fora de `PREFIXOS` simplesmente não casa com o recorte acima.
        filtros.append(AuditLog.acao == acao)
    if id_usuario is not None:
        filtros.append(AuditLog.id_usuario == id_usuario)
    if desde:
        filtros.append(AuditLog.criado_em >= desde)
    if ate:
        filtros.append(AuditLog.criado_em <= ate)
    cond = and_(*filtros)

    total = (await db.execute(select(func.count(AuditLog.id)).where(cond))).scalar_one()
    rows = (await db.execute(
        select(AuditLog, Usuario.nome)
        .outerjoin(Usuario, and_(Usuario.id == AuditLog.id_usuario,
                                 Usuario.tenant_id == tenant_id))
        .where(cond)
        .order_by(AuditLog.criado_em.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).all()

    return AuditLogPage(
        items=[
            AuditLogOut(
                id=a.id, id_usuario=a.id_usuario, nome_usuario=nome, acao=a.acao,
                entidade=a.entidade, id_entidade=a.id_entidade, payload=a.payload,
                request_id=a.request_id, ip=a.ip, criado_em=a.criado_em)
            for a, nome in rows
        ],
        total=int(total), page=page, page_size=page_size)
