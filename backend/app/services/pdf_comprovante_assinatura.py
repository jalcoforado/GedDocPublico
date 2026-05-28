"""Comprovante de assinatura eletrônica interna (PR2b).

PDF simples com identificação do processo/anexo, dados do assinante, hash de
integridade e resultado da validação. Deixa explícito que é assinatura
eletrônica interna com evidências — NÃO é assinatura qualificada ICP-Brasil.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from ..schemas.assinatura import EvidenciasOut, ValidacaoOut

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
    evidencias: EvidenciasOut, validacao: ValidacaoOut
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

    # Rodapé
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(x, 1.5 * cm, f"Emitido em {_fmt_dt(datetime.now())} · aprimora")

    c.showPage()
    c.save()
    return buf.getvalue()
