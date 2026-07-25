"""Bloqueios de saldo (Pagamentos v2.0 — RF-SLD-07). Valores administrativamente
bloqueados numa conta por período; reduzem o disponível projetado (ver
`pagamentos_caixa.bloqueado_conta`). CRUD tenant-scoped."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import BloqueioSaldo
from ..schemas.pagamentos import BloqueioSaldoCreate, BloqueioSaldoUpdate
from . import pagamentos_cadastros as cad


def _utcnow() -> datetime:
    return datetime.utcnow()


async def criar_bloqueio(db: AsyncSession, *, tenant_id: int, usuario_id: int,
                         payload: BloqueioSaldoCreate) -> BloqueioSaldo:
    # valida a conta (existência + tenant)
    await cad.obter_conta(db, tenant_id=tenant_id, conta_id=payload.id_conta)
    if payload.periodo_fim is not None and payload.periodo_fim < payload.periodo_inicio:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Período final anterior ao inicial.")
    b = BloqueioSaldo(
        tenant_id=tenant_id, id_conta=payload.id_conta, valor=payload.valor,
        motivo=payload.motivo, periodo_inicio=payload.periodo_inicio,
        periodo_fim=payload.periodo_fim, id_usuario_responsavel=usuario_id,
        ativo=True, criado_em=_utcnow())
    db.add(b); await db.commit(); await db.refresh(b)
    return b


async def obter_bloqueio(db: AsyncSession, *, tenant_id: int, bloqueio_id: int) -> BloqueioSaldo:
    b = (await db.execute(select(BloqueioSaldo).where(
        BloqueioSaldo.id == bloqueio_id, BloqueioSaldo.tenant_id == tenant_id,
        BloqueioSaldo.excluido.is_(False)))).scalar_one_or_none()
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bloqueio não encontrado")
    return b


async def listar_bloqueios(db: AsyncSession, *, tenant_id: int, conta_id: int | None = None,
                           apenas_ativos: bool = False) -> list[BloqueioSaldo]:
    stmt = select(BloqueioSaldo).where(
        BloqueioSaldo.tenant_id == tenant_id, BloqueioSaldo.excluido.is_(False))
    if conta_id is not None:
        stmt = stmt.where(BloqueioSaldo.id_conta == conta_id)
    if apenas_ativos:
        stmt = stmt.where(BloqueioSaldo.ativo.is_(True))
    return list((await db.execute(stmt.order_by(BloqueioSaldo.id.desc()))).scalars().all())


async def atualizar_bloqueio(db: AsyncSession, *, tenant_id: int, bloqueio_id: int,
                             payload: BloqueioSaldoUpdate) -> BloqueioSaldo:
    b = await obter_bloqueio(db, tenant_id=tenant_id, bloqueio_id=bloqueio_id)
    dados = payload.model_dump(exclude_unset=True)
    inicio = dados.get("periodo_inicio", b.periodo_inicio)
    fim = dados.get("periodo_fim", b.periodo_fim)
    if fim is not None and fim < inicio:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Período final anterior ao inicial.")
    for k, v in dados.items():
        setattr(b, k, v)
    b.atualizado_em = _utcnow(); await db.commit(); await db.refresh(b)
    return b


async def excluir_bloqueio(db: AsyncSession, *, tenant_id: int, bloqueio_id: int) -> None:
    b = await obter_bloqueio(db, tenant_id=tenant_id, bloqueio_id=bloqueio_id)
    b.excluido = True; b.ativo = False; b.atualizado_em = _utcnow()
    await db.commit()
