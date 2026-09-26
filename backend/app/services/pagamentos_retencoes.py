"""Retenções tributárias sobre um débito (F4, spec §4.3). CRUD tenant-scoped,
travado enquanto a parcela do débito estiver "engajada" num lote — PENDENTE
(lote em RASCUNHO/PROGRAMADO/ENVIADO) ou já PAGA (lote PROCESSADO): mudar o
líquido de dinheiro em trânsito ou já pago não faz sentido. A checagem usa o
mesmo critério do UNIQUE parcial de `lote_pagamento_parcela`
(`situacao <> 'FALHOU'`) — uma linha FALHOU não bloqueia (a parcela voltou a
`LIBERADA`, livre para um lote novo, e a retenção pode ser corrigida antes
dele).

`valor_liquido` é sempre DERIVADO — nunca uma coluna (spec §4.3, ruling 6 do
plano da F4)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Debito, LotePagamentoParcela, Parcela, Retencao
from ..schemas.pagamentos import RetencaoCreate, RetencaoUpdate


def _utcnow() -> datetime:
    return datetime.utcnow()


def valor_liquido(valor_total: Decimal, retencoes: list[Retencao]) -> Decimal:
    """Função pura (ruling 6): bruto menos a soma das retenções não excluídas."""
    return valor_total - sum((r.valor for r in retencoes), Decimal("0"))


async def _obter_debito(db: AsyncSession, *, tenant_id: int, debito_id: int) -> Debito:
    d = (await db.execute(select(Debito).where(
        Debito.id == debito_id, Debito.tenant_id == tenant_id,
        Debito.excluido.is_(False)))).scalar_one_or_none()
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Débito não encontrado")
    return d


async def _assert_debito_fora_de_lote_ativo(db: AsyncSession, *, tenant_id: int,
                                            debito_id: int) -> None:
    engajada = (await db.execute(
        select(LotePagamentoParcela.id)
        .join(Parcela, Parcela.id == LotePagamentoParcela.id_parcela)
        .where(
            Parcela.id_debito == debito_id,
            LotePagamentoParcela.tenant_id == tenant_id,
            LotePagamentoParcela.situacao != "FALHOU",
        ).limit(1)
    )).scalar_one_or_none()
    if engajada is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Débito tem parcela em lote de pagamento (pendente ou já paga) — "
            "retenção travada.",
        )


async def listar_retencoes_debito(db: AsyncSession, *, tenant_id: int,
                                  debito_id: int) -> list[Retencao]:
    await _obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    stmt = select(Retencao).where(
        Retencao.tenant_id == tenant_id, Retencao.id_debito == debito_id,
        Retencao.excluido.is_(False),
    ).order_by(Retencao.id)
    return list((await db.execute(stmt)).scalars().all())


async def resumo_retencoes(db: AsyncSession, *, tenant_id: int,
                           debito_id: int) -> tuple[Decimal, Decimal, list[Retencao]]:
    """(valor_bruto, valor_liquido, retenções) — 404 se o débito não existir."""
    debito = await _obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    retencoes = await listar_retencoes_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    return debito.valor_total, valor_liquido(debito.valor_total, retencoes), retencoes


async def criar_retencao(db: AsyncSession, *, tenant_id: int, debito_id: int,
                         payload: RetencaoCreate) -> Retencao:
    await _obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    await _assert_debito_fora_de_lote_ativo(db, tenant_id=tenant_id, debito_id=debito_id)
    r = Retencao(
        tenant_id=tenant_id, id_debito=debito_id, tipo=payload.tipo,
        descricao=payload.descricao, base_calculo=payload.base_calculo,
        aliquota=payload.aliquota, valor=payload.valor, recolhido=False,
        criado_em=_utcnow(),
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


async def _obter_retencao(db: AsyncSession, *, tenant_id: int, retencao_id: int) -> Retencao:
    r = (await db.execute(select(Retencao).where(
        Retencao.id == retencao_id, Retencao.tenant_id == tenant_id,
        Retencao.excluido.is_(False)))).scalar_one_or_none()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Retenção não encontrada")
    return r


async def atualizar_retencao(db: AsyncSession, *, tenant_id: int, retencao_id: int,
                             payload: RetencaoUpdate) -> Retencao:
    r = await _obter_retencao(db, tenant_id=tenant_id, retencao_id=retencao_id)
    await _assert_debito_fora_de_lote_ativo(db, tenant_id=tenant_id, debito_id=r.id_debito)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(r, campo, valor)
    r.atualizado_em = _utcnow()
    await db.commit()
    await db.refresh(r)
    return r


async def excluir_retencao(db: AsyncSession, *, tenant_id: int, retencao_id: int) -> None:
    r = await _obter_retencao(db, tenant_id=tenant_id, retencao_id=retencao_id)
    await _assert_debito_fora_de_lote_ativo(db, tenant_id=tenant_id, debito_id=r.id_debito)
    r.excluido = True
    r.atualizado_em = _utcnow()
    await db.commit()


async def recolher_retencao(db: AsyncSession, *, tenant_id: int, retencao_id: int,
                            data_recolhimento: date, documento_recolhimento: str) -> Retencao:
    r = await _obter_retencao(db, tenant_id=tenant_id, retencao_id=retencao_id)
    r.recolhido = True
    r.data_recolhimento = data_recolhimento
    r.documento_recolhimento = documento_recolhimento
    r.atualizado_em = _utcnow()
    await db.commit()
    await db.refresh(r)
    return r


async def listar_pendentes_recolhimento(db: AsyncSession, *, tenant_id: int,
                                        tipo: str | None = None) -> list[Retencao]:
    stmt = select(Retencao).where(
        Retencao.tenant_id == tenant_id, Retencao.excluido.is_(False),
        Retencao.recolhido.is_(False),
    )
    if tipo is not None:
        stmt = stmt.where(Retencao.tipo == tipo)
    return list((await db.execute(stmt.order_by(Retencao.id))).scalars().all())
