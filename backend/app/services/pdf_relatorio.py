"""PDF do Relatório de processos por unidade/período.

Layout: cabeçalho + bloco de filtros + cards de totais + duas tabelinhas de
breakdown + tabela completa de processos. Quebra de página automática via
Platypus (SimpleDocTemplate + Table).
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..schemas.relatorio import RelatorioResposta

APRIMORA = HexColor("#1e3a5f")
GRAY = HexColor("#6b7280")
LIGHT = HexColor("#f3f4f6")


def _fmt_dt(d: datetime | None) -> str:
    if not d:
        return "—"
    return d.strftime("%d/%m/%Y %H:%M")


def _fmt_d(d: datetime | None) -> str:
    if not d:
        return "—"
    return d.strftime("%d/%m/%Y")


def gerar_relatorio_pdf(r: RelatorioResposta) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Relatório de processos",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "h1", parent=styles["Heading1"], textColor=APRIMORA, fontSize=18, spaceAfter=4
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"], textColor=APRIMORA, fontSize=12, spaceAfter=4
    )
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=GRAY)
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=9, leading=11)

    story: list = []

    # Cabeçalho
    story.append(Paragraph("APRIMORA — Relatório de processos", h1))
    story.append(
        Paragraph(
            f"Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            small,
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    # Filtros aplicados
    f = r.filtros_aplicados
    filtros_txt = []
    if r.nome_unidade:
        filtros_txt.append(f"<b>Unidade:</b> {r.nome_unidade}")
    if f.desde:
        filtros_txt.append(f"<b>Desde:</b> {_fmt_d(f.desde)}")
    if f.ate:
        filtros_txt.append(f"<b>Até:</b> {_fmt_d(f.ate)}")
    if f.apenas_ativos:
        filtros_txt.append("<b>Apenas ativos</b>")
    if not filtros_txt:
        filtros_txt.append("Sem filtros (todos os processos)")
    story.append(Paragraph(" · ".join(filtros_txt), normal))
    story.append(Spacer(1, 0.4 * cm))

    # Totais (linha de cards)
    t = r.totais
    totals_data = [
        ["Total", "Ativos", "Inativos", "Sigilosos", "Externos"],
        [str(t.total), str(t.ativos), str(t.inativos), str(t.sigilosos), str(t.externos)],
    ]
    totals = Table(totals_data, colWidths=[5 * cm] * 5)
    totals.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                ("TEXTCOLOR", (0, 0), (-1, 0), GRAY),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 16),
                ("TEXTCOLOR", (0, 1), (-1, 1), APRIMORA),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(totals)
    story.append(Spacer(1, 0.4 * cm))

    # Breakdown por tipo de processo
    story.append(Paragraph("Por tipo de processo", h2))
    if r.por_tipo_processo:
        tp_data = [["Tipo", "Quantidade", "%"]]
        for item in r.por_tipo_processo:
            tp_data.append([item.label, str(item.count), f"{item.pct:.1f}%"])
        tp = Table(tp_data, colWidths=[15 * cm, 4 * cm, 3 * cm])
        tp.setStyle(_table_style())
        story.append(tp)
    else:
        story.append(Paragraph("Sem dados.", small))
    story.append(Spacer(1, 0.4 * cm))

    # Breakdown por unidade proprietária
    story.append(Paragraph("Por unidade proprietária", h2))
    if r.por_unidade_proprietaria:
        un_data = [["Unidade", "Quantidade", "%"]]
        for item in r.por_unidade_proprietaria:
            un_data.append([item.label, str(item.count), f"{item.pct:.1f}%"])
        un = Table(un_data, colWidths=[15 * cm, 4 * cm, 3 * cm])
        un.setStyle(_table_style())
        story.append(un)
    else:
        story.append(Paragraph("Sem dados.", small))
    story.append(Spacer(1, 0.5 * cm))

    # Lista completa
    story.append(Paragraph(f"Processos ({len(r.processos)})", h2))
    if r.processos:
        rows_data = [
            ["Número", "Aberto em", "Manifestante", "Tipo", "Unid. propr.", "Local atual", "Status"]
        ]
        for p in r.processos:
            status = "Ativo" if p.ativo else "Inativo"
            if not p.publico:
                status += " · Sigiloso"
            if p.externo:
                status += " · Externo"
            rows_data.append(
                [
                    Paragraph(p.numero_processo, normal),
                    _fmt_dt(p.data_hora_abertura),
                    Paragraph(p.manifestante or "—", normal),
                    Paragraph(p.tipo_processo or "—", normal),
                    Paragraph(p.unidade_proprietaria or "—", normal),
                    Paragraph(p.local_atual or "—", normal),
                    Paragraph(status, normal),
                ]
            )
        tbl = Table(
            rows_data,
            colWidths=[4 * cm, 2.8 * cm, 5 * cm, 3.5 * cm, 4.5 * cm, 4.5 * cm, 3.2 * cm],
            repeatRows=1,
        )
        tbl.setStyle(_table_style())
        story.append(tbl)
    else:
        story.append(Paragraph("Nenhum processo no recorte.", small))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _footer(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(GRAY)
    canvas_obj.drawString(1.5 * cm, 1.0 * cm, "Documento gerado eletronicamente pelo Aprimora")
    canvas_obj.drawRightString(
        doc.pagesize[0] - 1.5 * cm,
        1.0 * cm,
        f"Página {doc.page}",
    )
    canvas_obj.restoreState()


def _table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), APRIMORA),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (-1, 0), "LEFT"),
            ("ALIGN", (1, 1), (1, -1), "CENTER"),
            ("ALIGN", (2, 1), (2, -1), "RIGHT"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
    )
