"""Autorização de Pagamentos (R2) — autorizar em lote (saldo/alçada/segregação),
Ordem de Pagamento e consultas. Pagamento/estorno de parcela na Task 5."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Alcada, Debito, DebitoHistorico, MovimentacaoConta, OrdemPagamento, OrdemPagamentoDebito, Parcela,
)
from . import pagamentos_caixa as caixa
from .pagamentos_debitos import (
    PagamentoDebitoError, _registrar_transicao, aprovadores_do_debito, listar_parcelas, obter_debito,
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


async def obter_parcela(db: AsyncSession, *, tenant_id: int, parcela_id: int) -> Parcela:
    p = (await db.execute(select(Parcela).where(Parcela.id == parcela_id,
        Parcela.tenant_id == tenant_id, Parcela.excluido.is_(False)).with_for_update())
        ).scalar_one_or_none()
    if p is None:
        raise PagamentoDebitoError("Parcela não encontrada", status.HTTP_404_NOT_FOUND)
    return p


async def liberar_parcelas(db: AsyncSession, *, tenant_id: int, usuario_id: int,
                           parcela_ids: list[int], data_prevista: date | None = None,
                           ip: str | None = None) -> list[Parcela]:
    """Liberação de pagamento (2º ato do rito): parcela A_PAGAR de débito
    AUTORIZADO|PAGO_PARCIAL → LIBERADA. Lote all-or-nothing: valida (com lock)
    TODAS as parcelas e débitos antes de mudar qualquer status. Histórico: uma
    ação LIBERADO por débito envolvido, agrupando os números das parcelas."""
    pares: list[tuple[Parcela, Debito]] = []
    debitos_por_id: dict[int, Debito] = {}
    for pid in parcela_ids:
        p = await obter_parcela(db, tenant_id=tenant_id, parcela_id=pid)
        d = debitos_por_id.get(p.id_debito)
        if d is None:
            d = await obter_debito(db, tenant_id=tenant_id, debito_id=p.id_debito, for_update=True)
            debitos_por_id[d.id] = d
        if d.status not in ("AUTORIZADO", "PAGO_PARCIAL"):
            raise PagamentoDebitoError(
                f"Débito {d.id} não autorizado para liberação de pagamento (está '{d.status}').",
                status.HTTP_409_CONFLICT)
        if p.status != "A_PAGAR":
            raise PagamentoDebitoError(
                f"Parcela {pid} não está a pagar (está '{p.status}').", status.HTTP_409_CONFLICT)
        pares.append((p, d))

    numeros_por_debito: dict[int, list[int]] = {}
    for p, d in pares:
        p.status = "LIBERADA"; p.data_liberacao = _utcnow().date()
        p.id_usuario_liberacao = usuario_id; p.data_prevista_pagamento = data_prevista
        p.atualizado_em = _utcnow()
        numeros_por_debito.setdefault(d.id, []).append(p.numero)

    for d_id, numeros in numeros_por_debito.items():
        d = debitos_por_id[d_id]
        justificativa = f"Parcelas {', '.join(str(n) for n in sorted(numeros))}"
        db.add(DebitoHistorico(tenant_id=tenant_id, id_debito=d.id, status_anterior=d.status,
                               status_novo=d.status, acao="LIBERADO", justificativa=justificativa,
                               id_usuario=usuario_id, ip_origem=ip, criado_em=_utcnow()))
        d.atualizado_em = _utcnow()

    await db.commit()
    for p, _d in pares:
        await db.refresh(p)
    return [p for p, _d in pares]


async def revogar_liberacao(db: AsyncSession, *, tenant_id: int, usuario_id: int, parcela_id: int,
                            justificativa: str, ip: str | None = None) -> Parcela:
    """Reverte a liberação: LIBERADA → A_PAGAR, limpa os campos de liberação.
    Histórico do débito: ação LIBERACAO_REVOGADA."""
    p = await obter_parcela(db, tenant_id=tenant_id, parcela_id=parcela_id)
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=p.id_debito, for_update=True)
    if p.status != "LIBERADA":
        raise PagamentoDebitoError(f"Parcela não está liberada (está '{p.status}').",
                                   status.HTTP_409_CONFLICT)
    p.status = "A_PAGAR"; p.data_liberacao = None
    p.id_usuario_liberacao = None; p.data_prevista_pagamento = None
    p.atualizado_em = _utcnow()
    db.add(DebitoHistorico(tenant_id=tenant_id, id_debito=d.id, status_anterior=d.status,
                           status_novo=d.status, acao="LIBERACAO_REVOGADA", justificativa=justificativa,
                           id_usuario=usuario_id, ip_origem=ip, criado_em=_utcnow()))
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(p)
    return p


async def pagar_parcela(db: AsyncSession, *, tenant_id: int, usuario_id: int, parcela_id: int,
                        forma_pagamento: str, data_pagamento: date | None = None,
                        ip: str | None = None) -> Parcela:
    """Atômico: movimentação SAIDA/PAGAMENTO + parcela PAGA + status do débito, num commit."""
    p = await obter_parcela(db, tenant_id=tenant_id, parcela_id=parcela_id)
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=p.id_debito, for_update=True)
    if d.status not in ("AUTORIZADO", "PAGO_PARCIAL"):
        raise PagamentoDebitoError(
            f"Débito não autorizado para pagamento (está '{d.status}').", status.HTTP_409_CONFLICT)
    if p.status != "LIBERADA":
        raise PagamentoDebitoError(
            f"Parcela não liberada para pagamento (está '{p.status}').", status.HTTP_409_CONFLICT)
    quando = data_pagamento or _utcnow().date()
    mov = MovimentacaoConta(tenant_id=tenant_id, id_conta=d.id_conta, tipo="SAIDA",
                            valor=p.valor, origem="PAGAMENTO", id_debito=d.id, id_parcela=p.id,
                            data=quando, id_usuario=usuario_id,
                            descricao=f"Pagamento parcela {p.numero} — débito #{d.id}"[:255],
                            criado_em=_utcnow())
    db.add(mov); await db.flush()
    p.status = "PAGA"; p.data_pagamento = quando
    p.forma_pagamento = forma_pagamento; p.id_movimentacao = mov.id; p.atualizado_em = _utcnow()
    todas = await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
    pendentes = [x for x in todas if x.id != p.id and x.status == "A_PAGAR"]
    novo = "PAGO" if not pendentes else "PAGO_PARCIAL"
    _registrar_transicao(db, debito=d, novo_status=novo, acao="PAGAMENTO", usuario_id=usuario_id,
                         justificativa=f"Parcela {p.numero} — {forma_pagamento}", ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(p)
    return p


async def estornar_parcela(db: AsyncSession, *, tenant_id: int, usuario_id: int, parcela_id: int,
                           justificativa: str, ip: str | None = None) -> Parcela:
    p = await obter_parcela(db, tenant_id=tenant_id, parcela_id=parcela_id)
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=p.id_debito, for_update=True)
    if p.status != "PAGA":
        raise PagamentoDebitoError("Só parcelas pagas podem ser estornadas.", status.HTTP_409_CONFLICT)
    mov = MovimentacaoConta(tenant_id=tenant_id, id_conta=d.id_conta, tipo="ENTRADA",
                            valor=p.valor, origem="ESTORNO", id_debito=d.id, id_parcela=p.id,
                            data=_utcnow().date(), id_usuario=usuario_id,
                            descricao=f"Estorno parcela {p.numero} — débito #{d.id}: {justificativa}"[:255],
                            criado_em=_utcnow())
    db.add(mov)
    p.status = "A_PAGAR"; p.data_pagamento = None
    p.forma_pagamento = None; p.id_movimentacao = None
    p.data_liberacao = None; p.id_usuario_liberacao = None; p.data_prevista_pagamento = None
    p.atualizado_em = _utcnow()
    todas = await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
    alguma_paga = any(x.id != p.id and x.status == "PAGA" for x in todas)
    novo = "PAGO_PARCIAL" if alguma_paga else "AUTORIZADO"
    _registrar_transicao(db, debito=d, novo_status=novo, acao="ESTORNO", usuario_id=usuario_id,
                         justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(p)
    return p
