"""Caixa de Pagamentos — movimentações e saldo (R1). Saldo é derivado das
movimentações + conta.saldo_inicial (fonte única da verdade)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    BloqueioSaldo, ContaBancaria, Debito, FonteRecursos, MovimentacaoConta, Parcela, SaldoHistorico,
)
from ..schemas.pagamentos import (
    ContaSaldoPainel, FichaFonteContaItem, FichaFonteOut, MovimentacaoCreate, SaldoConta,
    SimulacaoAutorizacaoOut,
)

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
    """Σ parcelas A_PAGAR/LIBERADA (não excluídas) de débitos com reserva ativa
    (AUTORIZADO ou em tesouraria) cuja conta PAGADORA é esta conta (v2.0)."""
    from .pagamentos_debitos import COM_RESERVA
    stmt = (select(func.coalesce(func.sum(Parcela.valor), 0))
            .join(Debito, Debito.id == Parcela.id_debito)
            .where(Parcela.tenant_id == tenant_id, Parcela.status.in_(("A_PAGAR", "LIBERADA")),
                   Parcela.excluido.is_(False), Debito.id_conta_pagadora == conta_id,
                   Debito.excluido.is_(False), Debito.status.in_(COM_RESERVA)))
    return (await db.execute(stmt)).scalar_one()


async def bloqueado_conta(db, *, tenant_id, conta_id, ref: date | None = None) -> Decimal:
    """Σ dos bloqueios administrativos ATIVOS vigentes na data de referência (RF-SLD-07)."""
    hoje = ref or datetime.utcnow().date()
    stmt = (select(func.coalesce(func.sum(BloqueioSaldo.valor), 0))
            .where(BloqueioSaldo.tenant_id == tenant_id, BloqueioSaldo.id_conta == conta_id,
                   BloqueioSaldo.ativo.is_(True), BloqueioSaldo.excluido.is_(False),
                   BloqueioSaldo.periodo_inicio <= hoje,
                   or_(BloqueioSaldo.periodo_fim.is_(None), BloqueioSaldo.periodo_fim >= hoje)))
    return (await db.execute(stmt)).scalar_one()


async def ultima_atualizacao_conta(db, *, tenant_id, conta_id) -> datetime | None:
    """Data/hora da última movimentação da conta (RF-AUT-05/RF-SLD-06)."""
    return (await db.execute(select(func.max(MovimentacaoConta.criado_em)).where(
        MovimentacaoConta.tenant_id == tenant_id, MovimentacaoConta.id_conta == conta_id,
        MovimentacaoConta.excluido.is_(False)))).scalar_one_or_none()


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
    bloqueado = await bloqueado_conta(db, tenant_id=tenant_id, conta_id=conta_id)
    saldo_atual = inicial + entradas - saidas
    # Conciliado := saldo bancário até a conciliação da Fase 3 existir (spec seção 10).
    # Disponível projetado = conciliado − reservado (autorizados-não-debitados) − bloqueado.
    # Estornos já são ENTRADAS, portanto já compõem o saldo.
    disponivel = saldo_atual - comprometido - bloqueado
    return SaldoConta(id_conta=conta_id, saldo_inicial=inicial, total_entradas=entradas,
                      total_saidas=saidas, saldo_atual=saldo_atual,
                      comprometido=comprometido, bloqueado=bloqueado, disponivel=disponivel,
                      saldo_bancario=saldo_atual, saldo_conciliado=saldo_atual,
                      disponivel_projetado=disponivel)


async def registrar_snapshot_saldos(db, *, tenant_id, ref: date | None = None) -> int:
    """Grava/atualiza o snapshot diário dos saldos de cada conta do tenant
    (RF-SLD-03). Idempotente por (tenant_id, id_conta, data). Retorna nº de contas."""
    dia = ref or datetime.utcnow().date()
    contas = (await db.execute(select(ContaBancaria).where(
        ContaBancaria.tenant_id == tenant_id, ContaBancaria.excluido.is_(False)))).scalars().all()
    n = 0
    for conta in contas:
        s = await saldo_conta(db, tenant_id=tenant_id, conta_id=conta.id)
        valores = dict(saldo_bancario=s.saldo_bancario, saldo_conciliado=s.saldo_conciliado,
                       saldo_reservado=s.comprometido, saldo_bloqueado=s.bloqueado)
        stmt = pg_insert(SaldoHistorico).values(
            tenant_id=tenant_id, id_conta=conta.id, data=dia,
            criado_em=datetime.utcnow(), **valores)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_saldohist_conta_data", set_=valores)
        await db.execute(stmt)
        n += 1
    await db.commit()
    return n


async def simular_autorizacao(db, *, tenant_id, id_conta, debito_ids=None, valor=None):
    """Impacto projetado de um pagamento na conta (RF-PNL-05), sem gravar nada."""
    conta = await _obter_conta(db, tenant_id=tenant_id, conta_id=id_conta)
    if debito_ids:
        soma = (await db.execute(select(func.coalesce(func.sum(Debito.valor_total), 0)).where(
            Debito.tenant_id == tenant_id, Debito.id.in_(debito_ids),
            Debito.excluido.is_(False)))).scalar_one()
        valor_simulado = Decimal(soma)
    else:
        valor_simulado = Decimal(valor or 0)
    s = await saldo_conta(db, tenant_id=tenant_id, conta_id=conta.id)
    apos = s.disponivel_projetado - valor_simulado
    return SimulacaoAutorizacaoOut(
        id_conta=conta.id, valor_simulado=valor_simulado,
        disponivel_antes=s.disponivel_projetado, disponivel_projetado_apos=apos,
        suficiente=apos >= 0)


def _mascara(conta: str) -> str:
    limpa = (conta or "").strip()
    return ("****" + limpa[-4:]) if len(limpa) > 4 else (limpa or "****")


async def ficha_fonte(db, *, tenant_id, id_fonte) -> FichaFonteOut:
    """Ficha da fonte com TODAS as contas vinculadas e seus saldos (RF-FON-06)."""
    fonte = (await db.execute(select(FonteRecursos).where(
        FonteRecursos.id == id_fonte, FonteRecursos.tenant_id == tenant_id,
        FonteRecursos.excluido.is_(False)))).scalar_one_or_none()
    if fonte is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fonte não encontrada")
    contas = (await db.execute(select(ContaBancaria).where(
        ContaBancaria.tenant_id == tenant_id, ContaBancaria.id_fonte_recursos == id_fonte,
        ContaBancaria.excluido.is_(False)).order_by(ContaBancaria.nome))).scalars().all()
    itens: list[FichaFonteContaItem] = []
    disponivel_total = Decimal("0")
    for c in contas:
        s = await saldo_conta(db, tenant_id=tenant_id, conta_id=c.id)
        atualizado = await ultima_atualizacao_conta(db, tenant_id=tenant_id, conta_id=c.id)
        if c.ativa:
            disponivel_total += s.disponivel_projetado
        itens.append(FichaFonteContaItem(
            id_conta=c.id, nome=c.nome, banco=c.banco, conta_mascarada=_mascara(c.conta),
            ativa=c.ativa, modo_movimentacao=c.modo_movimentacao,
            saldo_bancario=s.saldo_bancario, saldo_conciliado=s.saldo_conciliado,
            reservado=s.comprometido, bloqueado=s.bloqueado,
            disponivel_projetado=s.disponivel_projetado, atualizado_em=atualizado))
    return FichaFonteOut(
        id_fonte=fonte.id, codigo=fonte.codigo, descricao=fonte.descricao, situacao=fonte.situacao,
        exercicio=fonte.exercicio, tipo_vinculacao=fonte.tipo_vinculacao,
        disponivel_total=disponivel_total, contas=itens)


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
            bloqueado=saldo.bloqueado, saldo_conciliado=saldo.saldo_conciliado,
            disponivel_projetado=saldo.disponivel_projetado,
        ))
    return painel
