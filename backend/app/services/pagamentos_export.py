"""Exportação das listagens de Pagamentos — Onda C, fatias C1.1 e C1.3.

C1.1 (2026-08-07) exportou a lista de débitos. C1.3 (2026-08-13) fechou as
outras quatro listagens que o escopo previa: extrato da conta, painel de
caixa, ordens de pagamento e lançamentos de conciliação. Parar na primeira
não economizava trabalho — produzia um módulo em que o usuário não consegue
prever qual tela exporta.

Formato CSV com separador `;` e BOM UTF-8: é o que o Excel em pt-BR abre com
as colunas já separadas e os acentos corretos, sem passar pelo assistente de
importação. Foi a razão de NÃO adicionar `openpyxl` só para gerar XLSX — a
dependência não se pagava para o caso de uso "abrir no Excel".

Exporta o mesmo recorte que a tela mostra: os filtros são os do painel
(RF-PNL-02), reusando `listar_debitos`. Sem esse reuso, exportação e tela
divergiriam no dia em que um filtro mudasse.
"""
from __future__ import annotations

import csv
import io
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    ContaBancaria, Contrato, Debito, FonteRecursos, NaturezaDespesa, Usuario,
)
from . import pagamentos_autorizacao as aut_svc
from . import pagamentos_caixa as caixa_svc
from . import pagamentos_conciliacao as conc_svc
from . import pagamentos_debitos as deb_svc

# BOM: sem ele o Excel lê UTF-8 como ANSI e "competência" vira "competÃªncia".
BOM = "﻿"
SEP = ";"

COLUNAS_DEBITOS = [
    "id", "status", "competencia", "descricao", "fornecedor", "natureza",
    "fonte_recursos", "contrato", "numero_ne", "numero_nf", "valor_total",
    "criticidade", "urgente", "justificativa_urgencia", "liquidacao_confirmada",
    "data_liquidacao", "criado_em",
]


def _moeda(v: Decimal | None) -> str:
    """Decimal em pt-BR (vírgula decimal) — o Excel só reconhece como número
    se o separador casar com a localidade."""
    if v is None:
        return ""
    return f"{v:.2f}".replace(".", ",")


def _data(v) -> str:
    return v.isoformat() if v is not None else ""


def _bool(v: bool | None) -> str:
    return "sim" if v else "não"


async def _mapa(db: AsyncSession, model, tenant_id: int, campo: str) -> dict[int, str]:
    """id → rótulo legível, para não exportar uma parede de FKs."""
    rows = (
        await db.execute(
            select(model.id, getattr(model, campo)).where(model.tenant_id == tenant_id)
        )
    ).all()
    return {r[0]: r[1] for r in rows}


async def csv_debitos(db: AsyncSession, *, tenant_id: int, **filtros) -> str:
    """CSV dos débitos no mesmo recorte da listagem.

    `filtros` são repassados a `listar_debitos` — manter a assinatura aberta é
    proposital: um filtro novo no painel passa a valer aqui sem alteração.
    """
    debitos = await deb_svc.listar_debitos(db, tenant_id=tenant_id, **filtros)

    fornecedores = await deb_svc.nomes_fornecedores(
        db, tenant_id=tenant_id, ids={d.id_fornecedor for d in debitos}
    )
    naturezas = await _mapa(db, NaturezaDespesa, tenant_id, "descricao")
    fontes = await _mapa(db, FonteRecursos, tenant_id, "descricao")
    contratos = await _mapa(db, Contrato, tenant_id, "numero")

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=SEP, quoting=csv.QUOTE_MINIMAL,
                        lineterminator="\r\n")
    writer.writerow(COLUNAS_DEBITOS)
    for d in debitos:
        writer.writerow([
            d.id,
            d.status,
            d.competencia,
            d.descricao,
            fornecedores.get(d.id_fornecedor, ""),
            naturezas.get(d.id_natureza, ""),
            fontes.get(d.id_fonte_recursos, ""),
            contratos.get(d.id_contrato, "") if d.id_contrato else "",
            d.numero_ne or "",
            d.numero_nf or "",
            _moeda(d.valor_total),
            d.criticidade,
            _bool(d.urgente),
            d.justificativa_urgencia or "",
            _bool(d.liquidacao_confirmada),
            _data(d.data_liquidacao),
            _data(d.criado_em),
        ])
    return BOM + buf.getvalue()


def nome_arquivo_debitos(**filtros) -> str:
    """Nome que carrega o recorte exportado — abrir três arquivos chamados
    `debitos.csv` e não saber qual é qual é o caminho curto para erro."""
    partes = ["debitos"]
    if filtros.get("status_f"):
        partes.append(str(filtros["status_f"]).lower())
    if filtros.get("competencia"):
        partes.append(str(filtros["competencia"]))
    return "-".join(partes) + ".csv"


# ---------------------------------------------------------------------------
# C1.3 — as quatro listagens restantes
#
# Todas reusam o serviço de listagem da tela, e isso não é preferência de
# estilo: export que refaz a consulta diverge da tela no primeiro filtro novo,
# e a divergência chega como "o CSV veio diferente do que eu vi" — reclamação
# que ninguém consegue reproduzir.
# ---------------------------------------------------------------------------

COLUNAS_EXTRATO = [
    "id", "data", "tipo", "valor", "origem", "descricao", "id_debito",
    "id_parcela", "criado_em",
]

COLUNAS_PAINEL = [
    "id_conta", "conta", "banco", "grupo_despesa", "saldo_inicial",
    "total_entradas", "total_saidas", "saldo_atual", "comprometido",
    "bloqueado", "disponivel", "disponivel_projetado", "saldo_conciliado",
    "saldo_minimo_alerta", "abaixo_minimo",
]

COLUNAS_ORDENS = [
    "id", "numero", "criado_em", "conta_pagadora", "autorizador",
    "valor_total", "valor_reservado", "saldo_antes", "saldo_projetado_apos",
    "excecao_saldo", "justificativa_excecao",
]

COLUNAS_LANCAMENTOS = [
    "id", "data", "historico", "documento", "favorecido", "tipo", "valor",
    "conciliado",
]


def _escritor(buf: io.StringIO, colunas: list[str]):
    w = csv.writer(buf, delimiter=SEP, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    w.writerow(colunas)
    return w


async def csv_extrato_conta(db: AsyncSession, *, tenant_id: int, conta_id: int) -> str:
    """Movimentações de UMA conta — o extrato interno, não o do banco."""
    movs = await caixa_svc.listar_extrato(db, tenant_id=tenant_id, conta_id=conta_id)
    buf = io.StringIO()
    w = _escritor(buf, COLUNAS_EXTRATO)
    for m in movs:
        w.writerow([
            m.id, _data(m.data), m.tipo, _moeda(m.valor), m.origem or "",
            m.descricao or "", m.id_debito or "", m.id_parcela or "",
            _data(m.criado_em),
        ])
    return BOM + buf.getvalue()


async def csv_painel_caixa(db: AsyncSession, *, tenant_id: int) -> str:
    """Os cinco saldos por conta, como o painel mostra."""
    linhas = await caixa_svc.painel_caixa(db, tenant_id=tenant_id)
    buf = io.StringIO()
    w = _escritor(buf, COLUNAS_PAINEL)
    for c in linhas:
        w.writerow([
            c.id_conta, c.nome, c.banco, c.grupo_despesa,
            _moeda(c.saldo_inicial), _moeda(c.total_entradas),
            _moeda(c.total_saidas), _moeda(c.saldo_atual),
            _moeda(c.comprometido), _moeda(c.bloqueado), _moeda(c.disponivel),
            _moeda(c.disponivel_projetado), _moeda(c.saldo_conciliado),
            _moeda(c.saldo_minimo_alerta), _bool(c.abaixo_minimo),
        ])
    return BOM + buf.getvalue()


async def _rotulos_de_ordem(db: AsyncSession, tenant_id: int, ordens):
    contas = await _mapa(db, ContaBancaria, tenant_id, "nome")
    ids = {o.id_usuario_autorizador for o in ordens}
    autorizadores: dict[int, str] = {}
    if ids:
        rows = (await db.execute(
            select(Usuario.id, Usuario.nome).where(Usuario.id.in_(ids))
        )).all()
        autorizadores = {r[0]: r[1] for r in rows}
    return contas, autorizadores


async def csv_ordens(db: AsyncSession, *, tenant_id: int) -> str:
    """Ordens de pagamento, com a exceção de saldo (RN-15) como coluna.

    A exceção entra aqui porque é exatamente o que um controle interno procura
    numa lista de OPs — e, desde a migration 0091, ela é um booleano, não uma
    frase escondida no meio de um texto livre.
    """
    ordens = await aut_svc.listar_ordens(db, tenant_id=tenant_id)
    contas, autorizadores = await _rotulos_de_ordem(db, tenant_id, ordens)
    buf = io.StringIO()
    w = _escritor(buf, COLUNAS_ORDENS)
    for o in ordens:
        w.writerow([
            o.id, o.numero, _data(o.criado_em),
            contas.get(o.id_conta_pagadora, "") if o.id_conta_pagadora else "",
            autorizadores.get(o.id_usuario_autorizador, ""),
            _moeda(o.valor_total), _moeda(o.valor_reservado),
            _moeda(o.saldo_antes), _moeda(o.saldo_projetado_apos),
            _bool(o.excecao_saldo), o.justificativa_excecao or "",
        ])
    return BOM + buf.getvalue()


async def csv_lancamentos(db: AsyncSession, *, tenant_id: int, id_extrato: int) -> str:
    """Lançamentos de um extrato importado — a matéria-prima da conciliação."""
    lancs = await conc_svc.listar_lancamentos(db, tenant_id=tenant_id, id_extrato=id_extrato)
    buf = io.StringIO()
    w = _escritor(buf, COLUNAS_LANCAMENTOS)
    for lanc in lancs:
        w.writerow([
            lanc.id, _data(lanc.data), lanc.historico or "", lanc.documento or "",
            lanc.favorecido or "", lanc.tipo, _moeda(lanc.valor), _bool(lanc.conciliado),
        ])
    return BOM + buf.getvalue()


# ---------------------------------------------------------------------------
# PDF — só nos dois que viram DOCUMENTO
#
# Painel de caixa e ordens de pagamento são o que se imprime, assina e arquiva.
# Extrato e lançamentos são material de planilha: PDF ali seria pior que o CSV
# para o uso real (conferir, filtrar, somar).
# ---------------------------------------------------------------------------

def _tabela_html(colunas: list[str], linhas: list[list[str]]) -> str:
    import html as _h

    cab = "".join(f"<th>{_h.escape(c)}</th>" for c in colunas)
    corpo = "".join(
        "<tr>" + "".join(f"<td>{_h.escape(str(v))}</td>" for v in linha) + "</tr>"
        for linha in linhas
    )
    return "<table><thead><tr>" + cab + "</tr></thead><tbody>" + corpo + "</tbody></table>"


def _linhas_do_csv(conteudo: str) -> tuple[list[str], list[list[str]]]:
    """Reaproveita o CSV já montado como fonte do PDF.

    Duas montagens independentes divergiriam — e divergência entre o PDF e a
    planilha do MESMO relatório é o tipo de defeito que só aparece numa
    auditoria, quando os dois documentos já saíram da prefeitura.
    """
    texto = conteudo.lstrip(BOM)
    linhas = list(csv.reader(io.StringIO(texto), delimiter=SEP))
    if not linhas:
        return [], []
    return linhas[0], linhas[1:]


async def pdf_painel_caixa(db: AsyncSession, *, tenant_id: int) -> bytes:
    from .html_pdf import html_to_pdf_bytes

    colunas, linhas = _linhas_do_csv(await csv_painel_caixa(db, tenant_id=tenant_id))
    return html_to_pdf_bytes(_tabela_html(colunas, linhas), titulo="Painel de caixa")


async def pdf_ordens(db: AsyncSession, *, tenant_id: int) -> bytes:
    from .html_pdf import html_to_pdf_bytes

    colunas, linhas = _linhas_do_csv(await csv_ordens(db, tenant_id=tenant_id))
    return html_to_pdf_bytes(_tabela_html(colunas, linhas), titulo="Ordens de pagamento")
