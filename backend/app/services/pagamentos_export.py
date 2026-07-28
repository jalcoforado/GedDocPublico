"""Exportação das listagens de Pagamentos — Onda C, fatia C1.

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

from ..models import Contrato, Debito, FonteRecursos, NaturezaDespesa
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
