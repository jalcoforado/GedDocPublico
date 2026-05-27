"""PDFs do módulo de Protocolo (Fase P1).

1. `gerar_etiqueta_protocolo` — etiqueta com barcode pra colar no documento físico.
   Diferente da etiqueta de processo padrão (`pdf_etiqueta.py`): aqui o número
   sobressai E a ESPÉCIE DOCUMENTAL é destaque (Ofício / Requerimento / ...).

2. `gerar_comprovante_protocolo` — comprovante 2 vias na mesma folha A4:
   - Via DO MANIFESTANTE (cidadão leva pra casa)
   - Via DA UNIDADE (fica no arquivo)
   Separadas por linha tracejada de corte. Ambas idênticas no conteúdo.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.graphics.barcode import code128
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas

APRIMORA = HexColor("#1e3a5f")
GRAY = HexColor("#6b7280")
LIGHT = HexColor("#f1f5f9")
BORDER = HexColor("#cbd5e1")


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%d/%m/%Y %H:%M")


# ============================================================================
#  ETIQUETA
# ============================================================================

ETIQUETA_W = 99.0 * mm  # padrão Pimaco 6182
ETIQUETA_H = 50.0 * mm  # um pouco mais alta que a etiqueta de processo padrão
                        # pra caber espécie + canal


def _draw_etiqueta_protocolo(
    c: canvas.Canvas,
    x: float,
    y: float,
    *,
    numero_processo: str,
    manifestante: str,
    especie: str | None,
    data_recepcao: datetime | None,
    canal: str | None,
    nup: str | None = None,
) -> None:
    """Desenha 1 etiqueta com origem no canto inferior-esquerdo (x,y).

    Quando `nup` está preenchido, é o identificador em destaque (formato federal)
    + numero_processo legado fica como referência secundária. Sem NUP, mostra
    apenas o numero_processo. O barcode usa o que está em destaque.
    """
    # Borda
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.3)
    c.rect(x, y, ETIQUETA_W, ETIQUETA_H)

    # Banda superior colorida com nome do produto + espécie
    band_h = 6 * mm
    c.setFillColor(APRIMORA)
    c.rect(x, y + ETIQUETA_H - band_h, ETIQUETA_W, band_h, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 7)
    label_topo = "NUP FEDERAL · APRIMORA" if nup else "PROTOCOLO · APRIMORA"
    c.drawString(x + 3 * mm, y + ETIQUETA_H - 4 * mm, label_topo)
    if especie:
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(
            x + ETIQUETA_W - 3 * mm,
            y + ETIQUETA_H - 4 * mm,
            especie.upper(),
        )

    # Número(s)
    identificador_principal = nup or numero_processo
    c.setFillColor(HexColor("#111111"))
    # NUP é 21 chars (17 dígitos + 4 separadores) — usa fonte menor
    fonte_size = 13 if nup else 16
    c.setFont("Courier-Bold", fonte_size)
    c.drawString(x + 3 * mm, y + ETIQUETA_H - 12 * mm, identificador_principal)
    if nup:
        # mostra numero legado abaixo, menor
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 7)
        c.drawString(x + 3 * mm, y + ETIQUETA_H - 16 * mm, f"Legado: {numero_processo}")

    # Code128 (sempre do identificador principal — NUP se houver)
    bc_y = y + ETIQUETA_H - (29 * mm if nup else 27 * mm)
    barcode = code128.Code128(
        identificador_principal, barHeight=10 * mm, barWidth=0.32 * mm
    )
    if barcode.width > ETIQUETA_W - 6 * mm:
        ratio = (ETIQUETA_W - 6 * mm) / barcode.width
        barcode = code128.Code128(
            identificador_principal,
            barHeight=10 * mm,
            barWidth=0.32 * mm * ratio,
        )
    barcode.drawOn(c, x + 3 * mm, bc_y)

    # Recepção + canal
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 6)
    c.drawString(x + 3 * mm, y + 14 * mm, "RECEPÇÃO")
    c.drawString(x + 50 * mm, y + 14 * mm, "CANAL")
    c.setFillColor(HexColor("#111111"))
    c.setFont("Helvetica", 8)
    c.drawString(x + 3 * mm, y + 10 * mm, _fmt_dt(data_recepcao))
    c.drawString(x + 50 * mm, y + 10 * mm, (canal or "—").upper())

    # Manifestante (rodapé)
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 6)
    c.drawString(x + 3 * mm, y + 5 * mm, "MANIFESTANTE")
    c.setFillColor(HexColor("#111111"))
    c.setFont("Helvetica", 8)
    c.drawString(x + 3 * mm, y + 1.5 * mm, _truncate(manifestante, 60))


def gerar_etiqueta_protocolo(
    *,
    numero_processo: str,
    manifestante: str,
    especie: str | None,
    data_recepcao: datetime | None,
    canal: str | None,
    nup: str | None = None,
) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    x = (page_w - ETIQUETA_W) / 2
    y = page_h - 2 * cm - ETIQUETA_H
    _draw_etiqueta_protocolo(
        c,
        x,
        y,
        numero_processo=numero_processo,
        manifestante=manifestante,
        especie=especie,
        data_recepcao=data_recepcao,
        canal=canal,
        nup=nup,
    )
    c.showPage()
    c.save()
    return buf.getvalue()


# ============================================================================
#  COMPROVANTE 2 VIAS
# ============================================================================


def _draw_via(
    c: canvas.Canvas,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    via_label: str,
    numero_processo: str,
    manifestante: str,
    especie: str | None,
    assunto: str,
    unidade: str,
    data_recepcao: datetime | None,
    observacao: str | None,
    operador_nome: str | None,
    nup: str | None = None,
) -> None:
    """Desenha 1 via dentro de um retângulo (x,y é canto inferior-esquerdo)."""
    # Cabeçalho colorido
    band_h = 1.4 * cm
    c.setFillColor(APRIMORA)
    c.rect(x, y + height - band_h, width, band_h, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x + 0.6 * cm, y + height - 0.6 * cm, "COMPROVANTE DE PROTOCOLO")
    c.setFont("Helvetica", 8)
    c.drawString(x + 0.6 * cm, y + height - 1.1 * cm, via_label)
    c.drawRightString(
        x + width - 0.6 * cm,
        y + height - 1.1 * cm,
        datetime.now().strftime("Emitido em %d/%m/%Y %H:%M"),
    )

    # Número grande + barcode
    # Quando há NUP, ele é o identificador em destaque; numero_processo vira legado.
    identificador_principal = nup or numero_processo
    cy = y + height - band_h - 1.3 * cm
    c.setFillColor(HexColor("#111111"))
    # NUP é mais largo (21 chars) — fonte menor
    c.setFont("Courier-Bold", 13 if nup else 16)
    c.drawString(x + 0.6 * cm, cy, identificador_principal)
    if nup:
        # Mostra numero legado abaixo do NUP, mais discreto
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 8)
        c.drawString(x + 0.6 * cm, cy - 0.45 * cm, f"Legado: {numero_processo}")

    bc = code128.Code128(
        identificador_principal, barHeight=8 * mm, barWidth=0.3 * mm
    )
    if bc.width > 5 * cm:
        ratio = 5 * cm / bc.width
        bc = code128.Code128(
            identificador_principal, barHeight=8 * mm, barWidth=0.3 * mm * ratio
        )
    bc.drawOn(c, x + width - 0.6 * cm - bc.width, cy - 0.2 * cm)

    # Linhas de dados (2 colunas)
    y_data = cy - 1.0 * cm
    col_w = (width - 1.6 * cm) / 2

    def _kv(col_x: float, ky: float, label: str, value: str, w: float):
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 6.5)
        c.drawString(col_x, ky + 0.3 * cm, label.upper())
        c.setFillColor(HexColor("#111111"))
        c.setFont("Helvetica", 9)
        text = value or "—"
        if c.stringWidth(text, "Helvetica", 9) > w:
            while text and c.stringWidth(text + "…", "Helvetica", 9) > w:
                text = text[:-1]
            text += "…"
        c.drawString(col_x, ky, text)

    _kv(x + 0.6 * cm, y_data, "Manifestante", manifestante, col_w)
    _kv(x + 0.8 * cm + col_w, y_data, "Espécie", especie or "—", col_w)
    y_data -= 0.85 * cm
    _kv(x + 0.6 * cm, y_data, "Assunto", assunto, col_w)
    _kv(x + 0.8 * cm + col_w, y_data, "Unidade proprietária", unidade, col_w)
    y_data -= 0.85 * cm
    _kv(x + 0.6 * cm, y_data, "Recebido em", _fmt_dt(data_recepcao), col_w)
    _kv(x + 0.8 * cm + col_w, y_data, "Operador", operador_nome or "—", col_w)

    # Observação (se houver)
    if observacao:
        y_data -= 0.95 * cm
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 6.5)
        c.drawString(x + 0.6 * cm, y_data + 0.3 * cm, "OBSERVAÇÃO")
        c.setFillColor(HexColor("#111111"))
        c.setFont("Helvetica", 8)
        # Quebra simples por palavras (linhas de até ~width-1.2cm)
        max_w = width - 1.2 * cm
        words = observacao.split()
        line = ""
        ly = y_data
        for w in words:
            test = (line + " " + w).strip()
            if c.stringWidth(test, "Helvetica", 8) > max_w:
                c.drawString(x + 0.6 * cm, ly, line)
                ly -= 0.35 * cm
                line = w
                if ly < y + 1.2 * cm:
                    break
            else:
                line = test
        if line and ly >= y + 1.2 * cm:
            c.drawString(x + 0.6 * cm, ly, line)

    # Linha de assinatura no rodapé
    sig_y = y + 0.9 * cm
    c.setStrokeColor(HexColor("#111111"))
    c.setLineWidth(0.5)
    c.line(x + 0.6 * cm, sig_y, x + 0.6 * cm + 7 * cm, sig_y)
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(
        x + 0.6 * cm,
        sig_y - 0.35 * cm,
        "Assinatura do manifestante / recebedor",
    )

    # Bordas externas (sutil)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.3)
    c.rect(x, y, width, height)


def gerar_comprovante_protocolo(
    *,
    numero_processo: str,
    manifestante: str,
    especie: str | None,
    assunto: str,
    unidade: str,
    data_recepcao: datetime | None,
    observacao: str | None = None,
    operador_nome: str | None = None,
    nup: str | None = None,
) -> bytes:
    """Comprovante 2 vias na mesma folha A4 — corte tracejado entre elas."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    margin = 1.5 * cm
    via_w = page_w - 2 * margin
    via_h = (page_h - 3 * margin) / 2  # 2 vias + 1 margem entre

    # Via DE CIMA — manifestante
    top_y = page_h - margin - via_h
    _draw_via(
        c,
        x=margin,
        y=top_y,
        width=via_w,
        height=via_h,
        via_label="VIA DO MANIFESTANTE",
        numero_processo=numero_processo,
        manifestante=manifestante,
        especie=especie,
        assunto=assunto,
        unidade=unidade,
        data_recepcao=data_recepcao,
        observacao=observacao,
        operador_nome=operador_nome,
        nup=nup,
    )

    # Linha tracejada de corte
    cut_y = top_y - margin / 2
    c.setStrokeColor(GRAY)
    c.setLineWidth(0.4)
    c.setDash(3, 3)
    c.line(margin, cut_y, page_w - margin, cut_y)
    c.setDash()  # restaura
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(page_w / 2, cut_y - 0.25 * cm, "✂ corte aqui")

    # Via DE BAIXO — unidade (arquivo)
    bottom_y = margin
    _draw_via(
        c,
        x=margin,
        y=bottom_y,
        width=via_w,
        height=via_h,
        via_label="VIA DA UNIDADE (ARQUIVO)",
        numero_processo=numero_processo,
        manifestante=manifestante,
        especie=especie,
        assunto=assunto,
        unidade=unidade,
        data_recepcao=data_recepcao,
        observacao=observacao,
        operador_nome=operador_nome,
        nup=nup,
    )

    c.showPage()
    c.save()
    return buf.getvalue()
