"""Comprovantes de envio e recebimento de encaminhamentos.

Espelha `Imprimir::comprovanteEncaminhamento` e `comprovanteRecebimento` do PHP.
Mesmo layout para os dois — muda só o título e o conjunto de dados destacado.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Literal

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from ..schemas.processo import EncaminhamentoOut, ProcessoDetail

APRIMORA = HexColor("#1e3a5f")
GRAY = HexColor("#6b7280")

Tipo = Literal["envio", "recebimento"]


def _label_value(c: canvas.Canvas, x: float, y: float, label: str, value: str, w: float):
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(x, y + 0.42 * cm, label.upper())
    c.setFillColor(HexColor("#111111"))
    c.setFont("Helvetica", 11)
    text = value or "—"
    if c.stringWidth(text, "Helvetica", 11) > w:
        while text and c.stringWidth(text + "…", "Helvetica", 11) > w:
            text = text[:-1]
        text += "…"
    c.drawString(x, y, text)


def _fmt_dt(s) -> str:
    if not s:
        return "—"
    if isinstance(s, str):
        try:
            s = datetime.fromisoformat(s)
        except ValueError:
            return s
    return s.strftime("%d/%m/%Y %H:%M")


def _fmt_d(s) -> str:
    if not s:
        return "—"
    if isinstance(s, str):
        s_only = s[:10]
        try:
            from datetime import date as _d
            return _d.fromisoformat(s_only).strftime("%d/%m/%Y")
        except ValueError:
            return s_only
    return s.strftime("%d/%m/%Y")


def gerar_comprovante_pdf(
    processo: ProcessoDetail,
    encaminhamento: EncaminhamentoOut,
    *,
    tipo: Tipo,
    operador_nome: str | None = None,
) -> bytes:
    """`operador_nome` = nome do usuário que emitiu o comprovante (não persistido)."""
    titulo = "COMPROVANTE DE RECEBIMENTO" if tipo == "recebimento" else "COMPROVANTE DE ENCAMINHAMENTO"

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 2 * cm

    # Header
    c.setFillColor(APRIMORA)
    c.rect(0, height - 3.2 * cm, width, 3.2 * cm, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, height - 1.8 * cm, titulo)
    c.setFont("Helvetica", 9)
    c.drawString(margin, height - 2.4 * cm, f"Processo {processo.numero_processo}")
    c.drawRightString(width - margin, height - 1.8 * cm, datetime.now().strftime("Emitido em %d/%m/%Y %H:%M"))

    # Bloco do processo
    y = height - 5 * cm
    col_w = (width - 2 * margin - 0.5 * cm) / 2
    _label_value(c, margin, y, "Manifestante", processo.manifestante or "—", col_w)
    _label_value(c, margin + col_w + 0.5 * cm, y, "Assunto", processo.assunto or "—", col_w)
    y -= 1.3 * cm
    _label_value(c, margin, y, "Aberto em", _fmt_dt(processo.data_hora_abertura), col_w)
    _label_value(c, margin + col_w + 0.5 * cm, y, "Local atual", processo.local_atual or "—", col_w)
    y -= 1.5 * cm

    # Linha divisória
    c.setStrokeColor(GRAY)
    c.setLineWidth(0.4)
    c.line(margin, y, width - margin, y)
    y -= 0.7 * cm

    # Subtítulo da seção do encaminhamento
    c.setFillColor(APRIMORA)
    c.setFont("Helvetica-Bold", 12)
    sub = "DADOS DO RECEBIMENTO" if tipo == "recebimento" else "DADOS DO ENCAMINHAMENTO"
    c.drawString(margin, y, sub)
    y -= 0.9 * cm

    # Grid 2 colunas
    _label_value(c, margin, y, "Unidade de origem", encaminhamento.unidade_origem or "—", col_w)
    _label_value(c, margin + col_w + 0.5 * cm, y, "Unidade de destino", encaminhamento.unidade_destino, col_w)
    y -= 1.3 * cm
    _label_value(c, margin, y, "Prioridade", encaminhamento.prioridade or "—", col_w)
    _label_value(c, margin + col_w + 0.5 * cm, y, "Quantidade de folhas", str(encaminhamento.quantidade_folhas), col_w)
    y -= 1.3 * cm
    _label_value(c, margin, y, "Data prazo", _fmt_d(encaminhamento.data_prazo), col_w)
    if tipo == "recebimento":
        _label_value(
            c, margin + col_w + 0.5 * cm, y, "Recebido em",
            _fmt_dt(encaminhamento.data_hora_recebimento), col_w,
        )
    else:
        _label_value(
            c, margin + col_w + 0.5 * cm, y, "Status",
            "Cancelado" if encaminhamento.cancelado
            else "Recebido" if encaminhamento.recebido else "Pendente de recebimento",
            col_w,
        )
    y -= 1.8 * cm

    # Assinatura
    c.setStrokeColor(HexColor("#111111"))
    c.setLineWidth(0.7)
    sig_y = max(y, 4 * cm)
    c.line(margin, sig_y, margin + 8 * cm, sig_y)
    c.setFillColor(HexColor("#111111"))
    c.setFont("Helvetica", 9)
    c.drawString(margin, sig_y - 0.5 * cm, operador_nome or "Responsável pela operação")
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7.5)
    label_assin = "Recebedor" if tipo == "recebimento" else "Operador remetente"
    c.drawString(margin, sig_y - 0.9 * cm, label_assin)

    # Rodapé
    c.setFillColor(GRAY)
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(width / 2, 1.2 * cm, "Documento gerado eletronicamente pelo sistema Aprimora")
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 0.7 * cm, f"Encaminhamento #{encaminhamento.id} · Processo {processo.numero_processo}")

    c.showPage()
    c.save()
    return buf.getvalue()
