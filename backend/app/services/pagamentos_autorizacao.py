"""Autorização de Pagamentos (R2) — autorizar em lote (saldo/alçada/segregação),
Ordem de Pagamento e consultas. Pagamento/estorno de parcela na Task 5."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Alcada, Debito, OrdemPagamento, OrdemPagamentoDebito
from . import pagamentos_caixa as caixa
from .pagamentos_debitos import (
    PagamentoDebitoError, _registrar_transicao, aprovadores_do_debito, obter_debito,
)


def _utcnow() -> datetime:
    return datetime.utcnow()


async def _alcada_do_usuario(db, *, tenant_id: int, usuario_id: int, id_natureza: int) -> Decimal:
    """Alçada específica da natureza; fallback geral (id_natureza IS NULL); sem alçada → 403."""
    especifica = (await db.execute(select(Alcada).where(
        Alcada.tenant_id == tenant_id, Alcada.id_usuario == usuario_id,
        Alcada.id_natureza == id_natureza, Alcada.excluido.is_(False)))).scalar_one_or_none()
    if especifica is not None:
        return especifica.valor_maximo
    geral = (await db.execute(select(Alcada).where(
        Alcada.tenant_id == tenant_id, Alcada.id_usuario == usuario_id,
        Alcada.id_natureza.is_(None), Alcada.excluido.is_(False)))).scalar_one_or_none()
    if geral is not None:
        return geral.valor_maximo
    raise PagamentoDebitoError("Usuário sem alçada cadastrada para autorizar esta natureza.",
                               status.HTTP_403_FORBIDDEN)


async def _proximo_numero_op(db, *, tenant_id: int) -> str:
    ano = _utcnow().year
    prefixo = f"OP-{ano}-"
    ultimo = (await db.execute(select(func.max(OrdemPagamento.numero)).where(
        OrdemPagamento.tenant_id == tenant_id,
        OrdemPagamento.numero.like(f"{prefixo}%")))).scalar_one_or_none()
    seq = int(ultimo.rsplit("-", 1)[1]) + 1 if ultimo else 1
    return f"{prefixo}{seq:04d}"


async def autorizar_lote(db: AsyncSession, *, tenant_id: int, usuario_id: int,
                         debito_ids: list[int], ip: str | None = None) -> OrdemPagamento:
    """All-or-nothing: valida TODOS os débitos antes de mudar qualquer status."""
    debitos: list[Debito] = []
    for did in debito_ids:
        d = await obter_debito(db, tenant_id=tenant_id, debito_id=did)
        if d.status != "APROVADO":
            raise PagamentoDebitoError(
                f"Débito {did} não está APROVADO (está '{d.status}').", status.HTTP_409_CONFLICT)
        if usuario_id == d.id_usuario_solicitante:
            raise PagamentoDebitoError(
                f"Segregação de funções: o solicitante do débito {did} não pode autorizá-lo.",
                status.HTTP_403_FORBIDDEN)
        if usuario_id in await aprovadores_do_debito(db, tenant_id=tenant_id, debito_id=did):
            raise PagamentoDebitoError(
                f"Segregação de funções: quem aprovou o débito {did} não pode autorizá-lo.",
                status.HTTP_403_FORBIDDEN)
        limite = await _alcada_do_usuario(db, tenant_id=tenant_id, usuario_id=usuario_id,
                                          id_natureza=d.id_natureza)
        if d.valor_total > limite:
            raise PagamentoDebitoError(
                f"Débito {did} (R$ {d.valor_total}) excede a alçada do autorizador (R$ {limite}).",
                status.HTTP_403_FORBIDDEN)
        debitos.append(d)

    # saldo por conta: disponível deve cobrir o Σ do lote naquela conta
    por_conta: dict[int, Decimal] = {}
    for d in debitos:
        por_conta[d.id_conta] = por_conta.get(d.id_conta, Decimal("0")) + d.valor_total
    for conta_id, total in por_conta.items():
        saldo = await caixa.saldo_conta(db, tenant_id=tenant_id, conta_id=conta_id)
        if saldo.disponivel < total:
            raise PagamentoDebitoError(
                f"Saldo disponível insuficiente na conta {conta_id}: "
                f"disponível R$ {saldo.disponivel}, necessário R$ {total}.",
                status.HTTP_422_UNPROCESSABLE_ENTITY)

    op = OrdemPagamento(tenant_id=tenant_id,
                        numero=await _proximo_numero_op(db, tenant_id=tenant_id),
                        id_usuario_autorizador=usuario_id,
                        valor_total=sum((d.valor_total for d in debitos), Decimal("0")),
                        ip_origem=ip, criado_em=_utcnow())
    db.add(op); await db.flush()
    for d in debitos:
        db.add(OrdemPagamentoDebito(tenant_id=tenant_id, id_ordem=op.id, id_debito=d.id))
        _registrar_transicao(db, debito=d, novo_status="AUTORIZADO", acao="AUTORIZADO",
                             usuario_id=usuario_id, justificativa=f"OP {op.numero}", ip=ip)
        d.atualizado_em = _utcnow()
    await db.commit(); await db.refresh(op)
    return op


async def listar_ordens(db: AsyncSession, *, tenant_id: int) -> list[OrdemPagamento]:
    return list((await db.execute(select(OrdemPagamento).where(
        OrdemPagamento.tenant_id == tenant_id)
        .order_by(OrdemPagamento.id.desc()))).scalars().all())


async def obter_ordem(db: AsyncSession, *, tenant_id: int, ordem_id: int) -> OrdemPagamento:
    op = (await db.execute(select(OrdemPagamento).where(
        OrdemPagamento.id == ordem_id,
        OrdemPagamento.tenant_id == tenant_id))).scalar_one_or_none()
    if op is None:
        raise PagamentoDebitoError("Ordem de pagamento não encontrada", status.HTTP_404_NOT_FOUND)
    return op


async def debitos_da_ordem(db: AsyncSession, *, tenant_id: int, ordem_id: int) -> list[Debito]:
    return list((await db.execute(select(Debito)
        .join(OrdemPagamentoDebito, OrdemPagamentoDebito.id_debito == Debito.id)
        .where(OrdemPagamentoDebito.tenant_id == tenant_id,
               OrdemPagamentoDebito.id_ordem == ordem_id)
        .order_by(Debito.id))).scalars().all())
