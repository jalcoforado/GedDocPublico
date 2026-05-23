"""Geração de etiquetas físicas (única / dupla) com código de barras Code128.

Espelha `Imprimir::etiquetaUnica` e `etiquetaDupla` do PHP. Layout simples:
- Cabeçalho com número grande
- Barcode Code128 do número do processo
- Linhas com manifestante e data de abertura
- A "dupla" é só a mesma etiqueta repetida verticalmente numa folha A4.
"""
from __future__ import annotations

from io import BytesIO

from reportlab.graphics.barcode import code128
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas

from ..schemas.processo import ProcessoDetail

APRIMORA = HexColor("#1e3a5f")
GRAY = HexColor("#6b7280")

# Tamanho de etiqueta padrão tipo Pimaco 6182: ~99.0mm x 38.1mm.
ETIQUETA_W = 99.0 * mm
ETIQUETA_H = 38.1 * mm


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _draw_etiqueta(c: canvas.Canvas, x: float, y: float, processo: ProcessoDetail) -> None:
    """Desenha uma etiqueta com origem no canto inferior-esquerdo (x,y)."""
    # Borda fina
    c.setStrokeColor(GRAY)
    c.setLineWidth(0.3)
    c.rect(x, y, ETIQUETA_W, ETIQUETA_H)

    # Header pequeno
    c.setFillColor(APRIMORA)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 3 * mm, y + ETIQUETA_H - 4 * mm, "APRIMORA · PROCESSO ADMINISTRATIVO")

    # Número grande
    c.setFillColor(HexColor("#111111"))
    c.setFont("Courier-Bold", 14)
    c.drawString(x + 3 * mm, y + ETIQUETA_H - 11 * mm, processo.numero_processo)

    # Code128 abaixo do número
    barcode = code128.Code128(processo.numero_processo, barHeight=10 * mm, barWidth=0.32 * mm)
    bc_w = barcode.width
    bx = x + 3 * mm
    by = y + ETIQUETA_H - 24 * mm
    if bc_w > ETIQUETA_W - 6 * mm:
        # Encolhe se passar do limite
        ratio = (ETIQUETA_W - 6 * mm) / bc_w
        barcode = code128.Code128(
            processo.numero_processo,
            barHeight=10 * mm,
            barWidth=0.32 * mm * ratio,
        )
    barcode.drawOn(c, bx, by)

    # Manifestante + data abaixo
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 6.5)
    c.drawString(x + 3 * mm, y + 7 * mm, "MANIFESTANTE")
    c.setFillColor(HexColor("#111111"))
    c.setFont("Helvetica", 9)
    c.drawString(x + 3 * mm, y + 3.5 * mm, _truncate(processo.manifestante or "—", 48))

    if processo.data_hora_abertura:
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 6.5)
        data_str = processo.data_hora_abertura.strftime("%d/%m/%Y")
        c.drawRightString(x + ETIQUETA_W - 3 * mm, y + 3.5 * mm, f"Aberto: {data_str}")


def gerar_etiqueta_pdf(processo: ProcessoDetail, *, dupla: bool = False) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    # Centraliza horizontalmente; uma etiqueta no topo, opcionalmente duas
    x = (page_w - ETIQUETA_W) / 2
    y_top = page_h - 2 * cm - ETIQUETA_H

    _draw_etiqueta(c, x, y_top, processo)

    if dupla:
        y_bottom = y_top - ETIQUETA_H - 5 * mm
        _draw_etiqueta(c, x, y_bottom, processo)

    c.showPage()
    c.save()
    return buf.getvalue()
