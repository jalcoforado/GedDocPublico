"""PDF do Relatório de Tramitação."""
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

from ..schemas.relatorio_tramitacao import RelatorioTramitacaoResposta

APRIMORA = HexColor("#1e3a5f")
GRAY = HexColor("#6b7280")
LIGHT = HexColor("#f3f4f6")
RED = HexColor("#b91c1c")


def _fmt_min(m: int | float) -> str:
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


def gerar_tramitacao_pdf(r: RelatorioTramitacaoResposta) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Relatório de tramitação",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "h1", parent=styles["Heading1"], textColor=APRIMORA, fontSize=18, spaceAfter=4
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"], textColor=APRIMORA, fontSize=12, spaceAfter=4
    )
    h3 = ParagraphStyle(
        "h3", parent=styles["Heading3"], textColor=APRIMORA, fontSize=10, spaceAfter=2
    )
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=GRAY)
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=9, leading=11)

    story: list = []
    story.append(Paragraph("APRIMORA — Relatório de tramitação", h1))
    story.append(Paragraph(f"Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')}", small))
    story.append(Spacer(1, 0.3 * cm))

    f = r.filtros_aplicados
    filtros_txt = []
    if r.nome_unidade:
        filtros_txt.append(f"<b>Unidade:</b> {r.nome_unidade}")
    if f.desde:
        filtros_txt.append(f"<b>Desde:</b> {f.desde.strftime('%d/%m/%Y')}")
    if f.ate:
        filtros_txt.append(f"<b>Até:</b> {f.ate.strftime('%d/%m/%Y')}")
    if f.apenas_ativos:
        filtros_txt.append("<b>Apenas ativos</b>")
    if not filtros_txt:
        filtros_txt.append("Sem filtros")
    story.append(Paragraph(" · ".join(filtros_txt), normal))
    story.append(Spacer(1, 0.3 * cm))

    # Resumo
    resumo = [
        ["Processos", "Com atraso", "Tempo médio"],
        [
            str(r.qtd_processos),
            str(r.qtd_processos_com_atraso),
            _fmt_min(r.minutos_medio_por_processo),
        ],
    ]
    tab_resumo = Table(resumo, colWidths=[6 * cm, 6 * cm, 6 * cm])
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

    # Por unidade
    story.append(Paragraph("Tempo por unidade", h2))
    if r.por_unidade:
        un_data = [["Unidade", "Passagens", "Atrasos", "Tempo total", "Tempo médio"]]
        for u in r.por_unidade:
            un_data.append(
                [
                    Paragraph(u.unidade or "—", normal),
                    str(u.qtd_passagens),
                    str(u.qtd_atrasos),
                    _fmt_min(u.minutos_total),
                    _fmt_min(u.minutos_medio),
                ]
            )
        tab = Table(un_data, colWidths=[10 * cm, 3 * cm, 3 * cm, 4.5 * cm, 4.5 * cm], repeatRows=1)
        tab.setStyle(_table_style())
        story.append(tab)
    else:
        story.append(Paragraph("Sem dados.", small))
    story.append(Spacer(1, 0.5 * cm))

    # Processos detalhados
    story.append(Paragraph(f"Processos ({len(r.processos)})", h2))
    for p in r.processos:
        atraso_txt = (
            f"<font color='#b91c1c'><b>{p.qtd_atrasos} atraso(s)</b></font>"
            if p.teve_atraso
            else "sem atrasos"
        )
        header_txt = (
            f"<b>{p.numero_processo}</b> · {p.manifestante or '—'} · "
            f"{p.qtd_encaminhamentos} encaminhamento(s) · "
            f"{p.qtd_unidades_visitadas} unidade(s) · "
            f"tempo total: {_fmt_min(p.minutos_total)} "
            f"+ andamento {_fmt_min(p.minutos_em_andamento)} · {atraso_txt}"
        )
        story.append(Paragraph(header_txt, h3))

        if p.etapas:
            et_data = [["Unidade", "Chegou", "Saiu", "Tempo", "Prazo", "Status"]]
            for e in p.etapas:
                status = ""
                if e.atrasou:
                    status = "ATRASO"
                elif e.saiu_em is None:
                    status = "Em andamento"
                tempo_txt = _fmt_min(e.minutos_no_local) if e.minutos_no_local is not None else "—"
                et_data.append(
                    [
                        Paragraph(e.unidade or "—", normal),
                        _fmt_dt(e.chegou_em),
                        _fmt_dt(e.saiu_em),
                        tempo_txt,
                        _fmt_dt(e.prazo_estipulado),
                        status,
                    ]
                )
            et_tab = Table(
                et_data,
                colWidths=[7 * cm, 3.5 * cm, 3.5 * cm, 3 * cm, 3.5 * cm, 4.5 * cm],
                repeatRows=1,
            )
            et_tab.setStyle(_table_style(secondary=True))
            story.append(et_tab)
        story.append(Spacer(1, 0.3 * cm))

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


def _table_style(secondary: bool = False) -> TableStyle:
    header_bg = HexColor("#e5e7eb") if secondary else APRIMORA
    header_fg = HexColor("#111111") if secondary else colors.white
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), header_fg),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
    )
