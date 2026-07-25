"""Caixa de Pagamentos — movimentações e saldo (R1). Saldo é derivado das
movimentações + conta.saldo_inicial (fonte única da verdade)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ContaBancaria, Debito, MovimentacaoConta, Parcela
from ..schemas.pagamentos import ContaSaldoPainel, MovimentacaoCreate, SaldoConta

_ORIGENS_MANUAIS = {"APORTE", "RECEITA", "AJUSTE"}


async def _obter_conta(db, *, tenant_id, conta_id) -> ContaBancaria:
    c = (await db.execute(select(ContaBancaria).where(
        ContaBancaria.id == conta_id, ContaBancaria.tenant_id == tenant_id,
        ContaBancaria.excluido.is_(False)))).scalar_one_or_none()
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada")
    return c


async def lancar_movimentacao(db, *, tenant_id, usuario_id, payload: MovimentacaoCreate) -> MovimentacaoConta:
    if payload.origem not in _ORIGENS_MANUAIS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Origem interna (PAGAMENTO/ESTORNO) não pode ser lançada manualmente.")
    await _obter_conta(db, tenant_id=tenant_id, conta_id=payload.id_conta)
    m = MovimentacaoConta(tenant_id=tenant_id, id_conta=payload.id_conta, tipo=payload.tipo,
                          valor=payload.valor, origem=payload.origem, data=payload.data,
                          id_usuario=usuario_id, descricao=payload.descricao, criado_em=datetime.utcnow())
    db.add(m); await db.commit(); await db.refresh(m); return m


async def listar_extrato(db, *, tenant_id, conta_id) -> list[MovimentacaoConta]:
    await _obter_conta(db, tenant_id=tenant_id, conta_id=conta_id)
    return list((await db.execute(select(MovimentacaoConta).where(
        MovimentacaoConta.tenant_id == tenant_id, MovimentacaoConta.id_conta == conta_id,
        MovimentacaoConta.excluido.is_(False)).order_by(MovimentacaoConta.data.desc(),
        MovimentacaoConta.id.desc()))).scalars().all())


async def comprometido_conta(db, *, tenant_id, conta_id) -> Decimal:
    """Σ parcelas A_PAGAR/LIBERADA (não excluídas) de débitos AUTORIZADO/PAGO_PARCIAL
    cuja conta PAGADORA (reservada na autorização, v2.0) é esta conta."""
    stmt = (select(func.coalesce(func.sum(Parcela.valor), 0))
            .join(Debito, Debito.id == Parcela.id_debito)
            .where(Parcela.tenant_id == tenant_id, Parcela.status.in_(("A_PAGAR", "LIBERADA")),
                   Parcela.excluido.is_(False), Debito.id_conta_pagadora == conta_id,
                   Debito.excluido.is_(False),
                   Debito.status.in_(("AUTORIZADO", "PAGO_PARCIAL"))))
    return (await db.execute(stmt)).scalar_one()


async def saldo_conta(db, *, tenant_id, conta_id) -> SaldoConta:
    conta = await _obter_conta(db, tenant_id=tenant_id, conta_id=conta_id)
    def _soma(tipo: str):
        return select(func.coalesce(func.sum(MovimentacaoConta.valor), 0)).where(
            MovimentacaoConta.tenant_id == tenant_id, MovimentacaoConta.id_conta == conta_id,
            MovimentacaoConta.excluido.is_(False), MovimentacaoConta.tipo == tipo)
    entradas = (await db.execute(_soma("ENTRADA"))).scalar_one()
    saidas = (await db.execute(_soma("SAIDA"))).scalar_one()
    inicial = conta.saldo_inicial or Decimal("0")
    comprometido = await comprometido_conta(db, tenant_id=tenant_id, conta_id=conta_id)
    saldo_atual = inicial + entradas - saidas
    return SaldoConta(id_conta=conta_id, saldo_inicial=inicial, total_entradas=entradas,
                      total_saidas=saidas, saldo_atual=saldo_atual,
                      comprometido=comprometido, disponivel=saldo_atual - comprometido)


async def painel_caixa(db, *, tenant_id) -> list[ContaSaldoPainel]:
    contas = (await db.execute(select(ContaBancaria).where(
        ContaBancaria.tenant_id == tenant_id, ContaBancaria.excluido.is_(False))
        .order_by(ContaBancaria.nome))).scalars().all()
    painel: list[ContaSaldoPainel] = []
    for conta in contas:
        saldo = await saldo_conta(db, tenant_id=tenant_id, conta_id=conta.id)
        minimo = conta.saldo_minimo_alerta or Decimal("0")
        painel.append(ContaSaldoPainel(
            id_conta=conta.id, nome=conta.nome, banco=conta.banco, grupo_despesa=conta.grupo_despesa,
            saldo_inicial=saldo.saldo_inicial, total_entradas=saldo.total_entradas,
            total_saidas=saldo.total_saidas, saldo_atual=saldo.saldo_atual,
            saldo_minimo_alerta=minimo, abaixo_minimo=saldo.saldo_atual < minimo,
            comprometido=saldo.comprometido, disponivel=saldo.disponivel,
        ))
    return painel
