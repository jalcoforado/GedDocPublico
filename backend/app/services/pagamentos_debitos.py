"""Débitos de Pagamentos (R2) — CRUD de rascunho e transições de workflow.
Transições SÓ por aqui; cada uma grava debito_historico na MESMA transação."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Debito, DebitoHistorico, Fornecedor, Parcela, Usuario
from ..schemas.pagamentos import DebitoCreate, DebitoUpdate
from . import pagamentos_cadastros as cad


def _utcnow() -> datetime:
    return datetime.utcnow()


class PagamentoDebitoError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=code, detail=detail)


def _validar_parcelas(parcelas, valor_total: Decimal) -> None:
    numeros = sorted(p.numero for p in parcelas)
    if numeros != list(range(1, len(parcelas) + 1)):
        raise PagamentoDebitoError("Parcelas devem ser numeradas 1..N sem repetição.",
                                   status.HTTP_422_UNPROCESSABLE_ENTITY)
    soma = sum((p.valor for p in parcelas), Decimal("0"))
    if soma != valor_total:
        raise PagamentoDebitoError(
            f"Soma das parcelas ({soma}) difere do valor total ({valor_total}).",
            status.HTTP_422_UNPROCESSABLE_ENTITY)


async def _validar_refs(db, *, tenant_id: int, payload) -> None:
    await cad.obter_fornecedor(db, tenant_id=tenant_id, fornecedor_id=payload.id_fornecedor)
    await cad.obter_natureza(db, tenant_id=tenant_id, natureza_id=payload.id_natureza)
    await cad.obter_fonte(db, tenant_id=tenant_id, fonte_id=payload.id_fonte_recursos)
    # Conta é apenas uma sugestão (não-vinculante); se informada, deve ser da mesma fonte.
    if payload.id_conta is not None:
        conta = await cad.obter_conta(db, tenant_id=tenant_id, conta_id=payload.id_conta)
        if conta.id_fonte_recursos != payload.id_fonte_recursos:
            raise PagamentoDebitoError(
                "Conta sugerida não pertence à fonte de recursos informada.",
                status.HTTP_422_UNPROCESSABLE_ENTITY)
    if payload.id_contrato is not None:
        await cad.obter_contrato(db, tenant_id=tenant_id, contrato_id=payload.id_contrato)


def _registrar_transicao(db, *, debito: Debito, novo_status: str, acao: str,
                         usuario_id: int | None, justificativa: str | None = None,
                         ip: str | None = None) -> None:
    db.add(DebitoHistorico(tenant_id=debito.tenant_id, id_debito=debito.id,
                           status_anterior=debito.status if acao != "CRIADO" else None,
                           status_novo=novo_status, acao=acao, justificativa=justificativa,
                           id_usuario=usuario_id, ip_origem=ip, criado_em=_utcnow()))
    debito.status = novo_status


async def detectar_duplicidade(db, *, tenant_id: int, id_fornecedor: int, numero_nf: str | None,
                               numero_ne: str | None, valor_total, competencia: str,
                               excluir_id: int | None = None) -> list[int]:
    """IDs de débitos ativos com mesmo credor+NF+empenho+valor+competência (RF-SOL-09).
    Só considera quando há nota fiscal (numero_nf) — o documento que caracteriza a
    despesa. Ignora débitos já REJEITADO/CANCELADO."""
    if not numero_nf:
        return []
    stmt = select(Debito.id).where(
        Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
        Debito.id_fornecedor == id_fornecedor, Debito.numero_nf == numero_nf,
        Debito.valor_total == valor_total, Debito.competencia == competencia,
        Debito.status.notin_(("REJEITADO", "CANCELADO")))
    if numero_ne:
        stmt = stmt.where(Debito.numero_ne == numero_ne)
    if excluir_id is not None:
        stmt = stmt.where(Debito.id != excluir_id)
    return list((await db.execute(stmt)).scalars().all())


async def criar_debito(db: AsyncSession, *, tenant_id: int, usuario_id: int,
                       payload: DebitoCreate) -> Debito:
    await _validar_refs(db, tenant_id=tenant_id, payload=payload)
    _validar_parcelas(payload.parcelas, payload.valor_total)
    dups = await detectar_duplicidade(
        db, tenant_id=tenant_id, id_fornecedor=payload.id_fornecedor, numero_nf=payload.numero_nf,
        numero_ne=payload.numero_ne, valor_total=payload.valor_total, competencia=payload.competencia)
    if dups:
        raise PagamentoDebitoError(
            f"Possível duplicidade: já existe(m) débito(s) {dups} com mesmo credor, NF, "
            f"empenho, valor e competência.", status.HTTP_409_CONFLICT)
    d = Debito(tenant_id=tenant_id, id_fornecedor=payload.id_fornecedor,
               id_natureza=payload.id_natureza, id_fonte_recursos=payload.id_fonte_recursos,
               id_conta=payload.id_conta, id_contrato=payload.id_contrato,
               valor_total=payload.valor_total,
               competencia=payload.competencia, numero_ne=payload.numero_ne,
               numero_nf=payload.numero_nf, criticidade=payload.criticidade,
               urgente=payload.urgente, justificativa_urgencia=payload.justificativa_urgencia,
               descricao=payload.descricao, status="RASCUNHO",
               id_usuario_solicitante=usuario_id, criado_em=_utcnow())
    db.add(d); await db.flush()
    for p in payload.parcelas:
        db.add(Parcela(tenant_id=tenant_id, id_debito=d.id, numero=p.numero,
                       valor=p.valor, vencimento=p.vencimento, criado_em=_utcnow()))
    _registrar_transicao(db, debito=d, novo_status="RASCUNHO", acao="CRIADO", usuario_id=usuario_id)
    await db.commit(); await db.refresh(d)
    return d


async def obter_debito(db: AsyncSession, *, tenant_id: int, debito_id: int,
                       for_update: bool = False) -> Debito:
    stmt = select(Debito).where(Debito.id == debito_id,
        Debito.tenant_id == tenant_id, Debito.excluido.is_(False))
    if for_update:
        stmt = stmt.with_for_update()
    d = (await db.execute(stmt)).scalar_one_or_none()
    if d is None:
        raise PagamentoDebitoError("Débito não encontrado", status.HTTP_404_NOT_FOUND)
    return d


async def listar_debitos(db: AsyncSession, *, tenant_id: int, status_f: str | None = None,
                         solicitante_id: int | None = None) -> list[Debito]:
    stmt = select(Debito).where(Debito.tenant_id == tenant_id, Debito.excluido.is_(False))
    if status_f:
        stmt = stmt.where(Debito.status == status_f)
    if solicitante_id is not None:
        stmt = stmt.where(Debito.id_usuario_solicitante == solicitante_id)
    return list((await db.execute(stmt.order_by(Debito.id.desc()))).scalars().all())


async def listar_parcelas(db: AsyncSession, *, tenant_id: int, debito_id: int) -> list[Parcela]:
    return list((await db.execute(select(Parcela).where(
        Parcela.tenant_id == tenant_id, Parcela.id_debito == debito_id,
        Parcela.excluido.is_(False)).order_by(Parcela.numero))).scalars().all())


async def listar_historico(db: AsyncSession, *, tenant_id: int, debito_id: int) -> list[DebitoHistorico]:
    return list((await db.execute(select(DebitoHistorico).where(
        DebitoHistorico.tenant_id == tenant_id, DebitoHistorico.id_debito == debito_id)
        .order_by(DebitoHistorico.criado_em.desc(), DebitoHistorico.id.desc()))).scalars().all())


async def atualizar_debito(db: AsyncSession, *, tenant_id: int, debito_id: int,
                           usuario_id: int, payload: DebitoUpdate) -> Debito:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    if d.status != "RASCUNHO":
        raise PagamentoDebitoError("Só é possível editar débitos em rascunho.",
                                   status.HTTP_409_CONFLICT)
    dados = payload.model_dump(exclude_unset=True)
    parcelas_novas = dados.pop("parcelas", None)
    valor_total = dados.get("valor_total", d.valor_total)
    if parcelas_novas is not None:
        _validar_parcelas(payload.parcelas, valor_total)
    elif "valor_total" in dados:
        atuais = await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
        soma = sum((p.valor for p in atuais), Decimal("0"))
        if soma != valor_total:
            raise PagamentoDebitoError(
                f"Soma das parcelas ({soma}) difere do novo valor total ({valor_total}).",
                status.HTTP_422_UNPROCESSABLE_ENTITY)
    # valida refs alteradas
    class _Ref:  # payload efetivo para _validar_refs
        id_fornecedor = dados.get("id_fornecedor", d.id_fornecedor)
        id_natureza = dados.get("id_natureza", d.id_natureza)
        id_fonte_recursos = dados.get("id_fonte_recursos", d.id_fonte_recursos)
        id_conta = dados.get("id_conta", d.id_conta)
        id_contrato = dados.get("id_contrato", d.id_contrato)
    await _validar_refs(db, tenant_id=tenant_id, payload=_Ref)
    for k, v in dados.items():
        setattr(d, k, v)
    if parcelas_novas is not None:
        for p in await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id):
            p.excluido = True; p.atualizado_em = _utcnow()
        for p in payload.parcelas:
            db.add(Parcela(tenant_id=tenant_id, id_debito=d.id, numero=p.numero,
                           valor=p.valor, vencimento=p.vencimento, criado_em=_utcnow()))
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def excluir_debito(db: AsyncSession, *, tenant_id: int, debito_id: int) -> None:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    if d.status not in ("RASCUNHO", "REJEITADO", "CANCELADO"):
        raise PagamentoDebitoError("Só é possível excluir rascunhos/rejeitados/cancelados.",
                                   status.HTTP_409_CONFLICT)
    d.excluido = True; d.atualizado_em = _utcnow(); await db.commit()


async def nomes_fornecedores(db: AsyncSession, *, tenant_id: int, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = (await db.execute(select(Fornecedor.id, Fornecedor.nome).where(
        Fornecedor.tenant_id == tenant_id, Fornecedor.id.in_(ids)))).all()
    return {r[0]: r[1] for r in rows}


async def nomes_usuarios(db: AsyncSession, *, tenant_id: int, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = (await db.execute(select(Usuario.id, Usuario.nome).where(
        Usuario.tenant_id == tenant_id, Usuario.id.in_(ids)))).all()
    return {r[0]: r[1] for r in rows}


async def aprovadores_do_debito(db: AsyncSession, *, tenant_id: int, debito_id: int) -> set[int]:
    rows = (await db.execute(select(DebitoHistorico.id_usuario).where(
        DebitoHistorico.tenant_id == tenant_id, DebitoHistorico.id_debito == debito_id,
        DebitoHistorico.acao == "APROVADO"))).scalars().all()
    return {r for r in rows if r is not None}


def _exigir_status(d: Debito, *esperados: str) -> None:
    if d.status not in esperados:
        raise PagamentoDebitoError(
            f"Transição inválida: débito está '{d.status}' (esperado: {', '.join(esperados)}).",
            status.HTTP_409_CONFLICT)


async def enviar_aprovacao(db: AsyncSession, *, tenant_id: int, debito_id: int,
                           usuario_id: int, ip: str | None = None) -> Debito:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    _exigir_status(d, "RASCUNHO")
    parcelas = await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
    if not parcelas:
        raise PagamentoDebitoError("Débito sem parcelas.", status.HTTP_422_UNPROCESSABLE_ENTITY)
    soma = sum((p.valor for p in parcelas), Decimal("0"))
    if soma != d.valor_total:
        raise PagamentoDebitoError(
            f"Soma das parcelas ({soma}) difere do valor total ({d.valor_total}).",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    _registrar_transicao(db, debito=d, novo_status="AGUARDANDO_APROVACAO", acao="ENVIADO",
                         usuario_id=usuario_id, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def aprovar(db: AsyncSession, *, tenant_id: int, debito_id: int,
                  usuario_id: int, ip: str | None = None) -> Debito:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    _exigir_status(d, "AGUARDANDO_APROVACAO")
    if usuario_id == d.id_usuario_solicitante:
        raise PagamentoDebitoError("Segregação de funções: o solicitante não pode aprovar o próprio débito.",
                                   status.HTTP_403_FORBIDDEN)
    _registrar_transicao(db, debito=d, novo_status="APROVADO", acao="APROVADO",
                         usuario_id=usuario_id, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def devolver(db: AsyncSession, *, tenant_id: int, debito_id: int, usuario_id: int,
                   justificativa: str, ip: str | None = None) -> Debito:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    _exigir_status(d, "AGUARDANDO_APROVACAO")
    _registrar_transicao(db, debito=d, novo_status="RASCUNHO", acao="DEVOLVIDO",
                         usuario_id=usuario_id, justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def rejeitar(db: AsyncSession, *, tenant_id: int, debito_id: int, usuario_id: int,
                   justificativa: str, ip: str | None = None) -> Debito:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    _exigir_status(d, "AGUARDANDO_APROVACAO")
    _registrar_transicao(db, debito=d, novo_status="REJEITADO", acao="REJEITADO",
                         usuario_id=usuario_id, justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def cancelar(db: AsyncSession, *, tenant_id: int, debito_id: int, usuario_id: int,
                   justificativa: str, ip: str | None = None) -> Debito:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    _exigir_status(d, "RASCUNHO", "AGUARDANDO_APROVACAO", "APROVADO", "AUTORIZADO")
    parcelas = await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
    if any(p.status == "PAGA" for p in parcelas):
        raise PagamentoDebitoError("Débito com parcela paga não pode ser cancelado — estorne antes.",
                                   status.HTTP_409_CONFLICT)
    for p in parcelas:
        p.status = "CANCELADA"; p.atualizado_em = _utcnow()
    _registrar_transicao(db, debito=d, novo_status="CANCELADO", acao="CANCELADO",
                         usuario_id=usuario_id, justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def confirmar_liquidacao(db: AsyncSession, *, tenant_id: int, debito_id: int,
                               usuario_id: int, data_liquidacao=None, ip: str | None = None) -> Debito:
    """Confirma a liquidação (recebimento/atesto) — pré-requisito para autorizar
    (RF-VAL-02/RN-01). Permitido antes da autorização; não muda o status."""
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    _exigir_status(d, "RASCUNHO", "AGUARDANDO_APROVACAO", "APROVADO")
    d.liquidacao_confirmada = True
    d.data_liquidacao = data_liquidacao or _utcnow().date()
    db.add(DebitoHistorico(tenant_id=tenant_id, id_debito=d.id, status_anterior=d.status,
                           status_novo=d.status, acao="LIQUIDADO",
                           justificativa=f"Liquidação em {d.data_liquidacao.isoformat()}",
                           id_usuario=usuario_id, ip_origem=ip, criado_em=_utcnow()))
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def suspender(db: AsyncSession, *, tenant_id: int, debito_id: int, usuario_id: int,
                    justificativa: str, ip: str | None = None) -> Debito:
    """Tesouraria suspende um débito suspeito (RF-TES-06). APROVADO → SUSPENSO."""
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    _exigir_status(d, "AGUARDANDO_APROVACAO", "APROVADO")
    _registrar_transicao(db, debito=d, novo_status="SUSPENSO", acao="SUSPENSO",
                         usuario_id=usuario_id, justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def reativar(db: AsyncSession, *, tenant_id: int, debito_id: int, usuario_id: int,
                   justificativa: str | None = None, ip: str | None = None) -> Debito:
    """Reverte a suspensão: SUSPENSO → APROVADO."""
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    _exigir_status(d, "SUSPENSO")
    _registrar_transicao(db, debito=d, novo_status="APROVADO", acao="REATIVADO",
                         usuario_id=usuario_id, justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


def debito_out(d: Debito, *, nome_fornecedor: str) -> dict:
    return {
        "id": d.id, "id_fornecedor": d.id_fornecedor, "nome_fornecedor": nome_fornecedor,
        "id_natureza": d.id_natureza, "id_fonte_recursos": d.id_fonte_recursos,
        "id_conta": d.id_conta, "id_conta_pagadora": d.id_conta_pagadora,
        "id_contrato": d.id_contrato,
        "valor_total": d.valor_total, "competencia": d.competencia,
        "numero_ne": d.numero_ne, "numero_nf": d.numero_nf, "criticidade": d.criticidade,
        "urgente": d.urgente, "justificativa_urgencia": d.justificativa_urgencia,
        "descricao": d.descricao, "status": d.status,
        "id_usuario_solicitante": d.id_usuario_solicitante,
        "liquidacao_confirmada": d.liquidacao_confirmada, "data_liquidacao": d.data_liquidacao,
        "criado_em": d.criado_em, "atualizado_em": d.atualizado_em,
    }
