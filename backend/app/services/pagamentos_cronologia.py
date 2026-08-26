"""Fila cronológica de pagamentos (F3, spec §4.3/§4.4) — Task 2: registro do
marco na liquidação.

A fila obedece à ordem de chegada dentro do grupo `(id_unidade,
id_fonte_recursos, categoria, exercicio)` — o "marco" é `marco_em`, a data em
que o débito entra na fila (a data de liquidação, com a hora da confirmação
para desempatar dois débitos liquidados no mesmo dia). Este módulo não
comita: participa da transação do caller (`services/pagamentos_debitos.py`).

`categoria_do_debito` resolve de onde vem a classificação: débito COM
contrato usa a do contrato (`Contrato.categoria`); débito SEM contrato usa a
própria (`Debito.categoria`, migration 0108) — é o campo que a solicitação
preenche quando não há contrato para carregar essa informação.
"""
from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.pagamentos import Contrato, Debito, PosicaoCronologica
from . import pagamentos_estados as est

CATEGORIAS = ("BENS", "LOCACOES", "SERVICOS", "OBRAS")


class PagamentoCronologiaError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_422_UNPROCESSABLE_ENTITY):
        super().__init__(status_code=code, detail=detail)


def _utcnow() -> datetime:
    return datetime.utcnow()


def categoria_do_debito(debito: Debito, contrato: Contrato | None) -> str | None:
    """`contrato.categoria` se houver contrato, senão `debito.categoria`."""
    if contrato is not None:
        return contrato.categoria
    return debito.categoria


async def obter_contrato(db: AsyncSession, *, tenant_id: int,
                          id_contrato: int | None) -> Contrato | None:
    if id_contrato is None:
        return None
    return (await db.execute(select(Contrato).where(
        Contrato.tenant_id == tenant_id, Contrato.id == id_contrato,
    ))).scalar_one_or_none()


async def obter_posicao(db: AsyncSession, *, tenant_id: int,
                         id_debito: int) -> PosicaoCronologica | None:
    return (await db.execute(select(PosicaoCronologica).where(
        PosicaoCronologica.tenant_id == tenant_id,
        PosicaoCronologica.id_debito == id_debito,
    ))).scalar_one_or_none()


async def registrar_na_fila(db: AsyncSession, *, tenant_id: int, debito: Debito,
                            data_liquidacao: date) -> PosicaoCronologica:
    """Cria a posição do débito na fila cronológica.

    Idempotente: se já existe posição para o débito, devolve a existente SEM
    alterar o marco — é o que garante que confirmar a liquidação de novo (ou
    reliquidar) não empurra o débito para o fim da fila.

    Não comita — participa da transação do caller.
    """
    existente = await obter_posicao(db, tenant_id=tenant_id, id_debito=debito.id)
    if existente is not None:
        return existente

    contrato = await obter_contrato(db, tenant_id=tenant_id, id_contrato=debito.id_contrato)
    categoria = categoria_do_debito(debito, contrato)
    if categoria is None:
        raise PagamentoCronologiaError(
            "Débito sem contrato precisa de categoria para entrar na fila cronológica.")

    agora = _utcnow()
    marco_em = datetime.combine(data_liquidacao, agora.time())
    posicao = PosicaoCronologica(
        tenant_id=tenant_id, id_debito=debito.id, id_unidade=debito.id_unidade,
        id_fonte_recursos=debito.id_fonte_recursos, categoria=categoria,
        exercicio=data_liquidacao.year, marco_em=marco_em, situacao=est.REGISTRADA,
        registrado_em=agora, atualizado_em=agora,
    )
    db.add(posicao)
    await db.flush()
    return posicao


async def regravar_marco(db: AsyncSession, *, tenant_id: int, debito: Debito,
                         data_liquidacao_nova: date) -> PosicaoCronologica:
    """Atualiza `marco_em`/`exercicio` da posição existente para a nova data
    de liquidação. O caller registra o histórico `MARCO_REGRAVADO` — este
    módulo só mexe em `posicao_cronologica`, não em `debito_historico`.

    Não comita — participa da transação do caller.
    """
    posicao = await obter_posicao(db, tenant_id=tenant_id, id_debito=debito.id)
    if posicao is None:
        raise PagamentoCronologiaError(
            "Débito ainda não tem posição na fila cronológica.",
            status.HTTP_409_CONFLICT)
    agora = _utcnow()
    posicao.marco_em = datetime.combine(data_liquidacao_nova, agora.time())
    posicao.exercicio = data_liquidacao_nova.year
    posicao.atualizado_em = agora
    await db.flush()
    return posicao


async def retirar_da_fila(db: AsyncSession, *, tenant_id: int,
                          id_debito: int) -> PosicaoCronologica | None:
    """Espelha o cancelamento do débito na posição da fila (situacao
    RETIRADA), quando ela existe. Não comita."""
    posicao = await obter_posicao(db, tenant_id=tenant_id, id_debito=id_debito)
    if posicao is None:
        return None
    posicao.situacao = est.RETIRADA
    posicao.atualizado_em = _utcnow()
    await db.flush()
    return posicao
