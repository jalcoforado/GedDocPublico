"""Relatório de exceções de Pagamentos — Onda C, fatia C1.2.

Reúne num só lugar os estados que merecem olho humano. Nenhuma regra nova é
inventada aqui: cada exceção corresponde a algo que o modelo JÁ registra —
é justamente por isso que esta fatia pôde ser escrita sem a spec municipal
(ver `docs/pagamentos-onda-c-escopo.md`).

Cada regra devolve as linhas em falta e um total. O relatório inteiro é uma
foto do agora; não há persistência nem snapshot.

DÍVIDA PAGA em 2026-08-13 (fatia C1.3, migration 0091) — a exceção de saldo
insuficiente (RN-15). Ela era achada por `LIKE` sobre um texto concatenado na
justificativa do histórico, e o modo de falha era o pior possível num relatório
de compliance: frase reescrita ⇒ zero linhas, em silêncio, indistinguível de
"não houve exceção".

Hoje a fonte é `ordem_pagamento.excecao_saldo`, coluna. O `MARCADOR_RN15`
continua existindo porque a aplicação **ainda grava o texto** — `debito_historico`
é registro histórico e a frase está em linhas antigas —, mas nenhuma consulta
depende mais dele.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    ContaBancaria, Debito, DebitoHistorico, Fornecedor, LancamentoExtrato,
    MovimentacaoConta, OrdemPagamento, OrdemPagamentoDebito,
)

# Marcador que `pagamentos_autorizacao.autorizar_lote` ainda grava no texto do
# histórico. NÃO é mais fonte de consulta (ver docstring); fica aqui porque o
# backfill da 0091 dependeu dele e o teste de paridade ainda o usa para provar
# que a coluna encontra o mesmo conjunto que o `LIKE` encontrava.
MARCADOR_RN15 = "EXCEÇÃO DE SALDO (RN-15)"

# Situações de fornecedor que não deveriam sustentar despesa em andamento.
SITUACOES_IRREGULARES = ("IRREGULAR", "PENDENTE")

# Status de débito que ainda consomem/reservam saldo — usados para decidir se
# uma pendência cadastral do fornecedor é ou não relevante agora.
STATUS_EM_ANDAMENTO = (
    "EM_VALIDACAO", "VALIDADO", "ENVIADO_SECRETARIO", "AGUARDANDO_AUTORIZACAO",
    "AUTORIZADO", "ENVIADO_TESOURARIA", "EM_PROCESSAMENTO", "PAGO_PARCIAL",
)


@dataclass
class Excecao:
    codigo: str
    titulo: str
    descricao: str
    severidade: str  # alta | media | baixa
    total: int = 0
    itens: list[dict[str, Any]] = field(default_factory=list)


def _linha(**kw: Any) -> dict[str, Any]:
    """Normaliza Decimal/date para tipos serializáveis."""
    out: dict[str, Any] = {}
    for k, v in kw.items():
        if isinstance(v, Decimal):
            out[k] = str(v)
        elif isinstance(v, date):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


async def _colher(db: AsyncSession, stmt: Select, limite: int) -> tuple[list, int]:
    """Devolve (linhas limitadas, total real).

    O total vem de uma contagem separada de propósito: truncar a lista sem
    dizer quantas ficaram de fora transformaria "3 exceções" em conclusão
    falsa de quem lê.
    """
    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    linhas = (await db.execute(stmt.limit(limite))).all()
    return list(linhas), int(total)


async def _saldo_insuficiente(db: AsyncSession, tenant_id: int, limite: int) -> Excecao:
    exc = Excecao(
        codigo="RN15_SALDO_INSUFICIENTE",
        titulo="Autorização com saldo insuficiente",
        descricao=("Despesa autorizada com exceção de saldo (RN-15). Exige justificativa "
                   "e deve ser conferida — é a exceção mais sensível do rito."),
        severidade="alta",
    )
    # Fonte: a coluna (0091), não mais o `LIKE`. O conjunto é o mesmo — uma
    # linha por débito de uma OP autorizada com exceção —, e há teste de
    # paridade que compara as duas fontes sobre o mesmo dado.
    stmt = (
        select(OrdemPagamentoDebito.id_debito,
               OrdemPagamento.justificativa_excecao,
               OrdemPagamento.criado_em, Debito.descricao, Debito.valor_total)
        .join(OrdemPagamentoDebito, OrdemPagamentoDebito.id_ordem == OrdemPagamento.id)
        .join(Debito, Debito.id == OrdemPagamentoDebito.id_debito)
        .where(OrdemPagamento.tenant_id == tenant_id,
               OrdemPagamento.excecao_saldo.is_(True),
               Debito.excluido.is_(False))
        .order_by(OrdemPagamento.criado_em.desc())
    )
    linhas, exc.total = await _colher(db, stmt, limite)
    exc.itens = [
        _linha(id_debito=r[0], justificativa=r[1], em=r[2], descricao=r[3], valor=r[4])
        for r in linhas
    ]
    return exc


async def _fornecedor_irregular(db: AsyncSession, tenant_id: int, limite: int) -> Excecao:
    exc = Excecao(
        codigo="FORNECEDOR_IRREGULAR",
        titulo="Despesa em andamento com fornecedor irregular ou pendente",
        descricao=("O bloqueio existe na autorização, mas um débito já em curso pode ter "
                   "passado antes de a situação cadastral mudar."),
        severidade="alta",
    )
    stmt = (
        select(Debito.id, Debito.descricao, Debito.status, Debito.valor_total,
               Fornecedor.nome, Fornecedor.situacao_cadastral, Fornecedor.motivo_pendencia)
        .join(Fornecedor, Fornecedor.id == Debito.id_fornecedor)
        .where(Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
               Debito.status.in_(STATUS_EM_ANDAMENTO),
               Fornecedor.situacao_cadastral.in_(SITUACOES_IRREGULARES))
        .order_by(Debito.id.desc())
    )
    linhas, exc.total = await _colher(db, stmt, limite)
    exc.itens = [
        _linha(id_debito=r[0], descricao=r[1], status=r[2], valor=r[3],
               fornecedor=r[4], situacao=r[5], motivo=r[6])
        for r in linhas
    ]
    return exc


async def _por_status(db: AsyncSession, tenant_id: int, limite: int, *,
                      status: str, codigo: str, titulo: str, descricao: str,
                      severidade: str) -> Excecao:
    exc = Excecao(codigo=codigo, titulo=titulo, descricao=descricao, severidade=severidade)
    stmt = (
        select(Debito.id, Debito.descricao, Debito.valor_total, Debito.competencia,
               Debito.atualizado_em)
        .where(Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
               Debito.status == status)
        .order_by(Debito.id.desc())
    )
    linhas, exc.total = await _colher(db, stmt, limite)
    exc.itens = [
        _linha(id_debito=r[0], descricao=r[1], valor=r[2], competencia=r[3], desde=r[4])
        for r in linhas
    ]
    return exc


async def _urgente_sem_justificativa(db: AsyncSession, tenant_id: int, limite: int) -> Excecao:
    exc = Excecao(
        codigo="URGENTE_SEM_JUSTIFICATIVA",
        titulo="Débito marcado como urgente sem justificativa",
        descricao="Urgência muda a ordem de pagamento; sem justificativa, não é auditável.",
        severidade="media",
    )
    stmt = (
        select(Debito.id, Debito.descricao, Debito.valor_total, Debito.status)
        .where(Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
               Debito.urgente.is_(True),
               (Debito.justificativa_urgencia.is_(None))
               | (func.trim(Debito.justificativa_urgencia) == ""))
        .order_by(Debito.id.desc())
    )
    linhas, exc.total = await _colher(db, stmt, limite)
    exc.itens = [
        _linha(id_debito=r[0], descricao=r[1], valor=r[2], status=r[3]) for r in linhas
    ]
    return exc


async def _lancamentos_nao_conciliados(db: AsyncSession, tenant_id: int, limite: int) -> Excecao:
    exc = Excecao(
        codigo="EXTRATO_NAO_CONCILIADO",
        titulo="Lançamento de extrato pendente de conciliação",
        descricao=("Movimento no banco sem contrapartida conciliada. Quanto mais antigo, "
                   "pior — é o que impede o débito de chegar a CONCILIADO."),
        severidade="media",
    )
    stmt = (
        select(LancamentoExtrato.id, LancamentoExtrato.data, LancamentoExtrato.historico,
               LancamentoExtrato.valor, LancamentoExtrato.tipo, LancamentoExtrato.favorecido)
        .where(LancamentoExtrato.tenant_id == tenant_id,
               LancamentoExtrato.conciliado.is_(False))
        .order_by(LancamentoExtrato.data)
    )
    linhas, exc.total = await _colher(db, stmt, limite)
    hoje = date.today()
    exc.itens = [
        _linha(id_lancamento=r[0], data=r[1], historico=r[2], valor=r[3], tipo=r[4],
               favorecido=r[5], dias_em_aberto=(hoje - r[1]).days if r[1] else None)
        for r in linhas
    ]
    return exc


async def _conta_abaixo_do_minimo(db: AsyncSession, tenant_id: int, limite: int) -> Excecao:
    """Compara o saldo bancário com o mínimo de alerta configurado.

    Não chama `painel_caixa`: aquele serviço calcula os cinco saldos com uma
    consulta por conta, caro para um relatório que só precisa desta comparação.
    A fórmula é a mesma do `saldo_atual` de lá — inicial + entradas − saídas —,
    aqui em subquery correlacionada, no mesmo idioma de `saldo_conta`.
    """
    def _soma(tipo: str):
        return (
            select(func.coalesce(func.sum(MovimentacaoConta.valor), 0))
            .where(MovimentacaoConta.tenant_id == tenant_id,
                   MovimentacaoConta.id_conta == ContaBancaria.id,
                   MovimentacaoConta.excluido.is_(False),
                   MovimentacaoConta.tipo == tipo)
            .correlate(ContaBancaria)
            .scalar_subquery()
        )

    saldo = ContaBancaria.saldo_inicial + _soma("ENTRADA") - _soma("SAIDA")
    stmt = (
        select(ContaBancaria.id, ContaBancaria.nome, ContaBancaria.banco,
               saldo.label("saldo"), ContaBancaria.saldo_minimo_alerta)
        .where(ContaBancaria.tenant_id == tenant_id,
               ContaBancaria.excluido.is_(False), ContaBancaria.ativa.is_(True),
               saldo < ContaBancaria.saldo_minimo_alerta)
        .order_by(ContaBancaria.nome)
    )
    exc = Excecao(
        codigo="CONTA_ABAIXO_MINIMO",
        titulo="Conta abaixo do saldo mínimo de alerta",
        descricao="O mínimo é o que a própria prefeitura configurou como piso operacional.",
        severidade="alta",
    )
    linhas, exc.total = await _colher(db, stmt, limite)
    exc.itens = [
        _linha(id_conta=r[0], nome=r[1], banco=r[2], saldo=r[3], minimo=r[4])
        for r in linhas
    ]
    return exc


async def relatorio_excecoes(
    db: AsyncSession, *, tenant_id: int, limite_por_regra: int = 50,
) -> dict[str, Any]:
    """Executa todas as regras e devolve o consolidado.

    `limite_por_regra` corta a lista, nunca o total — quem lê precisa saber
    que existem 300 pendências mesmo vendo 50.
    """
    excecoes = [
        await _saldo_insuficiente(db, tenant_id, limite_por_regra),
        await _fornecedor_irregular(db, tenant_id, limite_por_regra),
        await _conta_abaixo_do_minimo(db, tenant_id, limite_por_regra),
        await _por_status(
            db, tenant_id, limite_por_regra, status="SUSPENSO",
            codigo="DEBITO_SUSPENSO", titulo="Débito suspenso",
            descricao="Parado por decisão administrativa; some da fila sem sumir da despesa.",
            severidade="media"),
        await _por_status(
            db, tenant_id, limite_por_regra, status="DEVOLVIDO",
            codigo="DEBITO_DEVOLVIDO", titulo="Débito devolvido para ajuste",
            descricao="Voltou ao solicitante e depende dele para andar.",
            severidade="baixa"),
        await _por_status(
            db, tenant_id, limite_por_regra, status="PAGO",
            codigo="PAGO_NAO_CONCILIADO", titulo="Pago ainda não conciliado",
            descricao=("Saiu da tesouraria mas não casou com o extrato. Vira CONCILIADO "
                       "sozinho quando a conciliação fechar."),
            severidade="baixa"),
        await _urgente_sem_justificativa(db, tenant_id, limite_por_regra),
        await _lancamentos_nao_conciliados(db, tenant_id, limite_por_regra),
    ]
    return {
        "gerado_em": date.today().isoformat(),
        "total_excecoes": sum(e.total for e in excecoes),
        "regras": [
            {
                "codigo": e.codigo, "titulo": e.titulo, "descricao": e.descricao,
                "severidade": e.severidade, "total": e.total,
                "exibindo": len(e.itens), "itens": e.itens,
            }
            for e in excecoes
        ],
    }
