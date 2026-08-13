"""RN-15 estruturada — fatia C1.3 (migration 0091).

A exceção de saldo insuficiente é "a exceção mais sensível do rito": autorizar
pagamento sem saldo disponível. Até esta fatia ela existia só como texto
concatenado numa justificativa, e o relatório de exceções a encontrava por
`LIKE`.

**O que havia de cobertura antes disto**: um teste que lia o código-fonte de
`autorizar_lote` com `inspect.getsource` e conferia que a string do marcador
estava lá. Isso protege contra renomear a frase — e contra mais nada. Nenhum
teste jamais autorizou com exceção e verificou que o relatório a encontrava.
Trocar a fonte de dados sem cobertura de comportamento seria trocar no escuro,
então ela vem aqui.

Os helpers de cenário são importados de `test_pagamentos_autorizacao` de
propósito: montar débito aprovado, fonte, conta com saldo e autorizador com
alçada são ~120 linhas de harness, e uma segunda cópia divergiria da primeira
no dia em que o rito mudasse.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select, text

from app.models import Debito, DebitoHistorico, OrdemPagamento, OrdemPagamentoDebito
from app.schemas.pagamentos import GrupoAutorizacaoIn
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_excecoes as exc_svc
from tests.test_pagamentos_autorizacao import (
    _autorizador_com_alcada,
    _cleanup,
    _debito_aprovado,
    _provisionar,
    _sm,
)

JUSTIFICATIVA = "Folha atrasada; prefeito autorizou por ofício 12/2026."


async def _autorizar_com_excecao(engine, tenant_id, *, valor="5000.00", saldo="100.00"):
    """Autoriza um débito cujo valor NÃO cabe no saldo, com a exceção ligada.

    `saldo` menor que `valor` é o ponto: sem `permitir_saldo_insuficiente` isto
    seria 422 (CA-AUT-04). É o caminho que o relatório precisa enxergar.
    """
    d, _sol, _apr, fonte, conta = await _debito_aprovado(
        engine, tenant_id, valor=valor, saldo_inicial=saldo
    )
    autorizador = await _autorizador_com_alcada(engine, tenant_id)
    async with _sm(engine)() as s:
        ops = await aut.autorizar_lote(
            s,
            tenant_id=tenant_id,
            usuario_id=autorizador,
            grupos=[GrupoAutorizacaoIn(
                id_fonte=fonte.id,
                id_conta_pagadora=conta.id,
                debito_ids=[d.id],
                permitir_saldo_insuficiente=True,
                justificativa_excecao=JUSTIFICATIVA,
            )],
        )
        await s.commit()
    return d, ops


@pytest.mark.asyncio
async def test_autorizacao_com_excecao_grava_a_coluna(admin_engine) -> None:
    """O que a fatia acrescenta: a exceção deixa de ser só texto."""
    t = await _provisionar(admin_engine)
    try:
        await _autorizar_com_excecao(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            op = (await s.execute(select(OrdemPagamento).where(
                OrdemPagamento.tenant_id == t.id))).scalars().one()
        assert op.excecao_saldo is True
        assert op.justificativa_excecao == JUSTIFICATIVA
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_autorizacao_normal_nao_marca_excecao(admin_engine) -> None:
    """O par indispensável. Sem ele, `excecao_saldo = True` fixo passaria —
    e todo pagamento do município apareceria no relatório de compliance como
    exceção, que é o jeito mais rápido de fazer ninguém mais ler o relatório."""
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, fonte, conta = await _debito_aprovado(
            admin_engine, t.id, valor="100.00", saldo_inicial="10000.00")
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            await aut.autorizar_lote(
                s, tenant_id=t.id, usuario_id=autorizador,
                grupos=[GrupoAutorizacaoIn(id_fonte=fonte.id,
                                           id_conta_pagadora=conta.id,
                                           debito_ids=[d.id])])
            await s.commit()
        async with _sm(admin_engine)() as s:
            op = (await s.execute(select(OrdemPagamento).where(
                OrdemPagamento.tenant_id == t.id))).scalars().one()
        assert op.excecao_saldo is False
        assert op.justificativa_excecao is None
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_o_relatorio_encontra_a_excecao_pela_coluna(admin_engine) -> None:
    """A ponta que interessa ao usuário: a exceção aparece no relatório.

    Nenhum teste afirmava isto antes — a regra RN-15 podia estar devolvendo
    zero para sempre e a suíte não notaria.
    """
    t = await _provisionar(admin_engine)
    try:
        d, _ops = await _autorizar_com_excecao(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            rel = await exc_svc.relatorio_excecoes(s, tenant_id=t.id, limite_por_regra=50)
        regra = next(r for r in rel["regras"] if r["codigo"] == "RN15_SALDO_INSUFICIENTE")
        assert regra["total"] == 1, regra
        item = regra["itens"][0]
        assert item["id_debito"] == d.id
        assert JUSTIFICATIVA in (item["justificativa"] or "")
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_coluna_e_like_encontram_o_mesmo_conjunto(admin_engine) -> None:
    """Paridade — o que prova que a troca de fonte não mudou o resultado.

    A coluna é fonte nova; o texto continua sendo gravado. Se as duas
    discordarem sobre o MESMO dado, ou o backfill errou o alvo ou a gravação
    nova está incompleta. Este teste é o que detectaria qualquer um dos dois.
    """
    t = await _provisionar(admin_engine)
    try:
        await _autorizar_com_excecao(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            por_coluna = (await s.execute(
                select(func.count()).select_from(OrdemPagamentoDebito)
                .join(OrdemPagamento, OrdemPagamento.id == OrdemPagamentoDebito.id_ordem)
                .join(Debito, Debito.id == OrdemPagamentoDebito.id_debito)
                .where(OrdemPagamento.tenant_id == t.id,
                       OrdemPagamento.excecao_saldo.is_(True),
                       Debito.excluido.is_(False))
            )).scalar_one()
            por_like = (await s.execute(
                select(func.count()).select_from(DebitoHistorico)
                .join(Debito, Debito.id == DebitoHistorico.id_debito)
                .where(DebitoHistorico.tenant_id == t.id,
                       DebitoHistorico.justificativa.like(f"%{exc_svc.MARCADOR_RN15}%"),
                       Debito.excluido.is_(False))
            )).scalar_one()
        assert por_coluna == por_like == 1, (por_coluna, por_like)
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_o_backfill_alcanca_linha_antiga(admin_engine) -> None:
    """O backfill da 0091, exercitado sobre uma linha no formato ANTIGO.

    A migration já rodou neste banco, então o teste refaz o cenário que ela
    encontraria: uma OP com a coluna zerada e o histórico com o texto. Sem
    isto, "a coluna existe" passaria mesmo com um `LIKE` que não casa nada — e
    o histórico do município ficaria invisível no relatório, em silêncio.
    """
    t = await _provisionar(admin_engine)
    try:
        d, _ops = await _autorizar_com_excecao(admin_engine, t.id)

        # Volta ao estado pré-0091: coluna zerada, texto intacto.
        async with _sm(admin_engine)() as s:
            await s.execute(text(
                "UPDATE pagamentos.ordem_pagamento "
                "SET excecao_saldo = false, justificativa_excecao = NULL "
                "WHERE tenant_id = :t"), {"t": t.id})
            await s.commit()

        async with _sm(admin_engine)() as s:
            antes = (await s.execute(select(OrdemPagamento).where(
                OrdemPagamento.tenant_id == t.id))).scalars().one()
            assert antes.excecao_saldo is False, "o cenário não voltou ao estado antigo"

            # O MESMO SQL da migration 0091.
            await s.execute(text("""
                UPDATE pagamentos.ordem_pagamento AS op
                   SET excecao_saldo = true,
                       justificativa_excecao = TRIM(BOTH ': ' FROM sub.texto)
                  FROM (
                      SELECT DISTINCT ON (h.justificativa)
                             h.tenant_id,
                             split_part(h.justificativa, 'OP ', 2) AS resto,
                             split_part(h.justificativa, 'EXCEÇÃO DE SALDO (RN-15)', 2) AS texto
                        FROM pagamentos.debito_historico h
                       WHERE h.justificativa LIKE '%EXCEÇÃO DE SALDO (RN-15)%'
                  ) AS sub
                 WHERE op.tenant_id = sub.tenant_id
                   AND sub.resto LIKE op.numero || '%'
            """))
            await s.commit()

        async with _sm(admin_engine)() as s:
            depois = (await s.execute(select(OrdemPagamento).where(
                OrdemPagamento.tenant_id == t.id))).scalars().one()
        assert depois.excecao_saldo is True, "o backfill não alcançou a linha antiga"
        assert depois.justificativa_excecao == JUSTIFICATIVA, depois.justificativa_excecao
        assert d.id  # o débito existe; ancora o cenário
    finally:
        await _cleanup(admin_engine, t.id)
