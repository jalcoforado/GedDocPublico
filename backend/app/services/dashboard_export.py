"""Exportação do dashboard executivo em CSV e PDF — Fase 18c.

Reusa o payload de `services.dashboard.kpis()` — não roda queries novas.
Quem chama o exportador já tem o dict do dashboard pronto.
"""
from __future__ import annotations

import csv
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

APRIMORA = HexColor("#1e3a5f")
GRAY = HexColor("#6b7280")
LIGHT = HexColor("#f3f4f6")
GREEN = HexColor("#16a34a")
RED = HexColor("#dc2626")


def _fmt_num(n: float | int | None, decimals: int = 0) -> str:
    if n is None:
        return "—"
    if decimals == 0:
        return f"{int(n):,}".replace(",", ".")
    return f"{n:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _delta(current: float | None, previous: float | None) -> str:
    """Renderiza delta como string '+12.3%' ou '-5.0%' ou '—'."""
    if current is None or previous is None:
        return "—"
    if previous == 0:
        return "+∞" if current > 0 else "0%"
    pct = ((current - previous) / abs(previous)) * 100
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.1f}%"


def to_csv(payload: dict[str, Any], nome_tenant: str = "") -> str:
    """Gera CSV multi-seção. Compatível com Excel/LibreOffice.

    Estrutura: comentários `#` no topo, depois seções `[Volume]`, `[Conclusão]`,
    `[SLA]`, `[Por tipo]`, `[Por assunto]`, `[Por unidade]`, `[Série temporal]`.
    """
    buf = StringIO()
    w = csv.writer(buf, delimiter=",", quoting=csv.QUOTE_MINIMAL)

    # Cabeçalho como comentários
    buf.write(f"# Aprimora — Dashboard executivo\n")
    if nome_tenant:
        buf.write(f"# Tenant: {nome_tenant}\n")
    buf.write(f"# Período: últimos {payload['periodo_dias']} dias\n")
    buf.write(f"# Unidade: {payload.get('id_unidade') or 'Todas'}\n")
    buf.write(f"# Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
    buf.write("\n")

    # Volume
    v = payload["volume"]
    c = payload.get("comparativo", {})
    w.writerow(["[Volume]"])
    w.writerow(["Métrica", "Atual", "Anterior", "Delta"])
    w.writerow(
        [
            "Abertos no período",
            v["abertos_periodo"],
            c.get("abertos_anterior", ""),
            _delta(v["abertos_periodo"], c.get("abertos_anterior")),
        ]
    )
    w.writerow(["Ativos agora", v["ativos_hoje"], "", "snapshot"])
    w.writerow(
        [
            "Externos no período",
            v["externos_periodo"],
            c.get("externos_anterior", ""),
            _delta(v["externos_periodo"], c.get("externos_anterior")),
        ]
    )
    w.writerow(
        [
            "Sigilosos no período",
            v["sigilosos_periodo"],
            c.get("sigilosos_anterior", ""),
            _delta(v["sigilosos_periodo"], c.get("sigilosos_anterior")),
        ]
    )
    w.writerow([])

    # Conclusão
    co = payload["conclusao"]
    w.writerow(["[Conclusão]"])
    w.writerow(["Métrica", "Atual", "Anterior", "Delta"])
    w.writerow(
        [
            "Arquivados no período",
            co["arquivados_periodo"],
            c.get("arquivados_anterior", ""),
            _delta(co["arquivados_periodo"], c.get("arquivados_anterior")),
        ]
    )
    w.writerow(
        [
            "Taxa de conclusão (%)",
            co["taxa_conclusao_pct"] if co["taxa_conclusao_pct"] is not None else "",
            c.get("taxa_conclusao_pct_anterior", ""),
            "",
        ]
    )
    w.writerow(
        [
            "Tempo médio (dias)",
            f"{co['tempo_medio_dias']:.1f}" if co["tempo_medio_dias"] is not None else "",
            f"{c['tempo_medio_dias_anterior']:.1f}"
            if c.get("tempo_medio_dias_anterior") is not None
            else "",
            "",
        ]
    )
    w.writerow([])

    # SLA
    sla = payload["sla"]
    w.writerow(["[SLA]"])
    w.writerow(["Métrica", "Atual", "Anterior", "Delta"])
    w.writerow(["Pendentes (snapshot)", sla["pendentes"], "", "snapshot"])
    w.writerow(
        [
            "Resolvidos no período",
            sla["resolvidos_periodo"],
            c.get("sla_resolvidos_anterior", ""),
            _delta(sla["resolvidos_periodo"], c.get("sla_resolvidos_anterior")),
        ]
    )
    w.writerow([])

    # Breakdowns
    for titulo, key in [
        ("[Por tipo de processo]", "por_tipo"),
        ("[Por assunto]", "por_assunto"),
        ("[Por unidade]", "por_unidade"),
    ]:
        w.writerow([titulo])
        w.writerow(["Categoria", "Contagem"])
        for item in payload.get(key, []):
            w.writerow([item["label"], item["count"]])
        w.writerow([])

    # Série temporal
    w.writerow(["[Série temporal (abertos por dia)]"])
    w.writerow(["Data", "Contagem"])
    for ponto in payload.get("serie_temporal", []):
        # ISO "2026-05-23T00:00:00" → "2026-05-23"
        dia = ponto["dia"][:10] if isinstance(ponto["dia"], str) else ponto["dia"]
        w.writerow([dia, ponto["count"]])
    w.writerow([])

    # PR 5a — seções novas append-only.
    doc = payload.get("documental") or {}
    if doc:
        w.writerow(["[Documental]"])
        w.writerow(["Métrica", "Valor"])
        w.writerow(["Processos com serviço (período)", doc.get("com_id_servico_periodo", 0)])
        w.writerow(["Processos sem serviço — legado (período)", doc.get("sem_id_servico_periodo", 0)])
        w.writerow(["Checklist pendente", doc.get("checklist_pendente", 0)])
        w.writerow(["Checklist parcial", doc.get("checklist_parcial", 0)])
        w.writerow(["Checklist completo", doc.get("checklist_completo", 0)])
        # PR 5a-fix: separado do completo.
        w.writerow(["Sem documentos exigidos", doc.get("sem_documentos_exigidos", 0)])
        w.writerow([])

    comp = payload.get("complementacao") or {}
    if comp:
        w.writerow(["[Complementação]"])
        w.writerow(["Métrica", "Valor"])
        w.writerow(["Abertas agora", comp.get("abertas_agora", 0)])
        w.writerow(["Solicitadas no período", comp.get("solicitadas_periodo", 0)])
        w.writerow(["Respondidas no período", comp.get("respondidas_periodo", 0)])
        w.writerow(["Canceladas no período", comp.get("canceladas_periodo", 0)])
        w.writerow(["Processos com complementação aberta", comp.get("processos_com_aberta_agora", 0)])
        tmr = comp.get("tempo_medio_resposta_dias")
        w.writerow(
            ["Tempo médio de resposta (dias)", f"{tmr:.1f}" if tmr is not None else ""]
        )
        w.writerow([])

    por_servico = payload.get("por_servico") or []
    if por_servico:
        w.writerow(["[Por serviço]"])
        w.writerow(
            [
                "id_servico",
                "Serviço",
                "Processos",
                "Compl. abertas",
                "Compl. respondidas",
                "Checklist pendente",
                "Checklist parcial",
                "Checklist completo",
                # PR 5a-fix.
                "Sem documentos exigidos",
            ]
        )
        for it in por_servico:
            w.writerow(
                [
                    it.get("id_servico") if it.get("id_servico") is not None else "",
                    it.get("nome", ""),
                    it.get("count", 0),
                    it.get("complementacoes_abertas", 0),
                    it.get("complementacoes_respondidas_periodo", 0),
                    it.get("checklist_pendente", 0),
                    it.get("checklist_parcial", 0),
                    it.get("checklist_completo", 0),
                    it.get("sem_documentos_exigidos", 0),
                ]
            )

    return buf.getvalue()


def to_pdf(payload: dict[str, Any], nome_tenant: str = "") -> bytes:
    """Gera PDF visual do dashboard. A4 vertical."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Dashboard executivo",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "h1", parent=styles["Heading1"], textColor=APRIMORA, fontSize=18, spaceAfter=4
    )
    h2 = ParagraphStyle(
        "h2",
        parent=styles["Heading2"],
        textColor=APRIMORA,
        fontSize=12,
        spaceAfter=4,
        spaceBefore=8,
    )
    small = ParagraphStyle(
        "small", parent=styles["Normal"], fontSize=8, textColor=GRAY
    )
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=9, leading=11)

    story: list = []
    story.append(Paragraph("APRIMORA — Dashboard executivo", h1))
    sub = []
    if nome_tenant:
        sub.append(nome_tenant)
    sub.append(f"Últimos {payload['periodo_dias']} dias")
    sub.append(
        f"Unidade: {payload.get('id_unidade') or 'Todas'}"
    )
    sub.append(f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    story.append(Paragraph(" · ".join(sub), small))
    story.append(Spacer(1, 0.4 * cm))

    v = payload["volume"]
    co = payload["conclusao"]
    sla = payload["sla"]
    c = payload.get("comparativo", {})

    # 6 cards em grid 3x2 — usa Table com 3 colunas
    def card(label: str, value: str, delta_str: str | None) -> Table:
        rows = [
            [Paragraph(f"<font size=8 color='#6b7280'>{label}</font>", normal)],
            [Paragraph(f"<font size=18 color='#1e3a5f'><b>{value}</b></font>", normal)],
        ]
        if delta_str:
            color = (
                "#16a34a"
                if delta_str.startswith("+") and not delta_str.startswith("+∞")
                else "#dc2626"
                if delta_str.startswith("-")
                else "#6b7280"
            )
            rows.append(
                [
                    Paragraph(
                        f"<font size=8 color='{color}'>{delta_str} vs anterior</font>",
                        normal,
                    )
                ]
            )
        t = Table(rows, colWidths=[5.5 * cm])
        t.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, GRAY),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("PADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return t

    cards = [
        card(
            "Abertos no período",
            _fmt_num(v["abertos_periodo"]),
            _delta(v["abertos_periodo"], c.get("abertos_anterior")),
        ),
        card("Ativos agora", _fmt_num(v["ativos_hoje"]), None),
        card(
            "Concluídos",
            _fmt_num(co["arquivados_periodo"]),
            _delta(co["arquivados_periodo"], c.get("arquivados_anterior")),
        ),
        card(
            "Tempo médio (d)",
            _fmt_num(co["tempo_medio_dias"], 1)
            if co["tempo_medio_dias"] is not None
            else "—",
            None,
        ),
        card("SLA pendentes", _fmt_num(sla["pendentes"]), None),
        card(
            "SLA resolvidos",
            _fmt_num(sla["resolvidos_periodo"]),
            _delta(sla["resolvidos_periodo"], c.get("sla_resolvidos_anterior")),
        ),
    ]
    grid = Table(
        [
            [cards[0], cards[1], cards[2]],
            [cards[3], cards[4], cards[5]],
        ],
        colWidths=[6 * cm, 6 * cm, 6 * cm],
    )
    grid.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(grid)
    story.append(Spacer(1, 0.4 * cm))

    # Breakdowns como tabelas
    def breakdown_table(titulo: str, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        story.append(Paragraph(titulo, h2))
        rows = [["Categoria", "Contagem"]]
        for it in items:
            rows.append([it["label"], _fmt_num(it["count"])])
        t = Table(rows, colWidths=[12 * cm, 3 * cm], repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), APRIMORA),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                    ("GRID", (0, 0), (-1, -1), 0.25, GRAY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

    breakdown_table("Top 5 — por tipo de processo", payload.get("por_tipo", []))
    breakdown_table("Top 10 — por assunto", payload.get("por_assunto", []))
    breakdown_table("Top 10 — por unidade", payload.get("por_unidade", []))

    # PR 5a — seções novas append-only.
    doc_kpis = payload.get("documental") or {}
    if doc_kpis:
        story.append(Paragraph("Documental (PR 5a)", h2))
        rows = [
            ["Métrica", "Valor"],
            ["Processos com serviço (período)", _fmt_num(doc_kpis.get("com_id_servico_periodo", 0))],
            ["Processos sem serviço — legado (período)", _fmt_num(doc_kpis.get("sem_id_servico_periodo", 0))],
            ["Checklist pendente", _fmt_num(doc_kpis.get("checklist_pendente", 0))],
            ["Checklist parcial", _fmt_num(doc_kpis.get("checklist_parcial", 0))],
            ["Checklist completo", _fmt_num(doc_kpis.get("checklist_completo", 0))],
            # PR 5a-fix.
            ["Sem documentos exigidos", _fmt_num(doc_kpis.get("sem_documentos_exigidos", 0))],
        ]
        t = Table(rows, colWidths=[12 * cm, 3 * cm], repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), APRIMORA),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                    ("GRID", (0, 0), (-1, -1), 0.25, GRAY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

    comp_kpis = payload.get("complementacao") or {}
    if comp_kpis:
        story.append(Paragraph("Complementação (PR 5a)", h2))
        tmr = comp_kpis.get("tempo_medio_resposta_dias")
        rows = [
            ["Métrica", "Valor"],
            ["Abertas agora", _fmt_num(comp_kpis.get("abertas_agora", 0))],
            ["Solicitadas no período", _fmt_num(comp_kpis.get("solicitadas_periodo", 0))],
            ["Respondidas no período", _fmt_num(comp_kpis.get("respondidas_periodo", 0))],
            ["Canceladas no período", _fmt_num(comp_kpis.get("canceladas_periodo", 0))],
            ["Processos com complementação aberta", _fmt_num(comp_kpis.get("processos_com_aberta_agora", 0))],
            ["Tempo médio de resposta (dias)", _fmt_num(tmr, 1) if tmr is not None else "—"],
        ]
        t = Table(rows, colWidths=[12 * cm, 3 * cm], repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), APRIMORA),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                    ("GRID", (0, 0), (-1, -1), 0.25, GRAY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

    por_servico = payload.get("por_servico") or []
    if por_servico:
        story.append(Paragraph("Por serviço — top 10 + legado (PR 5a)", h2))
        rows = [
            [
                "Serviço",
                "Proc.",
                "Compl. abertas",
                "Compl. resp.",
                "Pend.",
                "Parcial",
                "Compl.",
                # PR 5a-fix.
                "S/Docs",
            ]
        ]
        for it in por_servico:
            rows.append(
                [
                    it.get("nome", ""),
                    _fmt_num(it.get("count", 0)),
                    _fmt_num(it.get("complementacoes_abertas", 0)),
                    _fmt_num(it.get("complementacoes_respondidas_periodo", 0)),
                    _fmt_num(it.get("checklist_pendente", 0)),
                    _fmt_num(it.get("checklist_parcial", 0)),
                    _fmt_num(it.get("checklist_completo", 0)),
                    _fmt_num(it.get("sem_documentos_exigidos", 0)),
                ]
            )
        t = Table(
            rows,
            colWidths=[5.0 * cm, 1.3 * cm, 2.0 * cm, 2.0 * cm, 1.2 * cm, 1.2 * cm, 1.2 * cm, 1.2 * cm],
            repeatRows=1,
        )
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), APRIMORA),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                    ("GRID", (0, 0), (-1, -1), 0.25, GRAY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

    doc.build(story)
    return buf.getvalue()
