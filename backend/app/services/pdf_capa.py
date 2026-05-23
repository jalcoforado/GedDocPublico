"""Geração de capa de processo em PDF.

Espelha o `Imprimir::capaProcesso()` do PHP, mas usa reportlab em vez de mpdf.
Estrutura simples: cabeçalho com brasão/título, número do processo grande,
metadados (manifestante, assunto, abertura, unidade), observação se houver,
rodapé com data de impressão.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from ..schemas.processo import ProcessoDetail


APRIMORA = HexColor("#1e3a5f")
GRAY = HexColor("#6b7280")


def _draw_label(c: canvas.Canvas, x: float, y: float, label: str, value: str, w: float):
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(x, y + 0.45 * cm, label.upper())
    c.setFillColor(HexColor("#111111"))
    c.setFont("Helvetica", 11)
    # quebra simples por largura
    text = value or "—"
    if c.stringWidth(text, "Helvetica", 11) > w:
        # corta com elipse
        while text and c.stringWidth(text + "…", "Helvetica", 11) > w:
            text = text[:-1]
        text += "…"
    c.drawString(x, y, text)


def gerar_capa_pdf(processo: ProcessoDetail) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 2 * cm

    # Cabeçalho colorido
    c.setFillColor(APRIMORA)
    c.rect(0, height - 3.5 * cm, width, 3.5 * cm, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin, height - 2.0 * cm, "APRIMORA")
    c.setFont("Helvetica", 10)
    c.drawString(margin, height - 2.6 * cm, "Capa de Processo Administrativo")
    c.setFont("Helvetica", 9)
    c.drawRightString(width - margin, height - 2.0 * cm, datetime.now().strftime("Emitida em %d/%m/%Y %H:%M"))

    # Caixa com número do processo
    box_y = height - 6.5 * cm
    c.setFillColor(HexColor("#f3f4f6"))
    c.rect(margin, box_y, width - 2 * margin, 2.0 * cm, fill=1, stroke=0)
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 8)
    c.drawString(margin + 0.3 * cm, box_y + 1.4 * cm, "NÚMERO DO PROCESSO")
    c.setFillColor(APRIMORA)
    c.setFont("Courier-Bold", 22)
    c.drawString(margin + 0.3 * cm, box_y + 0.4 * cm, processo.numero_processo)

    # Dados principais (grid 2 colunas)
    col_w = (width - 2 * margin - 0.5 * cm) / 2
    col1_x = margin
    col2_x = margin + col_w + 0.5 * cm
    y = box_y - 1.5 * cm

    line_h = 1.4 * cm

    _draw_label(c, col1_x, y, "Aberto em", processo.data_hora_abertura.strftime("%d/%m/%Y %H:%M") if processo.data_hora_abertura else "—", col_w)
    _draw_label(c, col2_x, y, "Tipo de processo", processo.tipo_processo or "—", col_w)
    y -= line_h

    _draw_label(c, col1_x, y, "Manifestante", processo.manifestante or "—", col_w)
    _draw_label(c, col2_x, y, "CPF/CNPJ", processo.manifestante_cpf_cnpj or "—", col_w)
    y -= line_h

    _draw_label(c, col1_x, y, "Unidade proprietária", processo.unidade_proprietaria or "—", col_w)
    _draw_label(c, col2_x, y, "Local atual", processo.local_atual or "—", col_w)
    y -= line_h

    _draw_label(c, col1_x, y, "Número origem", processo.numero_origem or "—", col_w)
    _draw_label(
        c, col2_x, y, "Estado",
        ("Ativo" if processo.ativo else "Inativo")
        + (" · Sigiloso" if not processo.publico else "")
        + (" · Externo" if processo.externo else ""),
        col_w,
    )
    y -= line_h

    # Assunto (largo)
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(col1_x, y, "ASSUNTO")
    y -= 0.55 * cm
    styles = getSampleStyleSheet()
    p_style = ParagraphStyle(
        "assunto",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        textColor=HexColor("#111111"),
        leading=14,
    )
    para = Paragraph(processo.assunto or "—", p_style)
    aw, ah = para.wrap(width - 2 * margin, 4 * cm)
    para.drawOn(c, col1_x, y - ah)
    y -= ah + 0.5 * cm

    # Observação
    if processo.observacao:
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 7)
        c.drawString(col1_x, y, "OBSERVAÇÃO")
        y -= 0.55 * cm
        obs_para = Paragraph(processo.observacao.replace("\n", "<br/>"), p_style)
        aw, ah = obs_para.wrap(width - 2 * margin, height - 4 * cm - (height - y))
        obs_para.drawOn(c, col1_x, y - ah)
        y -= ah + 0.5 * cm

    # Resumo movimentações + anexos
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(col1_x, 3.5 * cm, "RESUMO")
    c.setFillColor(HexColor("#111111"))
    c.setFont("Helvetica", 10)
    c.drawString(
        col1_x, 2.9 * cm,
        f"{len(processo.movimentacoes)} movimentação(ões) · {len(processo.anexos)} anexo(s)",
    )

    # Rodapé
    c.setFillColor(GRAY)
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(width / 2, 1.2 * cm, "Documento gerado eletronicamente pelo sistema Aprimora")
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 0.7 * cm, f"Processo {processo.numero_processo}")

    c.showPage()
    c.save()
    return buf.getvalue()
