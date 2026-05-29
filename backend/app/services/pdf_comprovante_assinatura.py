"""Comprovante de assinatura eletrônica interna (PR2b).

PDF simples com identificação do processo/anexo, dados do assinante, hash de
integridade e resultado da validação. Deixa explícito que é assinatura
eletrônica interna com evidências — NÃO é assinatura qualificada ICP-Brasil.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from ..schemas.assinatura import EvidenciasOut, ValidacaoOut, ValidacaoPublicaOut

APRIMORA = HexColor("#1e3a5f")
GRAY = HexColor("#6b7280")
GREEN = HexColor("#15803d")
RED = HexColor("#b91c1c")
AMBER = HexColor("#b45309")


def _fmt_dt(s) -> str:
    if not s:
        return "—"
    if isinstance(s, str):
        try:
            s = datetime.fromisoformat(s)
        except ValueError:
            return s
    return s.strftime("%d/%m/%Y %H:%M:%S")


def _row(c: canvas.Canvas, x: float, y: float, label: str, value: str) -> None:
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(x, y + 0.40 * cm, label.upper())
    c.setFillColor(HexColor("#111111"))
    c.setFont("Helvetica", 10)
    c.drawString(x, y, value or "—")


def gerar_comprovante_assinatura_pdf(
    evidencias: EvidenciasOut, validacao: ValidacaoOut, *, url_validacao: str | None = None
) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    x = 2 * cm
    y = h - 2.5 * cm

    c.setFillColor(APRIMORA)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, "Comprovante de Assinatura Eletrônica")
    y -= 0.7 * cm
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 9)
    c.drawString(x, y, "Assinatura eletrônica interna com evidências — não é assinatura qualificada ICP-Brasil.")

    y -= 1.1 * cm
    _row(c, x, y, "Processo", evidencias.numero_processo or f"#{evidencias.id_processo}")
    _row(c, x + 9 * cm, y, "Documento (anexo)", evidencias.anexo_descricao or f"#{evidencias.id_anexo}")

    y -= 1.1 * cm
    _row(c, x, y, "Assinante", f"{evidencias.nome_assinante or '—'}")
    _row(c, x + 9 * cm, y, "Data/hora da assinatura", _fmt_dt(evidencias.dt_assinatura))

    y -= 1.1 * cm
    _row(c, x, y, "Status", evidencias.status)
    _row(c, x + 5 * cm, y, "Nível", evidencias.nivel)
    _row(c, x + 9 * cm, y, "Método", evidencias.metodo_autenticacao or "—")
    _row(c, x + 14 * cm, y, "Versão doc.", str(evidencias.documento_versao or "—"))

    y -= 1.1 * cm
    _row(c, x, y, f"Hash ({evidencias.hash_algoritmo or 'sha256'})", evidencias.documento_hash or "—")

    y -= 1.1 * cm
    _row(c, x, y, "IP", evidencias.ip_assinatura or "—")
    _row(c, x + 9 * cm, y, "Referência de auditoria", str(evidencias.id_audit_log or "—"))

    # Resultado da validação
    y -= 1.4 * cm
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(x, y + 0.40 * cm, "RESULTADO DA VALIDAÇÃO")
    if validacao.legado:
        cor, txt = AMBER, "LEGADO — sem hash de integridade"
    elif validacao.integro:
        cor, txt = GREEN, "ÍNTEGRO — confere com o hash assinado"
    else:
        cor, txt = RED, "DIVERGENTE — documento alterado após a assinatura"
    c.setFillColor(cor)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, txt)
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 8)
    c.drawString(x, y - 0.5 * cm, validacao.detalhe)

    # Validação pública (PR2e) — código + QR + URL, quando há código.
    if evidencias.codigo_validacao:
        yv = y - 2.0 * cm
        _row(c, x, yv, "Código de validação pública", evidencias.codigo_validacao)
        if url_validacao:
            _draw_qr(c, url_validacao, x, yv - 4.2 * cm, 3.0 * cm)
            c.setFillColor(GRAY)
            c.setFont("Helvetica", 8)
            c.drawString(x + 3.5 * cm, yv - 1.6 * cm, "Validação pública em:")
            c.setFillColor(APRIMORA)
            c.setFont("Helvetica", 8)
            c.drawString(x + 3.5 * cm, yv - 2.1 * cm, url_validacao)

    # Rodapé
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(x, 1.5 * cm, f"Emitido em {_fmt_dt(datetime.now())} · aprimora")

    c.showPage()
    c.save()
    return buf.getvalue()


def _draw_qr(c: canvas.Canvas, data: str, x: float, y: float, size: float) -> None:
    """Desenha um QR Code (reportlab nativo — sem dependência extra)."""
    widget = qr.QrCodeWidget(data)
    b = widget.getBounds()
    w = b[2] - b[0]
    h = b[3] - b[1]
    d = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
    d.add(widget)
    renderPDF.draw(d, c, x, y)


def gerar_comprovante_publico_pdf(
    resultado: ValidacaoPublicaOut, *, codigo: str, url_validacao: str
) -> bytes:
    """Comprovante PÚBLICO (PR2e) — versão minimizada para validação anônima.

    Diferente do interno: NÃO contém IP, user agent, método de autenticação,
    evidências internas nem referência de auditoria. Só o probatório mínimo +
    código/URL/QR de validação pública.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    x = 2 * cm
    y = h - 2.5 * cm

    c.setFillColor(APRIMORA)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, "Comprovante Público de Assinatura")
    y -= 0.7 * cm
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 9)
    c.drawString(x, y, resultado.aviso or "Assinatura eletrônica interna — não é ICP-Brasil.")

    # Resultado da validação (destaque no topo)
    y -= 1.3 * cm
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(x, y + 0.40 * cm, "RESULTADO DA VALIDAÇÃO")
    if resultado.integro:
        cor, txt = GREEN, "ÍNTEGRO — confere com o hash assinado"
    else:
        cor, txt = RED, "DIVERGENTE — documento alterado após a assinatura"
    c.setFillColor(cor)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, txt)

    y -= 1.4 * cm
    _row(c, x, y, "Assinante", resultado.signatario or "—")
    _row(c, x + 9 * cm, y, "Data/hora da assinatura", _fmt_dt(resultado.assinado_em))

    y -= 1.1 * cm
    _row(c, x, y, "Processo", resultado.processo_numero or "—")
    _row(c, x + 9 * cm, y, "Versão doc.", str(resultado.versao_documento or "—"))

    y -= 1.1 * cm
    _row(c, x, y, f"Hash ({resultado.algoritmo or 'sha256'})", resultado.hash or "—")

    y -= 1.1 * cm
    _row(c, x, y, "Código de validação", codigo)

    # QR + URL pública
    _draw_qr(c, url_validacao, x, y - 4.2 * cm, 3.5 * cm)
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 8)
    c.drawString(x + 4 * cm, y - 1.6 * cm, "Valide a autenticidade em:")
    c.setFillColor(APRIMORA)
    c.setFont("Helvetica", 8)
    c.drawString(x + 4 * cm, y - 2.1 * cm, url_validacao)

    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(x, 1.5 * cm, f"Emitido em {_fmt_dt(datetime.now())} · aprimora")

    c.showPage()
    c.save()
    return buf.getvalue()
