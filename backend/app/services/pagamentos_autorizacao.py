"""Autorização de Pagamentos (R2) — autorizar em lote (saldo/alçada/segregação),
Ordem de Pagamento e consultas. Pagamento/estorno de parcela na Task 5."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Alcada, ContaBancaria, Debito, DebitoHistorico, MovimentacaoConta, OrdemPagamento,
    OrdemPagamentoDebito, Parcela,
)
from ..schemas.pagamentos import ContaElegivelOut, GrupoAutorizacaoIn
from . import pagamentos_cadastros as cad
from . import pagamentos_caixa as caixa
from .pagamentos_debitos import (
    PagamentoDebitoError, _registrar_transicao, aprovadores_do_debito, listar_parcelas, obter_debito,
)


def _mascarar_conta(conta: str) -> str:
    """Exibe apenas os últimos 4 dígitos da conta (RF-AUT-05/09)."""
    limpa = (conta or "").strip()
    return ("****" + limpa[-4:]) if len(limpa) > 4 else (limpa or "****")


async def contas_elegiveis(db: AsyncSession, *, tenant_id: int, id_fonte: int) -> list[ContaElegivelOut]:
    """Contas ATIVAS da fonte, com saldo/disponível — candidatas a conta pagadora."""
    contas = list((await db.execute(select(ContaBancaria).where(
        ContaBancaria.tenant_id == tenant_id, ContaBancaria.id_fonte_recursos == id_fonte,
        ContaBancaria.ativa.is_(True), ContaBancaria.excluido.is_(False),
        ContaBancaria.modo_movimentacao == "PAGA")  # só contas que admitem pagamento (RF-CTA-08)
        .order_by(ContaBancaria.nome))).scalars().all())
    out: list[ContaElegivelOut] = []
    for c in contas:
        saldo = await caixa.saldo_conta(db, tenant_id=tenant_id, conta_id=c.id)
        minimo = c.saldo_minimo_alerta or Decimal("0")
        atualizado = await caixa.ultima_atualizacao_conta(db, tenant_id=tenant_id, conta_id=c.id)
        out.append(ContaElegivelOut(
            id_conta=c.id, nome=c.nome, banco=c.banco, agencia=c.agencia,
            conta_mascarada=_mascarar_conta(c.conta), saldo_atual=saldo.saldo_atual,
            disponivel=saldo.disponivel, abaixo_minimo=saldo.saldo_atual < minimo,
            reservado=saldo.comprometido, bloqueado=saldo.bloqueado,
            saldo_conciliado=saldo.saldo_conciliado,
            disponivel_projetado=saldo.disponivel_projetado, atualizado_em=atualizado))
    return out


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


async def _obter_conta_pagadora(db, *, tenant_id: int, conta_id: int) -> ContaBancaria:
    c = (await db.execute(select(ContaBancaria).where(
        ContaBancaria.id == conta_id, ContaBancaria.tenant_id == tenant_id,
        ContaBancaria.excluido.is_(False)))).scalar_one_or_none()
    if c is None:
        raise PagamentoDebitoError("Conta pagadora não encontrada.", status.HTTP_404_NOT_FOUND)
    if not c.ativa:
        raise PagamentoDebitoError(
            f"Conta pagadora {conta_id} não está ativa.", status.HTTP_422_UNPROCESSABLE_ENTITY)
    if c.modo_movimentacao != "PAGA":
        raise PagamentoDebitoError(
            f"Conta {conta_id} não admite pagamento (modo '{c.modo_movimentacao}').",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    return c


async def autorizar_lote(db: AsyncSession, *, tenant_id: int, usuario_id: int,
                         grupos: list[GrupoAutorizacaoIn], ip: str | None = None) -> list[OrdemPagamento]:
    """Autoriza por grupo {fonte, conta_pagadora, débitos} — v2.0 (RF-AUT-02..15).
    All-or-nothing sobre TODOS os grupos: valida tudo (fonte↔conta, segregação,
    alçada, saldo projetado) antes de gravar conta pagadora / criar qualquer OP.
    A conta pagadora é escolhida aqui e gravada imutável em debito.id_conta_pagadora."""
    if not grupos:
        raise PagamentoDebitoError("Nenhum grupo informado para autorização.",
                                   status.HTTP_422_UNPROCESSABLE_ENTITY)

    # 1) valida cada grupo e coleta os débitos; acumula necessidade por conta pagadora.
    grupos_val: list[tuple[GrupoAutorizacaoIn, ContaBancaria, list[Debito], Decimal]] = []
    necessidade_por_conta: dict[int, Decimal] = {}
    # RN-15: justificativa da exceção de saldo insuficiente, por conta (se autorizada).
    excecao_por_conta: dict[int, str] = {}
    vistos: set[int] = set()
    for g in grupos:
        conta = await _obter_conta_pagadora(db, tenant_id=tenant_id, conta_id=g.id_conta_pagadora)
        if g.permitir_saldo_insuficiente:
            if not (g.justificativa_excecao or "").strip():
                raise PagamentoDebitoError(
                    "Exceção de saldo insuficiente exige justificativa (RN-15).",
                    status.HTTP_422_UNPROCESSABLE_ENTITY)
            excecao_por_conta[conta.id] = g.justificativa_excecao.strip()
        if conta.id_fonte_recursos != g.id_fonte:
            raise PagamentoDebitoError(
                f"Conta pagadora {conta.id} não pertence à fonte {g.id_fonte} (RN-06).",
                status.HTTP_422_UNPROCESSABLE_ENTITY)
        debitos: list[Debito] = []
        for did in g.debito_ids:
            if did in vistos:
                raise PagamentoDebitoError(
                    f"Débito {did} informado em mais de um grupo.", status.HTTP_409_CONFLICT)
            vistos.add(did)
            d = await obter_debito(db, tenant_id=tenant_id, debito_id=did, for_update=True)
            if d.status != "APROVADO":
                raise PagamentoDebitoError(
                    f"Débito {did} não está APROVADO (está '{d.status}').", status.HTTP_409_CONFLICT)
            if d.id_fonte_recursos != g.id_fonte:
                raise PagamentoDebitoError(
                    f"Débito {did} não pertence à fonte {g.id_fonte} do grupo (RF-AUT-15).",
                    status.HTTP_422_UNPROCESSABLE_ENTITY)
            if not (d.numero_ne or "").strip():
                raise PagamentoDebitoError(
                    f"Débito {did} não pode ser autorizado sem número de empenho (RN-01).",
                    status.HTTP_422_UNPROCESSABLE_ENTITY)
            if not d.liquidacao_confirmada:
                raise PagamentoDebitoError(
                    f"Débito {did} não pode ser autorizado sem liquidação confirmada (RN-01).",
                    status.HTTP_422_UNPROCESSABLE_ENTITY)
            forn = await cad.obter_fornecedor(db, tenant_id=tenant_id, fornecedor_id=d.id_fornecedor)
            if forn.situacao_cadastral == "IRREGULAR":
                raise PagamentoDebitoError(
                    f"Fornecedor do débito {did} está IRREGULAR — pagamento bloqueado (RF-VAL-03).",
                    status.HTTP_422_UNPROCESSABLE_ENTITY)
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
        total = sum((d.valor_total for d in debitos), Decimal("0"))
        necessidade_por_conta[conta.id] = necessidade_por_conta.get(conta.id, Decimal("0")) + total
        grupos_val.append((g, conta, debitos, total))

    # 2) saldo disponível projetado de cada conta pagadora cobre o Σ que ela receberá.
    #    RN-15: se a autoridade autorizou expressamente a exceção (com justificativa),
    #    o bloqueio é dispensado e a exceção fica registrada no histórico.
    disponivel_corrente: dict[int, Decimal] = {}
    for conta_id, necessario in necessidade_por_conta.items():
        saldo = await caixa.saldo_conta(db, tenant_id=tenant_id, conta_id=conta_id)
        disponivel_corrente[conta_id] = saldo.disponivel
        if saldo.disponivel < necessario and conta_id not in excecao_por_conta:
            raise PagamentoDebitoError(
                f"Saldo disponível insuficiente na conta {conta_id}: "
                f"disponível R$ {saldo.disponivel}, necessário R$ {necessario}.",
                status.HTTP_422_UNPROCESSABLE_ENTITY)

    # 3) grava: uma OP por grupo, reserva na conta pagadora escolhida (imutável).
    ordens: list[OrdemPagamento] = []
    for g, conta, debitos, total in grupos_val:
        # RF-AUT-16: saldo antes e projetado após esta reserva (sequencial por conta).
        antes = disponivel_corrente[conta.id]
        apos = antes - total
        disponivel_corrente[conta.id] = apos
        op = OrdemPagamento(tenant_id=tenant_id,
                            numero=await _proximo_numero_op(db, tenant_id=tenant_id),
                            id_usuario_autorizador=usuario_id,
                            id_conta_pagadora=conta.id, valor_reservado=total,
                            saldo_antes=antes, saldo_projetado_apos=apos,
                            valor_total=total, ip_origem=ip, criado_em=_utcnow())
        db.add(op); await db.flush()
        justificativa = f"OP {op.numero}"
        if conta.id in excecao_por_conta:
            justificativa += f" — EXCEÇÃO DE SALDO (RN-15): {excecao_por_conta[conta.id]}"
        for d in debitos:
            d.id_conta_pagadora = conta.id
            db.add(OrdemPagamentoDebito(tenant_id=tenant_id, id_ordem=op.id, id_debito=d.id))
            _registrar_transicao(db, debito=d, novo_status="AUTORIZADO", acao="AUTORIZADO",
                                 usuario_id=usuario_id, justificativa=justificativa[:255], ip=ip)
            d.atualizado_em = _utcnow()
        ordens.append(op)
    await db.commit()
    for op in ordens:
        await db.refresh(op)
    return ordens


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
    if d.id_conta_pagadora is None:
        raise PagamentoDebitoError(
            "Débito sem conta pagadora definida (não autorizado corretamente).",
            status.HTTP_409_CONFLICT)
    mov = MovimentacaoConta(tenant_id=tenant_id, id_conta=d.id_conta_pagadora, tipo="SAIDA",
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
    mov = MovimentacaoConta(tenant_id=tenant_id, id_conta=d.id_conta_pagadora, tipo="ENTRADA",
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
