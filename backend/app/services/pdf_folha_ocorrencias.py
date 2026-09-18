"""Folha de ocorrências (F7, benchmark SUiTE).

PDF legível da trilha do processo — Data/Hora · Ocorrência · Usuário/Unidade
· Observação — pra anexar a um procedimento sem exigir acesso ao sistema.
O dado é o MESMO que a aba "Movimentações" já mostra (`ProcessoDetail.
movimentacoes`, `services/processos.py::_load_movimentacoes`): a folha é uma
saída impressa dele, não uma segunda fonte de verdade reconstruída a partir
do `audit_log` cru — que tem `acao` em código de máquina
(`"processo.encaminhado"`) e não o rótulo que o catálogo `protocolos.acao`
já resolve.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..schemas.processo import ProcessoDetail

APRIMORA = HexColor("#1e3a5f")
GRAY = HexColor("#6b7280")
LIGHT = HexColor("#f3f4f6")


def _fmt_dt(d: datetime) -> str:
    return d.strftime("%d/%m/%Y %H:%M")


def gerar_folha_ocorrencias_pdf(processo: ProcessoDetail) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Folha de ocorrências — {processo.numero_processo}",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "h1", parent=styles["Heading1"], textColor=APRIMORA, fontSize=16, spaceAfter=4
    )
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=GRAY)
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=8.5, leading=11)

    story: list = []

    story.append(Paragraph("APRIMORA — Folha de ocorrências", h1))
    story.append(
        Paragraph(
            f"Processo {processo.nup or processo.numero_processo}"
            + (f" ({processo.numero_processo})" if processo.nup else ""),
            styles["Heading2"],
        )
    )
    cabecalho = [
        f"<b>Assunto:</b> {processo.assunto or '—'}",
        f"<b>Manifestante:</b> {processo.manifestante or '—'}",
        f"<b>Aberto em:</b> {_fmt_dt(processo.data_hora_abertura)}",
    ]
    story.append(Paragraph(" · ".join(cabecalho), normal))
    story.append(
        Paragraph(f"Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')}", small)
    )
    story.append(Spacer(1, 0.5 * cm))

    if processo.movimentacoes:
        rows_data = [["Data/Hora", "Ocorrência", "Usuário/Unidade", "Observação"]]
        # `_load_movimentacoes` devolve mais recente primeiro (pra timeline na
        # tela); a folha impressa é um HISTÓRICO — lê-se do mais antigo pro
        # mais recente, como qualquer trilha de auditoria.
        for m in reversed(processo.movimentacoes):
            usuario_unidade = " / ".join(
                filter(None, [m.usuario, m.unidade_responsavel])
            ) or "—"
            observacao = m.despacho.despacho if m.despacho else "—"
            rows_data.append(
                [
                    _fmt_dt(m.data_hora_movimentacao),
                    Paragraph(m.acao, normal),
                    Paragraph(usuario_unidade, normal),
                    Paragraph(observacao, normal),
                ]
            )
        tbl = Table(
            rows_data,
            colWidths=[3.2 * cm, 3.3 * cm, 4.5 * cm, 6.5 * cm],
            repeatRows=1,
        )
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), APRIMORA),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("BOX", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(tbl)
    else:
        story.append(Paragraph("Sem ocorrências registradas.", small))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _footer(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(GRAY)
    canvas_obj.drawString(1.5 * cm, 1.0 * cm, "Documento gerado eletronicamente pelo Aprimora")
    canvas_obj.drawRightString(
        doc.pagesize[0] - 1.5 * cm, 1.0 * cm, f"Página {doc.page}",
    )
    canvas_obj.restoreState()
