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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.pagamentos import (
    Contrato, Debito, ExcecaoCronologica, FonteRecursos, Fornecedor, PosicaoCronologica,
)
from ..models.unidade_trabalho import UnidadeTrabalho
from ..schemas.pagamentos import (
    ExcecaoCronologicaOut, FilaCronologicaGrupo, PosicaoDebitoOut, PosicaoFilaItem,
)
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


async def listar_fila(db: AsyncSession, *, tenant_id: int, id_fonte: int | None = None,
                      id_unidade: int | None = None, categoria: str | None = None,
                      exercicio: int | None = None,
                      incluir_concluidas: bool = False) -> list[FilaCronologicaGrupo]:
    """Fila cronológica agrupada pela chave `(id_unidade, id_fonte_recursos,
    categoria, exercicio)`. A `posicao` de cada item é calculada por
    `row_number()` na própria consulta — nunca gravada em tabela: reordenar a
    fila é só uma questão de `marco_em` mudar, sem UPDATE nenhum de posição.

    Por padrão exclui `RETIRADA`/`CONCLUIDA` (a fila operacional só mostra o
    que ainda está em jogo); `incluir_concluidas=True` traz tudo, para
    auditoria.
    """
    rn = func.row_number().over(
        partition_by=(
            PosicaoCronologica.id_unidade, PosicaoCronologica.id_fonte_recursos,
            PosicaoCronologica.categoria, PosicaoCronologica.exercicio,
        ),
        order_by=(PosicaoCronologica.marco_em, PosicaoCronologica.id),
    ).label("posicao")

    tem_excecao = (
        select(func.count(ExcecaoCronologica.id))
        .where(
            ExcecaoCronologica.tenant_id == PosicaoCronologica.tenant_id,
            ExcecaoCronologica.id_debito == PosicaoCronologica.id_debito,
        )
        .correlate(PosicaoCronologica)
        .scalar_subquery()
    )

    stmt = (
        select(
            PosicaoCronologica, rn, Debito.descricao, Debito.valor_total,
            Fornecedor.nome, UnidadeTrabalho.unidade_trabalho, FonteRecursos.descricao,
            tem_excecao,
        )
        .join(Debito, (Debito.id == PosicaoCronologica.id_debito)
              & (Debito.tenant_id == PosicaoCronologica.tenant_id))
        .join(Fornecedor, (Fornecedor.id == Debito.id_fornecedor)
              & (Fornecedor.tenant_id == Debito.tenant_id))
        .join(UnidadeTrabalho, (UnidadeTrabalho.id == PosicaoCronologica.id_unidade)
              & (UnidadeTrabalho.tenant_id == PosicaoCronologica.tenant_id))
        .join(FonteRecursos, (FonteRecursos.id == PosicaoCronologica.id_fonte_recursos)
              & (FonteRecursos.tenant_id == PosicaoCronologica.tenant_id))
        .where(PosicaoCronologica.tenant_id == tenant_id)
    )
    if not incluir_concluidas:
        stmt = stmt.where(PosicaoCronologica.situacao.notin_((est.RETIRADA, est.CONCLUIDA)))
    if id_fonte is not None:
        stmt = stmt.where(PosicaoCronologica.id_fonte_recursos == id_fonte)
    if id_unidade is not None:
        stmt = stmt.where(PosicaoCronologica.id_unidade == id_unidade)
    if categoria is not None:
        stmt = stmt.where(PosicaoCronologica.categoria == categoria)
    if exercicio is not None:
        stmt = stmt.where(PosicaoCronologica.exercicio == exercicio)

    stmt = stmt.order_by(
        PosicaoCronologica.id_unidade, PosicaoCronologica.id_fonte_recursos,
        PosicaoCronologica.categoria, PosicaoCronologica.exercicio,
        PosicaoCronologica.marco_em, PosicaoCronologica.id,
    )

    linhas = (await db.execute(stmt)).all()

    grupos: dict[tuple, FilaCronologicaGrupo] = {}
    ordem: list[tuple] = []
    for (posicao, num, descricao, valor_total, fornecedor_nome, unidade_nome,
         fonte_nome, qtd_excecoes) in linhas:
        chave = (posicao.id_unidade, posicao.id_fonte_recursos, posicao.categoria,
                 posicao.exercicio)
        if chave not in grupos:
            grupos[chave] = FilaCronologicaGrupo(
                id_unidade=posicao.id_unidade, unidade_nome=unidade_nome,
                id_fonte_recursos=posicao.id_fonte_recursos, fonte_nome=fonte_nome,
                categoria=posicao.categoria, exercicio=posicao.exercicio, itens=[],
            )
            ordem.append(chave)
        grupos[chave].itens.append(PosicaoFilaItem(
            posicao=num, id_debito=posicao.id_debito, fornecedor_nome=fornecedor_nome,
            descricao=descricao, valor_total=valor_total, marco_em=posicao.marco_em,
            situacao=posicao.situacao, motivo_bloqueio=posicao.motivo_bloqueio,
            previsao_pagamento=posicao.previsao_pagamento, tem_excecao=qtd_excecoes > 0,
        ))
    return [grupos[chave] for chave in ordem]


async def posicao_do_debito(db: AsyncSession, *, tenant_id: int,
                            debito_id: int) -> PosicaoDebitoOut | None:
    """Posição do débito no grupo dele + total do grupo + exceções.

    `None` quando o débito não tem posição registrada (o caller devolve 404 —
    não é este módulo que decide o código HTTP).
    """
    posicao = await obter_posicao(db, tenant_id=tenant_id, id_debito=debito_id)
    if posicao is None:
        return None

    incluir_concluidas = posicao.situacao in (est.RETIRADA, est.CONCLUIDA)
    grupos = await listar_fila(
        db, tenant_id=tenant_id, id_fonte=posicao.id_fonte_recursos,
        id_unidade=posicao.id_unidade, categoria=posicao.categoria,
        exercicio=posicao.exercicio, incluir_concluidas=incluir_concluidas,
    )
    grupo = grupos[0] if grupos else None
    item = next((i for i in grupo.itens if i.id_debito == debito_id), None) if grupo else None
    if item is None:
        return None

    excecoes = (await db.execute(select(ExcecaoCronologica).where(
        ExcecaoCronologica.tenant_id == tenant_id,
        ExcecaoCronologica.id_debito == debito_id,
    ).order_by(ExcecaoCronologica.criado_em))).scalars().all()

    return PosicaoDebitoOut(
        posicao=item.posicao, total_grupo=len(grupo.itens), situacao=item.situacao,
        motivo_bloqueio=item.motivo_bloqueio, marco_em=item.marco_em,
        excecoes=[ExcecaoCronologicaOut.model_validate(e) for e in excecoes],
    )
