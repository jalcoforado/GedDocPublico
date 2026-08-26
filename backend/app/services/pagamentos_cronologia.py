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
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.pagamentos import (
    AnexoDebito, BloqueioSaldo, Contrato, Debito, ExcecaoCronologica, FonteRecursos, Fornecedor,
    Parcela, PedidoAjuste, PosicaoCronologica,
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


class OrdemCronologicaError(HTTPException):
    """409 — o débito tem gente na frente na fila cronológica (Ruling 5,
    F3 Task 5). O `detail` lista quem preteriu, legível para o operador."""
    def __init__(self, preteridos_: "list[PosicaoFilaItem]"):
        itens = "; ".join(
            f"débito #{i.id_debito} (posição {i.posicao}, {i.fornecedor_nome})"
            for i in preteridos_
        )
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ordem cronológica não respeitada. À frente na fila: {itens}",
        )


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


async def concluir_na_fila(db: AsyncSession, *, tenant_id: int,
                           id_debito: int) -> PosicaoCronologica | None:
    """Espelha a conclusão do pagamento (parcela integralmente paga) na
    posição da fila (situacao CONCLUIDA), quando ela existe. Não comita.

    Diferente de `reavaliar_debito`: CONCLUIDA não é um dos rótulos que
    `avaliar_elegibilidade` produz — é uma dimensão de execução (F4), então
    quem manda aqui é `pagar_parcela`, não a função pura."""
    posicao = await obter_posicao(db, tenant_id=tenant_id, id_debito=id_debito)
    if posicao is None:
        return None
    posicao.situacao = est.CONCLUIDA
    posicao.motivo_bloqueio = None
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


# ------------------------------------------------------------- elegibilidade
# Task 4 — a fila cronológica não muda só na liquidação (Task 2): qualquer
# evento que mude tramitação, fornecedor, saldo/bloqueio da conta pagadora ou
# exceção autorizada pode mudar a elegibilidade de um débito já na fila. Esta
# seção reavalia isso de forma síncrona, na mesma transação do evento.


def avaliar_elegibilidade(*, tramitacao: str, tem_pedido_aberto: bool,
                          fornecedor_regular: bool, disponivel_ok: bool,
                          tem_bloqueio: bool, tem_excecao: bool) -> tuple[str, str | None]:
    """Função PURA (sem IO) — o rótulo de fila que o débito deveria ter.

    Ordem de precedência (RULING F3): tramitação fora de AUTORIZADA vence tudo
    (a fila é irrelevante enquanto o rito não chegou lá); bloqueio de saldo
    vence pedido aberto, que vence fornecedor irregular, que vence
    indisponibilidade de saldo. `tem_excecao` só troca o rótulo de quem já
    teria chegado a ELEGIVEL — a exceção fura a ORDEM cronológica, não cura
    bloqueio, fornecedor irregular nem indisponibilidade de saldo.
    """
    if tramitacao != est.AUTORIZADA:
        return est.REGISTRADA, None
    if tem_bloqueio:
        return est.BLOQUEADA, "Bloqueio de saldo ativo na conta pagadora."
    if tem_pedido_aberto:
        return est.BLOQUEADA, "Pedido de ajuste em aberto sobre o débito."
    if not fornecedor_regular:
        return est.BLOQUEADA, "Fornecedor com situação cadastral irregular."
    if not disponivel_ok:
        return est.AGUARDANDO_DISPONIBILIDADE, "Saldo disponível insuficiente na conta pagadora."
    if tem_excecao:
        return est.EXCECAO_AUTORIZADA, None
    return est.ELEGIVEL, None


async def _tem_pedido_aberto(db: AsyncSession, *, tenant_id: int, debito_id: int) -> bool:
    stmt = select(func.count(PedidoAjuste.id)).where(
        PedidoAjuste.tenant_id == tenant_id, PedidoAjuste.id_debito == debito_id,
        PedidoAjuste.situacao == "ABERTO")
    return (await db.execute(stmt)).scalar_one() > 0


async def _tem_excecao(db: AsyncSession, *, tenant_id: int, debito_id: int) -> bool:
    stmt = select(func.count(ExcecaoCronologica.id)).where(
        ExcecaoCronologica.tenant_id == tenant_id, ExcecaoCronologica.id_debito == debito_id)
    return (await db.execute(stmt)).scalar_one() > 0


async def _fornecedor_regular(db: AsyncSession, *, tenant_id: int, fornecedor_id: int) -> bool:
    forn = (await db.execute(select(Fornecedor.situacao_cadastral).where(
        Fornecedor.tenant_id == tenant_id, Fornecedor.id == fornecedor_id,
    ))).scalar_one_or_none()
    return forn == "REGULAR"


async def _tem_bloqueio(db: AsyncSession, *, tenant_id: int, id_conta_pagadora: int) -> bool:
    hoje = date.today()
    stmt = select(func.count(BloqueioSaldo.id)).where(
        BloqueioSaldo.tenant_id == tenant_id, BloqueioSaldo.id_conta == id_conta_pagadora,
        BloqueioSaldo.ativo.is_(True), BloqueioSaldo.excluido.is_(False),
        BloqueioSaldo.periodo_inicio <= hoje,
        or_(BloqueioSaldo.periodo_fim.is_(None), BloqueioSaldo.periodo_fim >= hoje))
    return (await db.execute(stmt)).scalar_one() > 0


async def _disponivel_ok(db: AsyncSession, *, tenant_id: int, id_conta_pagadora: int,
                         debito_id: int) -> bool:
    """`saldo_conta().disponivel` já desconta o comprometido de TODOS os
    débitos com reserva ativa na conta — incluindo o próprio `debito_id`
    (ver `pagamentos_caixa.comprometido_conta`). Exigir `disponivel >=
    restante` sem somar essa reserva de volta cobraria o mesmo valor duas
    vezes (ruling do review, Task 4): um débito de valor V exigiria 2V livres
    para ficar ELEGIVEL. A reserva do próprio débito é exatamente a soma das
    parcelas dele ainda não pagas — o mesmo filtro que `comprometido_conta`
    usa (A_PAGAR/LIBERADA)."""
    from . import pagamentos_caixa as caixa

    saldo = await caixa.saldo_conta(db, tenant_id=tenant_id, conta_id=id_conta_pagadora)
    restante = (await db.execute(select(func.coalesce(func.sum(Parcela.valor), 0)).where(
        Parcela.tenant_id == tenant_id, Parcela.id_debito == debito_id,
        Parcela.excluido.is_(False), Parcela.status.in_(("A_PAGAR", "LIBERADA"))))).scalar_one()
    return (saldo.disponivel + restante) >= restante


async def _avaliar_fila_atual(db: AsyncSession, *, tenant_id: int, debito) -> tuple[str, str | None]:
    """Coleta os fatos correntes do débito (fornecedor, bloqueio, saldo,
    exceção) e devolve o rótulo de fila honesto via `avaliar_elegibilidade`
    (função pura). Compartilhado por `reavaliar_debito` e `registrar_excecao`
    — as duas precisam da MESMA precedência (BLOQUEADA/AGUARDANDO_
    DISPONIBILIDADE por cima de `tem_excecao`), senão a exceção mascararia um
    bloqueio real que nada tem a ver com ordem cronológica."""
    debito_id = debito.id
    tramitacao = debito.situacao_tramitacao

    tem_excecao = await _tem_excecao(db, tenant_id=tenant_id, debito_id=debito_id)
    tem_pedido_aberto = await _tem_pedido_aberto(db, tenant_id=tenant_id, debito_id=debito_id)

    if tramitacao == est.AUTORIZADA:
        fornecedor_regular = await _fornecedor_regular(
            db, tenant_id=tenant_id, fornecedor_id=debito.id_fornecedor)
        if debito.id_conta_pagadora is not None:
            tem_bloqueio = await _tem_bloqueio(
                db, tenant_id=tenant_id, id_conta_pagadora=debito.id_conta_pagadora)
            disponivel_ok = await _disponivel_ok(
                db, tenant_id=tenant_id, id_conta_pagadora=debito.id_conta_pagadora,
                debito_id=debito_id)
        else:
            # Autorizado sem conta pagadora definida (rito singular, sem lote):
            # nada a checar de saldo/bloqueio até a conta ser escolhida.
            tem_bloqueio, disponivel_ok = False, True
    else:
        fornecedor_regular, tem_bloqueio, disponivel_ok = True, False, True

    return avaliar_elegibilidade(
        tramitacao=tramitacao, tem_pedido_aberto=tem_pedido_aberto,
        fornecedor_regular=fornecedor_regular, disponivel_ok=disponivel_ok,
        tem_bloqueio=tem_bloqueio, tem_excecao=tem_excecao)


async def reavaliar_debito(db: AsyncSession, *, tenant_id: int, debito_id: int,
                           usuario_id: int | None = None) -> None:
    """Recalcula a elegibilidade de UM débito e, se mudou, aplica a transição
    (mesma transação do caller — não comita).

    Débito sem posição na fila, ou já em situação terminal (CONCLUIDA/
    RETIRADA), é no-op: a reavaliação só vale enquanto o débito ainda disputa
    a ordem cronológica.
    """
    posicao = await obter_posicao(db, tenant_id=tenant_id, id_debito=debito_id)
    if posicao is None or posicao.situacao in (est.CONCLUIDA, est.RETIRADA):
        return

    from . import pagamentos_debitos as deb

    debito = await deb.obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    novo_fila, motivo = await _avaliar_fila_atual(db, tenant_id=tenant_id, debito=debito)

    if novo_fila == posicao.situacao:
        return

    deb._registrar_transicao(db, debito=debito, acao="FILA_REAVALIADA",
                             usuario_id=usuario_id, fila=novo_fila, justificativa=motivo)
    posicao.situacao = novo_fila
    posicao.motivo_bloqueio = motivo
    posicao.atualizado_em = _utcnow()
    await db.flush()


async def reavaliar_por_fornecedor(db: AsyncSession, *, tenant_id: int,
                                   fornecedor_id: int) -> int:
    """Reavalia todos os débitos NÃO terminais desse fornecedor na fila.
    Devolve quantos foram considerados (percorridos)."""
    stmt = (select(PosicaoCronologica.id_debito)
            .join(Debito, (Debito.id == PosicaoCronologica.id_debito)
                  & (Debito.tenant_id == PosicaoCronologica.tenant_id))
            .where(PosicaoCronologica.tenant_id == tenant_id,
                   Debito.id_fornecedor == fornecedor_id,
                   PosicaoCronologica.situacao.notin_((est.CONCLUIDA, est.RETIRADA))))
    ids = [row[0] for row in (await db.execute(stmt)).all()]
    for debito_id in ids:
        await reavaliar_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    return len(ids)


async def reavaliar_por_conta(db: AsyncSession, *, tenant_id: int, conta_id: int) -> int:
    """Reavalia todos os débitos NÃO terminais cuja conta pagadora é `conta_id`.
    Devolve quantos foram considerados (percorridos)."""
    stmt = (select(PosicaoCronologica.id_debito)
            .join(Debito, (Debito.id == PosicaoCronologica.id_debito)
                  & (Debito.tenant_id == PosicaoCronologica.tenant_id))
            .where(PosicaoCronologica.tenant_id == tenant_id,
                   Debito.id_conta_pagadora == conta_id,
                   PosicaoCronologica.situacao.notin_((est.CONCLUIDA, est.RETIRADA))))
    ids = [row[0] for row in (await db.execute(stmt)).all()]
    for debito_id in ids:
        await reavaliar_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    return len(ids)


# ---------------------------------------------------------- ordem/exceção (Task 5)
# A guarda de ordem cronológica entra nos dois atos de seleção (liberar e
# pagar), ANTES de qualquer escrita: nenhum dos dois pode consumar a seleção
# de um débito que fura a fila sem exceção formal registrada.


async def preteridos(db: AsyncSession, *, tenant_id: int,
                     debito_id: int) -> list[PosicaoFilaItem]:
    """Débitos ELEGIVEL da MESMA chave `(id_unidade, id_fonte_recursos,
    categoria, exercicio)` com posição anterior à do débito informado
    (Ruling 5: `(marco_em, id)` menor). BLOQUEADA e AGUARDANDO_DISPONIBILIDADE
    à frente NÃO contam — só quem já está apto a ser pago fura a ordem.

    Reaproveita `listar_fila` (mesma numeração de posição exibida na tela) em
    vez de recalcular o `row_number()` sobre um subconjunto filtrado, o que
    daria posições erradas (a posição é relativa ao grupo INTEIRO, não só aos
    preteridos).
    """
    posicao = await obter_posicao(db, tenant_id=tenant_id, id_debito=debito_id)
    if posicao is None:
        return []

    grupos = await listar_fila(
        db, tenant_id=tenant_id, id_fonte=posicao.id_fonte_recursos,
        id_unidade=posicao.id_unidade, categoria=posicao.categoria,
        exercicio=posicao.exercicio, incluir_concluidas=False,
    )
    if not grupos:
        return []
    itens = grupos[0].itens
    alvo = next((i for i in itens if i.id_debito == debito_id), None)
    if alvo is None:
        return []
    return [i for i in itens if i.situacao == est.ELEGIVEL and i.posicao < alvo.posicao]


async def assert_ordem_respeitada(db: AsyncSession, *, tenant_id: int, debito_id: int) -> None:
    """Guarda de ordem cronológica (F3, Task 5, Ruling 5). Levanta
    `OrdemCronologicaError` (409) se houver débito ELEGIVEL à frente na
    mesma fila.

    Dois no-ops DELIBERADOS:
    - débito SEM posição na fila (legado, nunca liquidado por este fluxo) —
      a fila só governa quem está nela, não é retroativa;
    - `EXCECAO_AUTORIZADA` — é o furo formal já registrado por
      `registrar_excecao`, exatamente o que destrava este caso.
    """
    posicao = await obter_posicao(db, tenant_id=tenant_id, id_debito=debito_id)
    if posicao is None or posicao.situacao == est.EXCECAO_AUTORIZADA:
        return
    pretere = await preteridos(db, tenant_id=tenant_id, debito_id=debito_id)
    if pretere:
        raise OrdemCronologicaError(pretere)


async def registrar_excecao(db: AsyncSession, *, tenant_id: int, debito_id: int,
                            usuario_id: int, justificativa: str, fundamento: str,
                            data_autorizacao: date,
                            documentos: list[int] | None = None) -> ExcecaoCronologica:
    """Registra o furo formal de ordem cronológica (LRF/lei de licitações),
    append-only (migration 0107). Espelha `EXCECAO_AUTORIZADA` na posição e no
    débito (mesmo padrão de `reavaliar_debito`) e grava o histórico. Não
    comita — participa da transação do caller (o router faz o `audit.log` e
    o commit).

    `debito_id` sem posição → 404 (não há fila para furar); posição já
    terminal (`CONCLUIDA`/`RETIRADA`) → 409 (a seleção já aconteceu ou o
    débito saiu do jogo).
    """
    posicao = await obter_posicao(db, tenant_id=tenant_id, id_debito=debito_id)
    if posicao is None:
        raise PagamentoCronologiaError(
            "Débito não tem posição na fila cronológica.", status.HTTP_404_NOT_FOUND)
    if posicao.situacao in (est.CONCLUIDA, est.RETIRADA):
        raise PagamentoCronologiaError(
            f"Débito já está '{posicao.situacao}' — exceção cronológica não se aplica.",
            status.HTTP_409_CONFLICT)

    if documentos:
        vinculados = set((await db.execute(select(AnexoDebito.id).where(
            AnexoDebito.tenant_id == tenant_id, AnexoDebito.id_debito == debito_id,
            AnexoDebito.id.in_(documentos), AnexoDebito.excluido.is_(False),
        ))).scalars().all())
        faltando = sorted(set(documentos) - vinculados)
        if faltando:
            raise PagamentoCronologiaError(
                f"Documento(s) {faltando} não vinculado(s) a este débito.",
                status.HTTP_422_UNPROCESSABLE_ENTITY)

    agora = _utcnow()
    excecao = ExcecaoCronologica(
        tenant_id=tenant_id, id_debito=debito_id, justificativa=justificativa,
        fundamento=fundamento, id_autoridade=usuario_id, data_autorizacao=data_autorizacao,
        id_usuario_registro=usuario_id,
        documentos={"anexo_debito_ids": documentos} if documentos else None,
        criado_em=agora,
    )
    db.add(excecao)
    await db.flush()

    from . import pagamentos_debitos as deb

    debito = await deb.obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    # A exceção fura ORDEM cronológica, não cura bloqueio de saldo, fornecedor
    # irregular nem indisponibilidade (mesma precedência de `avaliar_
    # elegibilidade` — `tem_excecao` só troca o rótulo de quem JÁ chegaria a
    # ELEGIVEL). Por isso a fila gravada aqui vem de `_avaliar_fila_atual`
    # (que já enxerga esta exceção recém-criada via `_tem_excecao`), nunca de
    # `EXCECAO_AUTORIZADA` hardcoded — senão a exceção mascararia um bloqueio
    # real que nada tem a ver com ordem cronológica.
    novo_fila, motivo = await _avaliar_fila_atual(db, tenant_id=tenant_id, debito=debito)
    deb._registrar_transicao(
        db, debito=debito, acao="EXCECAO_AUTORIZADA", usuario_id=usuario_id,
        fila=novo_fila, justificativa=justificativa)
    posicao.situacao = novo_fila
    posicao.motivo_bloqueio = motivo
    posicao.atualizado_em = agora
    await db.flush()
    return excecao
