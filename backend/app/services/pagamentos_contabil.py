"""Export contábil neutro — Onda C2, fatia C2.1.

Gera, para um sistema contábil externo (Betha, Sagres etc.), um lote de
eventos "planos" derivados do domínio de Pagamentos — sem depender de o
sistema contábil entender a máquina de estados do débito, os três eixos da
F1 ou a RN-15. Cinco tipos de evento cobrem o ciclo de vida que importa para
a contabilidade:

- `debito_empenhado` — débito com número de empenho preenchido;
- `liquidacao` — liquidação confirmada (RF-VAL-02/RN-01);
- `pagamento` — parcela paga, com a exceção de saldo (RN-15) quando houver;
- `estorno_parcela` — reversão de um pagamento;
- `cancelamento_debito` — débito cancelado antes de autorizado.

## Âncora de cada evento — por que NÃO é uma coluna nova

O domínio não tem uma tabela "evento contábil": cada tipo é derivado do
registro real mais próximo, e a escolha importa porque `id_origem` tem de
ser estável (nunca uma sequência própria do export) e `ocorrido_em` tem de
vir de um campo que já existia antes desta fatia.

- `debito_empenhado`, `liquidacao`, `cancelamento_debito` — a linha de
  `debito_historico` da transição correspondente (`acao` = `CRIADO`,
  `LIQUIDADO`, `CANCELADO`). `id_origem` = `debito_historico.id`;
  `ocorrido_em` = `debito_historico.criado_em`.

  **Limitação documentada, não inventada**: `numero_ne` normalmente entra em
  `DebitoCreate` (a linha `CRIADO` já nasce com ele). Se for preenchido
  depois, por `atualizar_debito` enquanto o débito está em RASCUNHO, essa
  edição NÃO grava `debito_historico` (só transição de estado grava) — não
  existe, hoje, um evento de domínio para "número de empenho entrou depois
  da criação". Este export usa o valor CORRENTE de `Debito.numero_ne` no
  momento da coleta, ancorado no `criado_em` da linha `CRIADO`; é a melhor
  âncora real disponível, e o caso (raro — RN-01 exige empenho antes de
  autorizar) fica registrado aqui em vez de ganhar uma coluna nova.

- `pagamento`, `estorno_parcela` — a `movimentacao_conta` que a baixa real
  gera (`pagar_parcela`/`estornar_parcela` em `pagamentos_autorizacao.py`,
  `origem` = `PAGAMENTO`/`ESTORNO`). `id_origem` = `movimentacao_conta.id`;
  `ocorrido_em` = `movimentacao_conta.criado_em`. Preferida a
  `debito_historico` (`acao` = `PAGO`/`ESTORNADO`) porque é ali — e só ali —
  que `valor` e `data_pagamento` do evento realmente vivem; a linha de
  histórico do débito não carrega o valor da parcela.

## Imutabilidade

Um lote gerado nunca muda: o CSV é reconstruído sob demanda a partir dos
`export_contabil_evento` do lote (não recalculado do zero), e o hash gravado
na criação é conferido contra o hash da reconstrução. Divergência é
corrupção — 500 com log, nunca silenciosa.
"""
from __future__ import annotations

import csv
import hashlib
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    ContaBancaria, Debito, DebitoHistorico, ExportContabilEvento, ExportContabilLote,
    Fornecedor, FonteRecursos, MovimentacaoConta, OrdemPagamento, OrdemPagamentoDebito,
)

logger = logging.getLogger(__name__)

BOM = "﻿"
SEP = ";"

# Chave arbitrária (classe, tenant) do advisory lock que serializa o cálculo
# do próximo `numero` de lote por tenant — best-effort; a rede de verdade é o
# índice único parcial `(tenant_id, numero)` da migration 0101.
ADVISORY_CLASS = 910101

COLUNAS = [
    "id_evento", "tipo_evento", "id_debito", "ocorrido_em", "lote",
    "numero_empenho", "fonte", "credor_doc", "credor_nome", "valor", "vencimento",
    "data_liquidacao", "numero_ordem", "conta", "data_pagamento", "valor_pago",
    "excecao_saldo", "justificativa", "motivo",
]

_TIPO_POR_ACAO = {"CRIADO": "debito_empenhado", "LIQUIDADO": "liquidacao",
                  "CANCELADO": "cancelamento_debito"}
_ACAO_POR_TIPO = {v: k for k, v in _TIPO_POR_ACAO.items()}
_TIPO_POR_ORIGEM_MOV = {"PAGAMENTO": "pagamento", "ESTORNO": "estorno_parcela"}
_ORIGEM_MOV_POR_TIPO = {v: k for k, v in _TIPO_POR_ORIGEM_MOV.items()}

TIPOS_EVENTO = frozenset(_TIPO_POR_ACAO.values()) | frozenset(_TIPO_POR_ORIGEM_MOV.values())


class ExportContabilError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=code, detail=detail)


def _utcnow() -> datetime:
    return datetime.utcnow()


@dataclass
class EventoContabil:
    tipo_evento: str
    id_origem: int
    id_debito: int
    ocorrido_em: datetime
    numero_empenho: str | None = None
    fonte: str | None = None
    credor_doc: str | None = None
    credor_nome: str | None = None
    valor: Decimal | None = None
    vencimento: date | None = None
    data_liquidacao: date | None = None
    numero_ordem: str | None = None
    conta: str | None = None
    data_pagamento: date | None = None
    valor_pago: Decimal | None = None
    excecao_saldo: bool | None = None
    justificativa: str | None = None
    motivo: str | None = None

    @property
    def id_evento(self) -> str:
        return f"{self.tipo_evento}:{self.id_origem}"


# ---------------------------------------------------------------------------
# Contexto compartilhado — fornecedor/fonte por débito, OP por débito, conta
# ---------------------------------------------------------------------------

async def _mapa_fornecedores(db: AsyncSession, tenant_id: int, ids: set[int]) -> dict[int, tuple[str, str]]:
    if not ids:
        return {}
    rows = (await db.execute(select(Fornecedor.id, Fornecedor.cnpj_cpf, Fornecedor.nome).where(
        Fornecedor.tenant_id == tenant_id, Fornecedor.id.in_(ids)))).all()
    return {r[0]: (r[1], r[2]) for r in rows}


async def _mapa_fontes(db: AsyncSession, tenant_id: int, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = (await db.execute(select(FonteRecursos.id, FonteRecursos.descricao).where(
        FonteRecursos.tenant_id == tenant_id, FonteRecursos.id.in_(ids)))).all()
    return {r[0]: r[1] for r in rows}


async def _mapa_contas(db: AsyncSession, tenant_id: int, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = (await db.execute(select(ContaBancaria.id, ContaBancaria.nome).where(
        ContaBancaria.tenant_id == tenant_id, ContaBancaria.id.in_(ids)))).all()
    return {r[0]: r[1] for r in rows}


async def _ultima_ordem_por_debito(db: AsyncSession, tenant_id: int,
                                   ids_debito: set[int]) -> dict[int, OrdemPagamento]:
    """A OP mais recente de cada débito (autorização é 1:1 na prática do rito
    v2.0; `max(id)` é a garantia se algum dia deixar de ser)."""
    if not ids_debito:
        return {}
    rows = (await db.execute(
        select(OrdemPagamentoDebito.id_debito, OrdemPagamento)
        .join(OrdemPagamento, OrdemPagamento.id == OrdemPagamentoDebito.id_ordem)
        .where(OrdemPagamentoDebito.tenant_id == tenant_id,
               OrdemPagamentoDebito.id_debito.in_(ids_debito))
        .order_by(OrdemPagamentoDebito.id_debito, OrdemPagamento.id.desc())
    )).all()
    out: dict[int, OrdemPagamento] = {}
    for id_debito, op in rows:
        out.setdefault(id_debito, op)  # a primeira por débito é a de maior id (ORDER BY acima)
    return out


def _motivo_de_descricao(descricao: str | None) -> str | None:
    """`descricao` de `movimentacao_conta` (origem ESTORNO) carrega a
    justificativa no formato "Estorno parcela N — débito #ID: <motivo>"
    (`pagamentos_autorizacao.estornar_parcela`). Extrai a parte livre."""
    if not descricao or ": " not in descricao:
        return None
    return descricao.split(": ", 1)[1]


# ---------------------------------------------------------------------------
# Montagem de EventoContabil a partir da fonte real
# ---------------------------------------------------------------------------

def _montar_de_historico(h: DebitoHistorico, d: Debito, tipo: str, *,
                         fornecedores: dict[int, tuple[str, str]], fontes: dict[int, str]) -> EventoContabil:
    doc, nome = fornecedores.get(d.id_fornecedor, (None, None))
    ev = EventoContabil(
        tipo_evento=tipo, id_origem=h.id, id_debito=d.id, ocorrido_em=h.criado_em,
        numero_empenho=d.numero_ne, fonte=fontes.get(d.id_fonte_recursos),
        credor_doc=doc, credor_nome=nome, valor=d.valor_total,
    )
    if tipo == "liquidacao":
        ev.data_liquidacao = d.data_liquidacao
    elif tipo == "cancelamento_debito":
        ev.motivo = h.justificativa
    return ev


def _montar_de_movimentacao(m: MovimentacaoConta, tipo: str, *,
                            fornecedores: dict[int, tuple[str, str]], fontes: dict[int, str],
                            debitos: dict[int, Debito],
                            ordens_por_debito: dict[int, OrdemPagamento],
                            contas: dict[int, str]) -> EventoContabil:
    d = debitos.get(m.id_debito)
    doc, nome = fornecedores.get(d.id_fornecedor, (None, None)) if d else (None, None)
    op = ordens_por_debito.get(m.id_debito) if m.id_debito else None
    ev = EventoContabil(
        tipo_evento=tipo, id_origem=m.id, id_debito=m.id_debito, ocorrido_em=m.criado_em,
        numero_empenho=d.numero_ne if d else None,
        fonte=fontes.get(d.id_fonte_recursos) if d else None,
        credor_doc=doc, credor_nome=nome,
        conta=contas.get(m.id_conta),
    )
    if op is not None:
        ev.numero_ordem = op.numero
        ev.excecao_saldo = op.excecao_saldo
        ev.justificativa = op.justificativa_excecao
    if tipo == "pagamento":
        ev.data_pagamento = m.data
        ev.valor_pago = m.valor
    else:  # estorno_parcela
        ev.valor = m.valor
        ev.motivo = _motivo_de_descricao(m.descricao)
    return ev


async def _contexto(db: AsyncSession, tenant_id: int, debitos: list[Debito],
                    *, precisa_ordens: bool) -> tuple[dict, dict, dict, dict]:
    ids_debito = {d.id for d in debitos}
    fornecedores = await _mapa_fornecedores(db, tenant_id, {d.id_fornecedor for d in debitos})
    fontes = await _mapa_fontes(db, tenant_id, {d.id_fonte_recursos for d in debitos})
    ordens_por_debito = await _ultima_ordem_por_debito(db, tenant_id, ids_debito) if precisa_ordens else {}
    ids_conta = {op.id_conta_pagadora for op in ordens_por_debito.values() if op.id_conta_pagadora}
    contas = await _mapa_contas(db, tenant_id, ids_conta)
    return fornecedores, fontes, ordens_por_debito, contas


# ---------------------------------------------------------------------------
# Coleta dos eventos PENDENTES (ainda não capturados por nenhum lote)
# ---------------------------------------------------------------------------

async def _pares_ja_capturados(db: AsyncSession, tenant_id: int) -> set[tuple[str, int]]:
    rows = (await db.execute(select(
        ExportContabilEvento.tipo_evento, ExportContabilEvento.id_origem,
    ).where(ExportContabilEvento.tenant_id == tenant_id))).all()
    return {(r[0], r[1]) for r in rows}


async def coletar_eventos_pendentes(db: AsyncSession, *, tenant_id: int,
                                    ate: date) -> list[EventoContabil]:
    """Varre o domínio até `ate` (inclusive) e devolve os eventos que ainda
    não entraram em nenhum lote — a "complementação" que a Task pede."""
    ja_capturados = await _pares_ja_capturados(db, tenant_id)
    limite = datetime.combine(ate, datetime.max.time())

    historicos = (await db.execute(
        select(DebitoHistorico, Debito)
        .join(Debito, Debito.id == DebitoHistorico.id_debito)
        .where(DebitoHistorico.tenant_id == tenant_id,
               DebitoHistorico.acao.in_(list(_TIPO_POR_ACAO)),
               DebitoHistorico.criado_em <= limite)
        .order_by(DebitoHistorico.criado_em, DebitoHistorico.id)
    )).all()

    movimentacoes = list((await db.execute(
        select(MovimentacaoConta)
        .where(MovimentacaoConta.tenant_id == tenant_id,
               MovimentacaoConta.origem.in_(list(_TIPO_POR_ORIGEM_MOV)),
               MovimentacaoConta.excluido.is_(False),
               MovimentacaoConta.data <= ate)
        .order_by(MovimentacaoConta.criado_em, MovimentacaoConta.id)
    )).scalars().all())

    debitos_ctx = [d for _h, d in historicos]
    ids_debito_mov = {m.id_debito for m in movimentacoes if m.id_debito is not None}
    if ids_debito_mov:
        extras = list((await db.execute(select(Debito).where(
            Debito.tenant_id == tenant_id, Debito.id.in_(ids_debito_mov)))).scalars().all())
        debitos_ctx += extras
    debitos_por_id = {d.id: d for d in debitos_ctx}

    fornecedores, fontes, ordens_por_debito, contas = await _contexto(
        db, tenant_id, list(debitos_por_id.values()), precisa_ordens=bool(movimentacoes))

    eventos: list[EventoContabil] = []
    for h, d in historicos:
        tipo = _TIPO_POR_ACAO[h.acao]
        if tipo == "debito_empenhado" and not (d.numero_ne or "").strip():
            continue
        if (tipo, h.id) in ja_capturados:
            continue
        eventos.append(_montar_de_historico(h, d, tipo, fornecedores=fornecedores, fontes=fontes))

    for m in movimentacoes:
        tipo = _TIPO_POR_ORIGEM_MOV[m.origem]
        if (tipo, m.id) in ja_capturados:
            continue
        eventos.append(_montar_de_movimentacao(
            m, tipo, fornecedores=fornecedores, fontes=fontes, debitos=debitos_por_id,
            ordens_por_debito=ordens_por_debito, contas=contas))

    return sorted(eventos, key=lambda e: (e.ocorrido_em, e.tipo_evento, e.id_origem))


# ---------------------------------------------------------------------------
# Adapters — hoje só o CSV neutro
# ---------------------------------------------------------------------------

def _moeda(v: Decimal | None) -> str:
    return "" if v is None else f"{v:.2f}".replace(".", ",")


def _data(v) -> str:
    return v.isoformat() if v is not None else ""


def _dt(v: datetime | None) -> str:
    return v.strftime("%Y-%m-%d %H:%M:%S") if v is not None else ""


def _bool(v: bool | None) -> str:
    if v is None:
        return ""
    return "sim" if v else "não"


class ContabilAdapter(Protocol):
    def gerar(self, eventos: list[EventoContabil], *, lote_numero: int) -> bytes: ...


class AdapterNeutroCSV:
    """CSV `;` + BOM UTF-8 — mesmo padrão dos exports da C1.3
    (`services/pagamentos_export.py`): é o que o Excel pt-BR abre sem
    assistente de importação e sem estragar acentuação."""

    def gerar(self, eventos: list[EventoContabil], *, lote_numero: int) -> bytes:
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=SEP, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
        w.writerow(COLUNAS)
        for e in eventos:
            w.writerow([
                e.id_evento, e.tipo_evento, e.id_debito, _dt(e.ocorrido_em), lote_numero,
                e.numero_empenho or "", e.fonte or "", e.credor_doc or "", e.credor_nome or "",
                _moeda(e.valor), _data(e.vencimento), _data(e.data_liquidacao),
                e.numero_ordem or "", e.conta or "", _data(e.data_pagamento), _moeda(e.valor_pago),
                _bool(e.excecao_saldo), e.justificativa or "", e.motivo or "",
            ])
        return (BOM + buf.getvalue()).encode("utf-8")


ADAPTERS: dict[str, ContabilAdapter] = {"neutro-csv-v1": AdapterNeutroCSV()}


# ---------------------------------------------------------------------------
# Geração e reconstrução de lote
# ---------------------------------------------------------------------------

async def _proximo_numero(db: AsyncSession, *, tenant_id: int) -> int:
    ultimo = (await db.execute(select(func.max(ExportContabilLote.numero)).where(
        ExportContabilLote.tenant_id == tenant_id))).scalar_one_or_none()
    return (ultimo or 0) + 1


async def gerar_lote(db: AsyncSession, *, tenant_id: int, ate: date,
                     usuario_id: int) -> ExportContabilLote:
    """Coleta os eventos pendentes até `ate`, grava lote + eventos e calcula
    o hash do CSV gerado. Sem evento pendente → 409 (nada muda em disco)."""
    eventos = await coletar_eventos_pendentes(db, tenant_id=tenant_id, ate=ate)
    if not eventos:
        raise ExportContabilError(
            "Nada a exportar: nenhum evento pendente até a data informada.",
            status.HTTP_409_CONFLICT)

    # Serializa o cálculo do próximo número por tenant. Best-effort — a rede
    # real é o índice único parcial `(tenant_id, numero)` (migration 0101).
    await db.execute(text("SELECT pg_advisory_xact_lock(:cls, :tid)"),
                     {"cls": ADVISORY_CLASS, "tid": tenant_id})
    numero = await _proximo_numero(db, tenant_id=tenant_id)

    datas = [e.ocorrido_em.date() for e in eventos]
    lote = ExportContabilLote(
        tenant_id=tenant_id, numero=numero, periodo_inicio=min(datas), periodo_fim=max(datas),
        formato_versao="neutro-csv-v1", qtd_eventos=len(eventos),
        id_usuario=usuario_id, gerado_em=_utcnow())
    db.add(lote)
    await db.flush()

    for e in eventos:
        db.add(ExportContabilEvento(
            tenant_id=tenant_id, id_lote=lote.id, tipo_evento=e.tipo_evento,
            id_origem=e.id_origem, ocorrido_em=e.ocorrido_em))

    conteudo = ADAPTERS[lote.formato_versao].gerar(eventos, lote_numero=lote.numero)
    lote.hash_conteudo = hashlib.sha256(conteudo).hexdigest()

    await db.commit()
    await db.refresh(lote)
    return lote


async def obter_lote(db: AsyncSession, *, tenant_id: int, lote_id: int) -> ExportContabilLote:
    lote = (await db.execute(select(ExportContabilLote).where(
        ExportContabilLote.id == lote_id, ExportContabilLote.tenant_id == tenant_id,
        ExportContabilLote.excluido.is_(False)))).scalar_one_or_none()
    if lote is None:
        raise ExportContabilError("Lote não encontrado", status.HTTP_404_NOT_FOUND)
    return lote


async def listar_lotes(db: AsyncSession, *, tenant_id: int) -> list[ExportContabilLote]:
    return list((await db.execute(select(ExportContabilLote).where(
        ExportContabilLote.tenant_id == tenant_id, ExportContabilLote.excluido.is_(False))
        .order_by(ExportContabilLote.numero.desc()))).scalars().all())


async def _reidratar(db: AsyncSession, *, tenant_id: int,
                     registros: list[ExportContabilEvento]) -> list[EventoContabil]:
    ids_hist = {r.id_origem for r in registros if r.tipo_evento in _ACAO_POR_TIPO}
    ids_mov = {r.id_origem for r in registros if r.tipo_evento in _ORIGEM_MOV_POR_TIPO}

    historicos: dict[int, tuple[DebitoHistorico, Debito]] = {}
    if ids_hist:
        rows = (await db.execute(
            select(DebitoHistorico, Debito)
            .join(Debito, Debito.id == DebitoHistorico.id_debito)
            .where(DebitoHistorico.tenant_id == tenant_id, DebitoHistorico.id.in_(ids_hist))
        )).all()
        historicos = {h.id: (h, d) for h, d in rows}

    movimentacoes: dict[int, MovimentacaoConta] = {}
    if ids_mov:
        rows = list((await db.execute(select(MovimentacaoConta).where(
            MovimentacaoConta.tenant_id == tenant_id,
            MovimentacaoConta.id.in_(ids_mov)))).scalars().all())
        movimentacoes = {m.id: m for m in rows}

    debitos_ctx = [d for _h, d in historicos.values()]
    ids_debito_mov = {m.id_debito for m in movimentacoes.values() if m.id_debito is not None}
    if ids_debito_mov:
        extras = list((await db.execute(select(Debito).where(
            Debito.tenant_id == tenant_id, Debito.id.in_(ids_debito_mov)))).scalars().all())
        debitos_ctx += extras
    debitos_por_id = {d.id: d for d in debitos_ctx}

    fornecedores, fontes, ordens_por_debito, contas = await _contexto(
        db, tenant_id, list(debitos_por_id.values()), precisa_ordens=bool(movimentacoes))

    eventos: list[EventoContabil] = []
    for r in registros:
        if r.tipo_evento in _ACAO_POR_TIPO:
            par = historicos.get(r.id_origem)
            if par is None:
                raise ExportContabilError(
                    f"Corrupção: evento {r.tipo_evento}:{r.id_origem} não encontrado na "
                    "origem (debito_historico).", status.HTTP_500_INTERNAL_SERVER_ERROR)
            h, d = par
            eventos.append(_montar_de_historico(h, d, r.tipo_evento,
                                                fornecedores=fornecedores, fontes=fontes))
        else:
            m = movimentacoes.get(r.id_origem)
            if m is None:
                raise ExportContabilError(
                    f"Corrupção: evento {r.tipo_evento}:{r.id_origem} não encontrado na "
                    "origem (movimentacao_conta).", status.HTTP_500_INTERNAL_SERVER_ERROR)
            eventos.append(_montar_de_movimentacao(
                m, r.tipo_evento, fornecedores=fornecedores, fontes=fontes, debitos=debitos_por_id,
                ordens_por_debito=ordens_por_debito, contas=contas))

    return sorted(eventos, key=lambda e: (e.ocorrido_em, e.tipo_evento, e.id_origem))


async def reconstruir_csv(db: AsyncSession, *, tenant_id: int, lote_id: int) -> bytes:
    """Regenera o CSV do lote a partir dos dados de origem (nunca a partir de
    uma cópia gravada) e confere contra o hash da criação. Reemissão do
    mesmo lote sempre devolve o MESMO conteúdo — é a prova de imutabilidade."""
    lote = await obter_lote(db, tenant_id=tenant_id, lote_id=lote_id)
    registros = list((await db.execute(select(ExportContabilEvento).where(
        ExportContabilEvento.tenant_id == tenant_id,
        ExportContabilEvento.id_lote == lote.id))).scalars().all())
    eventos = await _reidratar(db, tenant_id=tenant_id, registros=registros)

    adapter = ADAPTERS.get(lote.formato_versao)
    if adapter is None:
        raise ExportContabilError(
            f"Formato de export desconhecido: '{lote.formato_versao}'.",
            status.HTTP_500_INTERNAL_SERVER_ERROR)
    conteudo = adapter.gerar(eventos, lote_numero=lote.numero)
    hash_atual = hashlib.sha256(conteudo).hexdigest()
    if hash_atual != lote.hash_conteudo:
        logger.error(
            "pagamentos.contabil.hash_divergente",
            extra={"tenant_id": tenant_id, "lote_id": lote.id,
                   "hash_gravado": lote.hash_conteudo, "hash_atual": hash_atual})
        raise ExportContabilError(
            "Corrupção detectada: o conteúdo reconstruído diverge do hash gravado.",
            status.HTTP_500_INTERNAL_SERVER_ERROR)
    return conteudo
