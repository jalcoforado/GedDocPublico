"""PDF do Relatório de Assinaturas."""
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

from ..schemas.relatorio_assinaturas import RelatorioAssinaturasResposta

APRIMORA = HexColor("#1e3a5f")
GRAY = HexColor("#6b7280")
LIGHT = HexColor("#f3f4f6")


def _fmt_min(m: int | float | None) -> str:
    if m is None:
        return "—"
    m = int(m)
    if m < 60:
        return f"{m} min"
    h = m // 60
    rem = m % 60
    if h < 24:
        return f"{h}h {rem:02d}min"
    d = h // 24
    rh = h % 24
    return f"{d}d {rh}h"


def _fmt_dt(d: datetime | None) -> str:
    if not d:
        return "—"
    return d.strftime("%d/%m/%Y %H:%M")


_STATUS_LABEL = {
    "pendente": "Pendente",
    "concluida": "Concluída",
    "cancelada": "Cancelada",
}


def gerar_assinaturas_pdf(r: RelatorioAssinaturasResposta) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Relatório de assinaturas",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=APRIMORA, fontSize=18, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=APRIMORA, fontSize=12, spaceAfter=4)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=GRAY)
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=9, leading=11)

    story: list = []
    story.append(Paragraph("APRIMORA — Relatório de assinaturas", h1))
    story.append(Paragraph(f"Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')}", small))
    story.append(Spacer(1, 0.3 * cm))

    f = r.filtros_aplicados
    filtros_txt = []
    if f.desde:
        filtros_txt.append(f"<b>Desde:</b> {f.desde.strftime('%d/%m/%Y')}")
    if f.ate:
        filtros_txt.append(f"<b>Até:</b> {f.ate.strftime('%d/%m/%Y')}")
    if f.status:
        filtros_txt.append(f"<b>Status:</b> {_STATUS_LABEL.get(f.status, f.status)}")
    if f.id_solicitante:
        filtros_txt.append(f"<b>Solicitante:</b> #{f.id_solicitante}")
    if f.id_assinante:
        filtros_txt.append(f"<b>Assinante:</b> #{f.id_assinante}")
    if not filtros_txt:
        filtros_txt.append("Sem filtros")
    story.append(Paragraph(" · ".join(filtros_txt), normal))
    story.append(Spacer(1, 0.3 * cm))

    # Totais
    t = r.totais
    resumo = [
        ["Total", "Pendentes", "Concluídas", "Canceladas", "Tempo médio"],
        [
            str(t.total),
            str(t.pendentes),
            str(t.concluidas),
            str(t.canceladas),
            _fmt_min(t.minutos_medio_conclusao),
        ],
    ]
    tab_resumo = Table(resumo, colWidths=[5 * cm] * 5)
    tab_resumo.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                ("TEXTCOLOR", (0, 0), (-1, 0), GRAY),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 14),
                ("TEXTCOLOR", (0, 1), (-1, 1), APRIMORA),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(tab_resumo)
    story.append(Spacer(1, 0.4 * cm))

    # Por assinante
    story.append(Paragraph("Por assinante", h2))
    if r.por_assinante:
        data = [["Assinante", "Pendentes", "Concluídas", "Tempo médio"]]
        for a in r.por_assinante:
            data.append([
                Paragraph(a.nome or f"#{a.id_assinante}", normal),
                str(a.pendentes),
                str(a.concluidas),
                _fmt_min(a.minutos_medio),
            ])
        tab = Table(data, colWidths=[13 * cm, 3 * cm, 3 * cm, 4 * cm], repeatRows=1)
        tab.setStyle(_table_style())
        story.append(tab)
    else:
        story.append(Paragraph("Sem dados.", small))
    story.append(Spacer(1, 0.4 * cm))

    # Por solicitante
    story.append(Paragraph("Por solicitante", h2))
    if r.por_solicitante:
        data = [["Solicitante", "Total", "Pendentes", "Concluídas", "Canceladas"]]
        for s in r.por_solicitante:
            data.append([
                Paragraph(s.nome or f"#{s.id_solicitante}", normal),
                str(s.total),
                str(s.pendentes),
                str(s.concluidas),
                str(s.canceladas),
            ])
        tab = Table(data, colWidths=[10 * cm, 3 * cm, 3 * cm, 3 * cm, 3 * cm], repeatRows=1)
        tab.setStyle(_table_style())
        story.append(tab)
    else:
        story.append(Paragraph("Sem dados.", small))
    story.append(Spacer(1, 0.4 * cm))

    # Lista de solicitações
    story.append(Paragraph(f"Solicitações ({len(r.solicitacoes)})", h2))
    if r.solicitacoes:
        data = [["Processo", "Solicitante", "Status", "Iniciada", "Tempo", "Assinantes", "Anexos"]]
        for s in r.solicitacoes:
            data.append([
                Paragraph(s.numero_processo or f"#{s.id_processo}", normal),
                Paragraph(s.nome_solicitante or "—", normal),
                _STATUS_LABEL[s.status],
                _fmt_dt(s.dt_inicio),
                _fmt_min(s.minutos_decorridos),
                f"{s.qtd_assinantes_concluidos}/{s.qtd_assinantes}",
                f"{s.qtd_anexos_assinados}/{s.qtd_anexos}",
            ])
        tab = Table(
            data,
            colWidths=[4 * cm, 5 * cm, 2.5 * cm, 3.5 * cm, 3 * cm, 3 * cm, 3 * cm],
            repeatRows=1,
        )
        tab.setStyle(_table_style())
        story.append(tab)
    else:
        story.append(Paragraph("Nenhuma solicitação no recorte.", small))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _footer(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(GRAY)
    canvas_obj.drawString(1.5 * cm, 1.0 * cm, "Documento gerado eletronicamente pelo Aprimora")
    canvas_obj.drawRightString(doc.pagesize[0] - 1.5 * cm, 1.0 * cm, f"Página {doc.page}")
    canvas_obj.restoreState()


def _table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), APRIMORA),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
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
