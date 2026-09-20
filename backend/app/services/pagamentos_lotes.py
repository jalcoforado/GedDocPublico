"""Execução em lote (F4, spec §4.3, §7.6). `LotePagamento` é o artefato da
EXECUÇÃO — não confundir com `OrdemPagamento`, artefato da AUTORIZAÇÃO (spec
premissa 7, "ordem_pagamento não vira lote"). Máquina de estados:
`RASCUNHO -> PROGRAMADO -> ENVIADO -> PROCESSADO`, com `CANCELADO` alcançável
de `RASCUNHO`/`PROGRAMADO` — depois de `ENVIADO`, só o retorno resolve
(Task 5: `processar_retorno`, `anexar_comprovante`).

Uma parcela só entra num lote a partir de `LIBERADA` (F1/F3 continuam sendo o
gate de autorização de tesouraria — o lote é só o agrupamento de execução), e
só uma linha ATIVA por parcela por vez (`situacao <> 'FALHOU'`, mesmo
critério do UNIQUE parcial da migration 0121).

`pagar_parcela`/`estornar_parcela` avulsos (`pagamentos_autorizacao.py`)
continuam existindo para pagamento fora do rito de lote (correção pontual,
estorno) — o lote é o caminho recomendado, não o único fisicamente possível.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ContaBancaria, Debito, DebitoHistorico, LotePagamento, LotePagamentoParcela, Parcela
from . import pagamentos_cronologia as cron
from . import pagamentos_estados as est
from .pagamentos_debitos import PagamentoDebitoError, _registrar_transicao, obter_debito
from .pagamentos_guardas import SegregacaoError, assert_segregacao


def _utcnow() -> datetime:
    return datetime.utcnow()


def _registrar_evento_lote(db, *, debito: Debito, acao: str, usuario_id: int,
                           justificativa: str) -> None:
    """Linha de histórico ligada a um evento de LOTE que não muda nenhuma das
    três dimensões do débito (a mudança de dimensão, quando houver, é feita
    por `_registrar_transicao` nas Tasks 4/5) — mesmo padrão de
    `revogar_liberacao` em `pagamentos_autorizacao.py`."""
    db.add(DebitoHistorico(
        tenant_id=debito.tenant_id, id_debito=debito.id,
        status_anterior=debito.status, status_novo=debito.status, acao=acao,
        justificativa=justificativa, id_usuario=usuario_id, criado_em=_utcnow(),
        versao_debito=debito.versao,
    ))


async def _proximo_numero_lote(db, *, tenant_id: int) -> str:
    ano = _utcnow().year
    prefixo = f"L-{ano}-"
    ultimo = (await db.execute(select(func.max(LotePagamento.numero)).where(
        LotePagamento.tenant_id == tenant_id,
        LotePagamento.numero.like(f"{prefixo}%")))).scalar_one_or_none()
    seq = int(ultimo.rsplit("-", 1)[1]) + 1 if ultimo else 1
    return f"{prefixo}{seq:04d}"


async def _obter_conta_pagadora(db, *, tenant_id: int, conta_id: int) -> ContaBancaria:
    c = (await db.execute(select(ContaBancaria).where(
        ContaBancaria.id == conta_id, ContaBancaria.tenant_id == tenant_id,
        ContaBancaria.excluido.is_(False)))).scalar_one_or_none()
    if c is None:
        raise PagamentoDebitoError("Conta pagadora não encontrada.", status.HTTP_404_NOT_FOUND)
    return c


async def obter_lote(db: AsyncSession, *, tenant_id: int, lote_id: int,
                     for_update: bool = False) -> LotePagamento:
    stmt = select(LotePagamento).where(
        LotePagamento.id == lote_id, LotePagamento.tenant_id == tenant_id)
    if for_update:
        stmt = stmt.with_for_update()
    lote = (await db.execute(stmt)).scalar_one_or_none()
    if lote is None:
        raise PagamentoDebitoError("Lote não encontrado.", status.HTTP_404_NOT_FOUND)
    return lote


async def listar_lotes(db: AsyncSession, *, tenant_id: int,
                       situacao: str | None = None) -> list[LotePagamento]:
    stmt = select(LotePagamento).where(LotePagamento.tenant_id == tenant_id)
    if situacao is not None:
        stmt = stmt.where(LotePagamento.situacao == situacao)
    return list((await db.execute(stmt.order_by(LotePagamento.id.desc()))).scalars().all())


async def parcelas_do_lote(db: AsyncSession, *, tenant_id: int, lote_id: int) -> list[LotePagamentoParcela]:
    stmt = select(LotePagamentoParcela).where(
        LotePagamentoParcela.tenant_id == tenant_id, LotePagamentoParcela.id_lote == lote_id,
    ).order_by(LotePagamentoParcela.id)
    return list((await db.execute(stmt)).scalars().all())


async def parcelas_elegiveis_para_lote(db: AsyncSession, *, tenant_id: int,
                                       id_conta_pagadora: int | None = None) -> list[Parcela]:
    """Parcelas `LIBERADA`, sem linha ativa em `lote_pagamento_parcela`
    (mesmo critério do UNIQUE parcial: `situacao <> 'FALHOU'`), opcionalmente
    filtradas por conta pagadora do débito."""
    ativas = select(LotePagamentoParcela.id_parcela).where(
        LotePagamentoParcela.tenant_id == tenant_id,
        LotePagamentoParcela.situacao != "FALHOU",
    )
    stmt = select(Parcela).where(
        Parcela.tenant_id == tenant_id, Parcela.status == "LIBERADA",
        Parcela.excluido.is_(False), Parcela.id.not_in(ativas),
    )
    if id_conta_pagadora is not None:
        stmt = stmt.join(Debito, Debito.id == Parcela.id_debito).where(
            Debito.id_conta_pagadora == id_conta_pagadora)
    return list((await db.execute(
        stmt.order_by(Parcela.data_prevista_pagamento, Parcela.vencimento))).scalars().all())


async def _validar_parcelas_para_lote(db: AsyncSession, *, tenant_id: int,
                                      parcela_ids: list[int],
                                      id_conta_pagadora: int) -> tuple[
                                          dict[int, Parcela], dict[int, Debito], list[int]]:
    """Carrega e valida (com lock) parcelas candidatas a um lote — nova
    criação ou acréscimo a um `RASCUNHO` existente. All-or-nothing: qualquer
    parcela inválida barra o lote inteiro, nada é gravado."""
    if len(set(parcela_ids)) != len(parcela_ids):
        raise PagamentoDebitoError("Parcela repetida na lista.", status.HTTP_422_UNPROCESSABLE_ENTITY)
    parcelas_por_id: dict[int, Parcela] = {}
    debitos_por_id: dict[int, Debito] = {}
    ordem_debitos: list[int] = []
    for pid in parcela_ids:
        p = (await db.execute(select(Parcela).where(
            Parcela.id == pid, Parcela.tenant_id == tenant_id, Parcela.excluido.is_(False),
        ).with_for_update())).scalar_one_or_none()
        if p is None:
            raise PagamentoDebitoError(f"Parcela {pid} não encontrada.", status.HTTP_404_NOT_FOUND)
        if p.status != "LIBERADA":
            raise PagamentoDebitoError(
                f"Parcela {pid} não está liberada (está '{p.status}').", status.HTTP_409_CONFLICT)
        ativa = (await db.execute(select(LotePagamentoParcela.id).where(
            LotePagamentoParcela.tenant_id == tenant_id, LotePagamentoParcela.id_parcela == pid,
            LotePagamentoParcela.situacao != "FALHOU"))).scalar_one_or_none()
        if ativa is not None:
            raise PagamentoDebitoError(
                f"Parcela {pid} já está em outro lote ativo.", status.HTTP_409_CONFLICT)
        d = debitos_por_id.get(p.id_debito)
        if d is None:
            d = await obter_debito(db, tenant_id=tenant_id, debito_id=p.id_debito, for_update=True)
            if d.id_conta_pagadora != id_conta_pagadora:
                raise PagamentoDebitoError(
                    f"Débito {d.id} não pertence à conta pagadora {id_conta_pagadora} deste lote "
                    "— um lote é sempre de uma única conta pagadora.",
                    status.HTTP_422_UNPROCESSABLE_ENTITY)
            debitos_por_id[d.id] = d
            ordem_debitos.append(d.id)
        parcelas_por_id[pid] = p
    return parcelas_por_id, debitos_por_id, ordem_debitos


async def criar_lote(db: AsyncSession, *, tenant_id: int, id_conta_pagadora: int,
                     parcela_ids: list[int], usuario_id: int) -> LotePagamento:
    if not parcela_ids:
        raise PagamentoDebitoError(
            "Lote precisa de ao menos uma parcela.", status.HTTP_422_UNPROCESSABLE_ENTITY)
    await _obter_conta_pagadora(db, tenant_id=tenant_id, conta_id=id_conta_pagadora)

    parcelas_por_id, debitos_por_id, ordem_debitos = await _validar_parcelas_para_lote(
        db, tenant_id=tenant_id, parcela_ids=parcela_ids, id_conta_pagadora=id_conta_pagadora)

    # Ordem cronológica (F3) débito a débito, na ordem de primeira aparição —
    # mesmo padrão de `liberar_parcelas`: um débito anterior do MESMO lote já
    # conta como cumprido para o próximo.
    for d_id in ordem_debitos:
        await cron.assert_ordem_respeitada(db, tenant_id=tenant_id, debito_id=d_id)

    valor_total = sum((parcelas_por_id[pid].valor for pid in parcela_ids), Decimal("0"))
    lote = LotePagamento(
        tenant_id=tenant_id, numero=await _proximo_numero_lote(db, tenant_id=tenant_id),
        id_conta_pagadora=id_conta_pagadora, situacao="RASCUNHO", valor_total=valor_total,
        id_usuario=usuario_id, criado_em=_utcnow(),
    )
    db.add(lote)
    await db.flush()
    for pid in parcela_ids:
        db.add(LotePagamentoParcela(
            tenant_id=tenant_id, id_lote=lote.id, id_parcela=pid,
            situacao="PENDENTE", criado_em=_utcnow(),
        ))
    for d_id in ordem_debitos:
        _registrar_evento_lote(db, debito=debitos_por_id[d_id], acao="LOTE_CRIADO",
                               usuario_id=usuario_id, justificativa=f"Lote {lote.numero}")
    await db.commit()
    await db.refresh(lote)
    return lote


async def adicionar_parcela(db: AsyncSession, *, tenant_id: int, lote_id: int,
                            parcela_id: int) -> LotePagamento:
    lote = await obter_lote(db, tenant_id=tenant_id, lote_id=lote_id, for_update=True)
    if lote.situacao != "RASCUNHO":
        raise PagamentoDebitoError(
            f"Lote não está em rascunho (está '{lote.situacao}') — não aceita mais parcelas.",
            status.HTTP_409_CONFLICT)
    parcelas_por_id, debitos_por_id, ordem_debitos = await _validar_parcelas_para_lote(
        db, tenant_id=tenant_id, parcela_ids=[parcela_id], id_conta_pagadora=lote.id_conta_pagadora)
    for d_id in ordem_debitos:
        await cron.assert_ordem_respeitada(db, tenant_id=tenant_id, debito_id=d_id)

    db.add(LotePagamentoParcela(
        tenant_id=tenant_id, id_lote=lote.id, id_parcela=parcela_id,
        situacao="PENDENTE", criado_em=_utcnow(),
    ))
    lote.valor_total = lote.valor_total + parcelas_por_id[parcela_id].valor
    lote.atualizado_em = _utcnow()
    # Sem linha em debito_historico: acréscimo/remoção de parcela num lote
    # ainda em RASCUNHO é edição de rascunho, não evento auditável do rito —
    # o que entra na trilha é o ciclo de vida do lote em si (criar/programar/
    # enviar/cancelar/retorno).
    await db.commit()
    await db.refresh(lote)
    return lote


async def remover_parcela(db: AsyncSession, *, tenant_id: int, lote_id: int,
                          parcela_id: int) -> LotePagamento:
    lote = await obter_lote(db, tenant_id=tenant_id, lote_id=lote_id, for_update=True)
    if lote.situacao != "RASCUNHO":
        raise PagamentoDebitoError(
            f"Lote não está em rascunho (está '{lote.situacao}') — parcela não pode ser removida.",
            status.HTTP_409_CONFLICT)
    vinculo = (await db.execute(select(LotePagamentoParcela).where(
        LotePagamentoParcela.tenant_id == tenant_id, LotePagamentoParcela.id_lote == lote_id,
        LotePagamentoParcela.id_parcela == parcela_id))).scalar_one_or_none()
    if vinculo is None:
        raise PagamentoDebitoError("Parcela não está neste lote.", status.HTTP_404_NOT_FOUND)
    parcela = (await db.execute(select(Parcela).where(Parcela.id == parcela_id))).scalar_one()
    await db.delete(vinculo)
    lote.valor_total = lote.valor_total - parcela.valor
    lote.atualizado_em = _utcnow()
    await db.commit()
    await db.refresh(lote)
    return lote


async def _debitos_do_lote(db: AsyncSession, *, tenant_id: int,
                           vinculos: list[LotePagamentoParcela]) -> dict[int, Debito]:
    """Débitos ÚNICOS por trás das parcelas de um lote, com lock — ordem de
    primeira aparição preservada (`dict` em Python 3 é ordenado)."""
    debitos: dict[int, Debito] = {}
    for v in vinculos:
        parcela = (await db.execute(select(Parcela).where(
            Parcela.id == v.id_parcela))).scalar_one()
        if parcela.id_debito not in debitos:
            debitos[parcela.id_debito] = await obter_debito(
                db, tenant_id=tenant_id, debito_id=parcela.id_debito, for_update=True)
    return debitos


async def cancelar_lote(db: AsyncSession, *, tenant_id: int, lote_id: int,
                        usuario_id: int) -> LotePagamento:
    """Só de `RASCUNHO`/`PROGRAMADO` (não de `ENVIADO` — depois de enviado ao
    banco só o retorno resolve). Libera as parcelas removendo as linhas
    `lote_pagamento_parcela` — elas reaparecem em `parcelas_elegiveis_para_lote`."""
    lote = await obter_lote(db, tenant_id=tenant_id, lote_id=lote_id, for_update=True)
    if lote.situacao not in ("RASCUNHO", "PROGRAMADO"):
        raise PagamentoDebitoError(
            f"Lote '{lote.situacao}' não pode ser cancelado.", status.HTTP_409_CONFLICT)
    vinculos = await parcelas_do_lote(db, tenant_id=tenant_id, lote_id=lote_id)
    debitos_afetados = await _debitos_do_lote(db, tenant_id=tenant_id, vinculos=vinculos)
    for v in vinculos:
        await db.delete(v)
    lote.situacao = "CANCELADO"
    lote.atualizado_em = _utcnow()
    for d in debitos_afetados.values():
        _registrar_evento_lote(db, debito=d, acao="LOTE_CANCELADO", usuario_id=usuario_id,
                               justificativa=f"Lote {lote.numero} cancelado")
    await db.commit()
    await db.refresh(lote)
    return lote


async def programar_lote(db: AsyncSession, *, tenant_id: int, lote_id: int,
                         data_programada: date, usuario_id: int) -> LotePagamento:
    """`RASCUNHO -> PROGRAMADO`. Não muda `situacao_pagamento` do débito — já
    é `PROGRAMADA` desde a liberação (F1); o que `enviar_lote` faz é levá-la a
    `ENVIADA_BANCO`."""
    lote = await obter_lote(db, tenant_id=tenant_id, lote_id=lote_id, for_update=True)
    if lote.situacao != "RASCUNHO":
        raise PagamentoDebitoError(
            f"Lote '{lote.situacao}' não pode ser programado.", status.HTTP_409_CONFLICT)
    vinculos = await parcelas_do_lote(db, tenant_id=tenant_id, lote_id=lote_id)
    if not vinculos:
        raise PagamentoDebitoError("Lote vazio não pode ser programado.", status.HTTP_409_CONFLICT)
    debitos_afetados = await _debitos_do_lote(db, tenant_id=tenant_id, vinculos=vinculos)
    lote.situacao = "PROGRAMADO"
    lote.data_programada = data_programada
    lote.atualizado_em = _utcnow()
    for d in debitos_afetados.values():
        _registrar_evento_lote(db, debito=d, acao="LOTE_PROGRAMADO", usuario_id=usuario_id,
                               justificativa=f"Lote {lote.numero} programado para {data_programada}")
    await db.commit()
    await db.refresh(lote)
    return lote


async def enviar_lote(db: AsyncSession, *, tenant_id: int, lote_id: int,
                      usuario_id: int) -> LotePagamento:
    """`PROGRAMADO -> ENVIADO`. Fecha o gap de segregação de funções da F1
    (spec §6.2, premissa 6): quem executa o pagamento não pode ter sido
    solicitante, gestor decisor nem validador de NENHUM débito do lote — nem
    super-usuário faz bypass. Checa TODOS antes de gravar qualquer coisa
    (all-or-nothing); se algum falhar, nada muda e o 403 lista quais."""
    lote = await obter_lote(db, tenant_id=tenant_id, lote_id=lote_id, for_update=True)
    if lote.situacao != "PROGRAMADO":
        raise PagamentoDebitoError(
            f"Lote '{lote.situacao}' não pode ser enviado.", status.HTTP_409_CONFLICT)
    vinculos = await parcelas_do_lote(db, tenant_id=tenant_id, lote_id=lote_id)
    debitos_afetados = await _debitos_do_lote(db, tenant_id=tenant_id, vinculos=vinculos)

    problemas: list[str] = []
    for d in debitos_afetados.values():
        try:
            assert_segregacao(d, usuario_id=usuario_id, ato="PAGAR")
        except SegregacaoError as e:
            problemas.append(f"débito {d.id} ({e.detail})")
    if problemas:
        raise PagamentoDebitoError(
            "Segregação de funções barra o envio deste lote: "
            + "; ".join(problemas), status.HTTP_403_FORBIDDEN)

    lote.situacao = "ENVIADO"
    lote.enviado_em = _utcnow()
    lote.id_usuario_envio = usuario_id
    lote.atualizado_em = _utcnow()
    for d in debitos_afetados.values():
        _registrar_transicao(db, debito=d, acao="LOTE_ENVIADO", pagamento=est.ENVIADA_BANCO,
                             usuario_id=usuario_id, justificativa=f"Lote {lote.numero} enviado")
        d.atualizado_em = _utcnow()
    await db.commit()
    await db.refresh(lote)
    return lote
