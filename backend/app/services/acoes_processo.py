"""Ações de tramitação: encaminhar, receber, cancelar encaminhamento.

Espelha o fluxo de aprimora/app/models/Processo.php:
- Encaminhar (flag ENCAMINHAMENTO): cria movimentação + encaminhamento + despacho opcional.
  id_local_atual NÃO muda no encaminhamento — o processo continua "fisicamente"
  na unidade de origem até o destinatário confirmar o recebimento.
- Receber (flag RECEBIMENTO): marca o encaminhamento pendente como recebido,
  cria nova movimentação, e SÓ ENTÃO atualiza id_local_atual.
- Cancelar (sem flag dedicada — usa registro lógico): só permite cancelar
  encaminhamento ainda não recebido. Mantém histórico (não deleta).
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Acao, Despacho, Encaminhamento, Movimentacao, Processo
from ..schemas.processo import CancelarEncaminhamentoRequest, EncaminharRequest


class AcaoError(Exception):
    pass


async def _get_acao(db: AsyncSession, flag: str) -> Acao:
    acao = (
        await db.execute(
            select(Acao).where(
                Acao.flag == flag,
                Acao.excluido.is_(False),
                Acao.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if acao is None:
        raise AcaoError(f"Ação '{flag}' não cadastrada em protocolos.acao")
    return acao


async def _get_processo(db: AsyncSession, processo_id: int) -> Processo:
    p = (
        await db.execute(
            select(Processo).where(
                Processo.id == processo_id, Processo.excluido.is_(False)
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise AcaoError(f"Processo {processo_id} não encontrado")
    if not p.ativo:
        raise AcaoError("Processo inativo — não permite movimentação")
    return p


async def encaminhar(
    db: AsyncSession,
    processo_id: int,
    payload: EncaminharRequest,
    *,
    usuario_id: int,
) -> Encaminhamento:
    processo = await _get_processo(db, processo_id)

    # Bloqueia se há encaminhamento pendente (não recebido e não cancelado).
    pendente = (
        await db.execute(
            select(Encaminhamento).where(
                Encaminhamento.id_processo == processo_id,
                Encaminhamento.excluido.is_(False),
                Encaminhamento.recebido.is_(False),
                Encaminhamento.cancelado.is_(False),
            )
        )
    ).scalar_one_or_none()
    if pendente:
        raise AcaoError(
            "Já existe encaminhamento pendente. Cancele-o ou aguarde o recebimento."
        )

    acao = await _get_acao(db, "ENCAMINHAMENTO")
    now = datetime.now()
    unidade_origem = processo.id_local_atual or processo.id_unidade_proprietaria

    movimentacao = Movimentacao(
        id_processo=processo_id,
        id_unidade_responsavel=unidade_origem,
        id_acao=acao.id,
        id_usuario=usuario_id,
        data_hora_movimentacao=now,
        ativo=True,
        excluido=False,
    )
    db.add(movimentacao)
    await db.flush()

    encaminhamento = Encaminhamento(
        id_processo=processo_id,
        id_unidade_origem=unidade_origem,
        id_unidade_destino=payload.id_unidade_destino,
        id_prioridade=payload.id_prioridade,
        quantidade_folhas=payload.quantidade_folhas,
        data_prazo=payload.data_prazo,
        externo=False,
        recebido=False,
        cancelado=False,
        id_usuario=usuario_id,
        id_movimentacao=movimentacao.id,
        ativo=True,
        excluido=False,
    )
    db.add(encaminhamento)

    if payload.despacho:
        db.add(
            Despacho(
                id_processo=processo_id,
                despacho=payload.despacho,
                id_usuario=usuario_id,
                id_movimentacao=movimentacao.id,
                ativo=True,
                excluido=False,
            )
        )

    movimentacao.id_encaminhamento = None  # ligação inversa é via encaminhamento.id_movimentacao
    processo.id_ultima_movimentacao = movimentacao.id

    await db.commit()
    await db.refresh(encaminhamento)
    return encaminhamento


async def receber(
    db: AsyncSession,
    processo_id: int,
    *,
    usuario_id: int,
) -> Encaminhamento:
    processo = await _get_processo(db, processo_id)

    enc = (
        await db.execute(
            select(Encaminhamento)
            .where(
                Encaminhamento.id_processo == processo_id,
                Encaminhamento.excluido.is_(False),
                Encaminhamento.recebido.is_(False),
                Encaminhamento.cancelado.is_(False),
            )
            .order_by(Encaminhamento.id.desc())
        )
    ).scalar_one_or_none()
    if enc is None:
        raise AcaoError("Nenhum encaminhamento pendente para este processo")

    acao = await _get_acao(db, "RECEBIMENTO")
    now = datetime.now()

    enc.recebido = True
    enc.data_hora_recebimento = now

    movimentacao = Movimentacao(
        id_processo=processo_id,
        id_unidade_responsavel=enc.id_unidade_destino,
        id_acao=acao.id,
        id_usuario=usuario_id,
        id_encaminhamento=enc.id,
        data_hora_movimentacao=now,
        ativo=True,
        excluido=False,
    )
    db.add(movimentacao)
    await db.flush()

    # Só aqui o processo "muda de lugar".
    processo.id_local_atual = enc.id_unidade_destino
    processo.id_ultima_movimentacao = movimentacao.id

    await db.commit()
    await db.refresh(enc)
    return enc


async def cancelar_encaminhamento(
    db: AsyncSession,
    encaminhamento_id: int,
    payload: CancelarEncaminhamentoRequest,
    *,
    usuario_id: int,
) -> Encaminhamento:
    enc = (
        await db.execute(
            select(Encaminhamento).where(
                Encaminhamento.id == encaminhamento_id,
                Encaminhamento.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if enc is None:
        raise AcaoError(f"Encaminhamento {encaminhamento_id} não encontrado")
    if enc.recebido:
        raise AcaoError("Não pode cancelar encaminhamento já recebido")
    if enc.cancelado:
        raise AcaoError("Encaminhamento já estava cancelado")

    enc.cancelado = True
    # Mantém id_local_atual onde estava (origem) — encaminhamento não chegou a mudar.

    if payload.despacho:
        db.add(
            Despacho(
                id_processo=enc.id_processo,
                despacho=f"[Cancelamento de encaminhamento] {payload.despacho}",
                id_usuario=usuario_id,
                id_movimentacao=enc.id_movimentacao,
                ativo=True,
                excluido=False,
            )
        )

    await db.commit()
    await db.refresh(enc)
    return enc
