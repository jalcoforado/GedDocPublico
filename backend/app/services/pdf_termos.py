"""Termos formais P6 — apensamento, desapensamento, desentranhamento.

Padrão visual: tipografia de documento administrativo brasileiro.
- Cabeçalho em barra escura com símbolo institucional + título
- Corpo em parágrafo formal com dados sublinhados (data, identificador, motivo)
- Linha de assinatura tracejada (formato cartorial)
- Rodapé com serial number do termo (data + tipo + processo) pra rastreabilidade

Nenhuma decoração desnecessária — esses documentos sobrevivem 30+ anos no
arquivo, então prevalência é legibilidade e severidade institucional.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Literal

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

# Paleta: preto austero + cinza pra labels + accent muito sóbrio
INK = HexColor("#0a0a0a")
INK_SOFT = HexColor("#3a3a3a")
GRAY = HexColor("#6b7280")
LINE = HexColor("#1a1a1a")
ACCENT = HexColor("#1e3a5f")  # mesmo brand do resto do sistema

TipoTermo = Literal["APENSAMENTO", "DESAPENSAMENTO", "DESENTRANHAMENTO"]


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%d/%m/%Y às %H:%M")


def _header(c: canvas.Canvas, *, titulo: str, subtitulo: str, page_w: float, page_h: float) -> None:
    """Cabeçalho em barra com título do termo."""
    band_h = 2.5 * cm
    c.setFillColor(INK)
    c.rect(0, page_h - band_h, page_w, band_h, fill=1, stroke=0)
    # Faixa de accent fina logo abaixo
    c.setFillColor(ACCENT)
    c.rect(0, page_h - band_h - 0.12 * cm, page_w, 0.12 * cm, fill=1, stroke=0)

    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, page_h - 1.5 * cm, titulo)
    c.setFont("Helvetica", 9)
    c.drawString(2 * cm, page_h - 2.05 * cm, subtitulo)

    # Aprimora discreto à direita
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Oblique", 8)
    c.drawRightString(page_w - 2 * cm, page_h - 1.5 * cm, "APRIMORA · PROTOCOLO")
    c.setFillColor(HexColor("#cbd5e1"))
    c.drawRightString(
        page_w - 2 * cm,
        page_h - 2.05 * cm,
        datetime.now().strftime("Emitido em %d/%m/%Y às %H:%M"),
    )


def _serial(tipo: TipoTermo, processo_id: int) -> str:
    """Serial number do termo — não é unique no banco, é só identificador visível."""
    return f"{tipo[:3]}-{processo_id:06d}-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def _campo_label(c: canvas.Canvas, x: float, y: float, label: str) -> None:
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7.5)
    c.drawString(x, y, label.upper())


def _campo_valor(
    c: canvas.Canvas, x: float, y: float, valor: str, width: float, *, size: int = 11
) -> None:
    c.setFillColor(INK)
    c.setFont("Helvetica", size)
    # Trunca elegantemente se passar do width
    text = valor or "—"
    while text and c.stringWidth(text, "Helvetica", size) > width:
        text = text[:-1] + "…" if not text.endswith("…") else text[:-2] + "…"
    c.drawString(x, y, text)


def _paragrafo(
    c: canvas.Canvas,
    x: float,
    y: float,
    texto: str,
    *,
    largura: float,
    fonte: str = "Helvetica",
    tam: int = 10.5,
    leading: float = 0.55 * cm,
) -> float:
    """Quebra texto em linhas e desenha — retorna y final."""
    c.setFillColor(INK_SOFT)
    c.setFont(fonte, tam)
    palavras = texto.split()
    linha = ""
    cy = y
    for w in palavras:
        teste = (linha + " " + w).strip()
        if c.stringWidth(teste, fonte, tam) > largura:
            c.drawString(x, cy, linha)
            cy -= leading
            linha = w
        else:
            linha = teste
    if linha:
        c.drawString(x, cy, linha)
        cy -= leading
    return cy


def _linha_assinatura(c: canvas.Canvas, x: float, y: float, w: float, label: str) -> None:
    """Linha tracejada cartorial + rótulo abaixo."""
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.setDash(2, 2)
    c.line(x, y, x + w, y)
    c.setDash()
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7.5)
    c.drawString(x, y - 0.35 * cm, label.upper())


def _rodape(c: canvas.Canvas, page_w: float, serial: str) -> None:
    c.setFillColor(GRAY)
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawCentredString(
        page_w / 2,
        1.2 * cm,
        "Termo gerado eletronicamente pelo sistema Aprimora · "
        "Documento de valor probatório nos termos da Lei 11.419/2006.",
    )
    c.setFont("Helvetica", 7)
    c.drawCentredString(page_w / 2, 0.75 * cm, f"Serial: {serial}")


# ============================================================================
#  APENSAMENTO
# ============================================================================

def gerar_termo_apensamento(
    *,
    numero_processo_apensado: str,
    numero_processo_principal: str,
    nup_apensado: str | None,
    nup_principal: str | None,
    manifestante_apensado: str | None,
    manifestante_principal: str | None,
    motivo: str,
    data_apensamento: datetime,
    operador_nome: str | None,
    processo_id: int,
) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    margin = 2 * cm

    serial = _serial("APENSAMENTO", processo_id)
    _header(
        c,
        titulo="TERMO DE APENSAMENTO DE PROCESSO",
        subtitulo="Anexação formal de processo administrativo",
        page_w=page_w,
        page_h=page_h,
    )

    y = page_h - 4 * cm

    # Dados das partes — pareados visualmente lado a lado
    col_w = (page_w - 2 * margin - 0.8 * cm) / 2

    _campo_label(c, margin, y, "Processo apensado (filho)")
    _campo_valor(
        c,
        margin,
        y - 0.45 * cm,
        nup_apensado or numero_processo_apensado,
        col_w,
        size=12,
    )
    if nup_apensado:
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 8)
        c.drawString(margin, y - 0.95 * cm, f"Legado: {numero_processo_apensado}")
    c.setFillColor(INK_SOFT)
    c.setFont("Helvetica", 9.5)
    c.drawString(margin, y - 1.5 * cm, manifestante_apensado or "—")

    _campo_label(c, margin + col_w + 0.8 * cm, y, "Processo principal (pai)")
    _campo_valor(
        c,
        margin + col_w + 0.8 * cm,
        y - 0.45 * cm,
        nup_principal or numero_processo_principal,
        col_w,
        size=12,
    )
    if nup_principal:
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 8)
        c.drawString(
            margin + col_w + 0.8 * cm,
            y - 0.95 * cm,
            f"Legado: {numero_processo_principal}",
        )
    c.setFillColor(INK_SOFT)
    c.setFont("Helvetica", 9.5)
    c.drawString(margin + col_w + 0.8 * cm, y - 1.5 * cm, manifestante_principal or "—")

    y -= 3 * cm

    # Linha horizontal separadora
    c.setStrokeColor(LINE)
    c.setLineWidth(0.4)
    c.line(margin, y, page_w - margin, y)
    y -= 0.8 * cm

    # Corpo do termo
    texto = (
        f"Em {data_apensamento.strftime('%d de %B de %Y às %H:%M').lower()}, "
        f"procedeu-se à anexação do processo "
        f"{nup_apensado or numero_processo_apensado} ao processo "
        f"{nup_principal or numero_processo_principal}, "
        f"que passa, a partir desta data, a integrá-lo para os efeitos "
        f"da tramitação administrativa."
    )
    y = _paragrafo(c, margin, y, texto, largura=page_w - 2 * margin)

    y -= 0.4 * cm
    _campo_label(c, margin, y, "Motivo do apensamento")
    y -= 0.5 * cm
    y = _paragrafo(c, margin, y, motivo, largura=page_w - 2 * margin, tam=10)

    # Assinatura — bottom, com folga
    sig_y = max(y - 2 * cm, 5 * cm)
    sig_w = 9 * cm
    _linha_assinatura(c, margin, sig_y, sig_w, operador_nome or "Operador responsável")
    if operador_nome:
        c.setFillColor(INK)
        c.setFont("Helvetica", 10)
        c.drawString(margin, sig_y - 1.0 * cm, operador_nome)

    _rodape(c, page_w, serial)
    c.showPage()
    c.save()
    return buf.getvalue()


# ============================================================================
#  DESAPENSAMENTO
# ============================================================================

def gerar_termo_desapensamento(
    *,
    numero_processo_apensado: str,
    numero_processo_principal: str,
    nup_apensado: str | None,
    nup_principal: str | None,
    motivo_apensamento: str,
    motivo_desapensamento: str,
    data_apensamento: datetime,
    data_desapensamento: datetime,
    operador_nome: str | None,
    processo_id: int,
) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    margin = 2 * cm

    serial = _serial("DESAPENSAMENTO", processo_id)
    _header(
        c,
        titulo="TERMO DE DESAPENSAMENTO",
        subtitulo="Desvinculação formal entre processos administrativos",
        page_w=page_w,
        page_h=page_h,
    )

    y = page_h - 4 * cm
    col_w = (page_w - 2 * margin - 0.8 * cm) / 2

    _campo_label(c, margin, y, "Processo desapensado")
    _campo_valor(c, margin, y - 0.45 * cm, nup_apensado or numero_processo_apensado, col_w, size=12)

    _campo_label(c, margin + col_w + 0.8 * cm, y, "Processo principal")
    _campo_valor(
        c,
        margin + col_w + 0.8 * cm,
        y - 0.45 * cm,
        nup_principal or numero_processo_principal,
        col_w,
        size=12,
    )

    y -= 1.6 * cm

    # Linha histórica: quando foi apensado
    _campo_label(c, margin, y, "Apensado em")
    _campo_valor(c, margin, y - 0.4 * cm, _fmt_dt(data_apensamento), col_w, size=10)
    _campo_label(c, margin + col_w + 0.8 * cm, y, "Desapensado em")
    _campo_valor(
        c,
        margin + col_w + 0.8 * cm,
        y - 0.4 * cm,
        _fmt_dt(data_desapensamento),
        col_w,
        size=10,
    )
    y -= 1.4 * cm

    c.setStrokeColor(LINE)
    c.setLineWidth(0.4)
    c.line(margin, y, page_w - margin, y)
    y -= 0.8 * cm

    # Corpo
    texto = (
        f"Pelo presente termo, declara-se desfeito o apensamento do processo "
        f"{nup_apensado or numero_processo_apensado} ao processo "
        f"{nup_principal or numero_processo_principal}. "
        f"Cada processo retoma sua tramitação autônoma a partir desta data."
    )
    y = _paragrafo(c, margin, y, texto, largura=page_w - 2 * margin)

    y -= 0.4 * cm
    _campo_label(c, margin, y, "Motivo original do apensamento")
    y -= 0.5 * cm
    y = _paragrafo(c, margin, y, motivo_apensamento, largura=page_w - 2 * margin, tam=10)

    y -= 0.3 * cm
    _campo_label(c, margin, y, "Motivo do desapensamento")
    y -= 0.5 * cm
    y = _paragrafo(c, margin, y, motivo_desapensamento, largura=page_w - 2 * margin, tam=10)

    sig_y = max(y - 2 * cm, 5 * cm)
    _linha_assinatura(c, margin, sig_y, 9 * cm, operador_nome or "Operador responsável")
    if operador_nome:
        c.setFillColor(INK)
        c.setFont("Helvetica", 10)
        c.drawString(margin, sig_y - 1.0 * cm, operador_nome)

    _rodape(c, page_w, serial)
    c.showPage()
    c.save()
    return buf.getvalue()


# ============================================================================
#  DESENTRANHAMENTO
# ============================================================================

def gerar_termo_desentranhamento(
    *,
    numero_processo: str,
    nup: str | None,
    descricao_anexo: str | None,
    motivo: str,
    autoridade: str,
    data_desentranhamento: datetime,
    operador_nome: str | None,
    processo_id: int,
    anexo_processo_id: int,
) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    margin = 2 * cm

    serial = _serial("DESENTRANHAMENTO", processo_id)
    _header(
        c,
        titulo="TERMO DE DESENTRANHAMENTO",
        subtitulo="Remoção formal de documento de processo administrativo",
        page_w=page_w,
        page_h=page_h,
    )

    y = page_h - 4 * cm
    full_w = page_w - 2 * margin

    _campo_label(c, margin, y, "Processo")
    _campo_valor(c, margin, y - 0.45 * cm, nup or numero_processo, full_w, size=13)
    if nup:
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 8.5)
        c.drawString(margin, y - 0.95 * cm, f"Número legado: {numero_processo}")
    y -= 1.7 * cm

    _campo_label(c, margin, y, "Documento desentranhado")
    _campo_valor(
        c,
        margin,
        y - 0.45 * cm,
        descricao_anexo or f"Anexo #{anexo_processo_id}",
        full_w,
        size=11,
    )
    y -= 1.3 * cm

    col_w = (full_w - 0.8 * cm) / 2
    _campo_label(c, margin, y, "Data do desentranhamento")
    _campo_valor(c, margin, y - 0.4 * cm, _fmt_dt(data_desentranhamento), col_w)
    _campo_label(c, margin + col_w + 0.8 * cm, y, "Autoridade")
    _campo_valor(c, margin + col_w + 0.8 * cm, y - 0.4 * cm, autoridade, col_w, size=10)
    y -= 1.4 * cm

    c.setStrokeColor(LINE)
    c.setLineWidth(0.4)
    c.line(margin, y, page_w - margin, y)
    y -= 0.8 * cm

    texto = (
        f"Pelo presente termo, fica formalizada a retirada do documento "
        f"acima descrito do processo {nup or numero_processo}, "
        f"em {_fmt_dt(data_desentranhamento)}, "
        f"por determinação de {autoridade}."
    )
    y = _paragrafo(c, margin, y, texto, largura=full_w)

    y -= 0.4 * cm
    _campo_label(c, margin, y, "Motivo")
    y -= 0.5 * cm
    y = _paragrafo(c, margin, y, motivo, largura=full_w, tam=10)

    y -= 0.4 * cm
    c.setFillColor(GRAY)
    c.setFont("Helvetica-Oblique", 8.5)
    advertencia = (
        "Observação: o documento desentranhado não é destruído. "
        "Permanece arquivado em separado, com referência ao processo de origem, "
        "respeitando o prazo de guarda definido pela Tabela de Temporalidade Documental."
    )
    y = _paragrafo(c, margin, y, advertencia, largura=full_w, fonte="Helvetica-Oblique", tam=8.5)

    sig_y = max(y - 2 * cm, 5 * cm)
    _linha_assinatura(c, margin, sig_y, 9 * cm, operador_nome or "Operador responsável")
    if operador_nome:
        c.setFillColor(INK)
        c.setFont("Helvetica", 10)
        c.drawString(margin, sig_y - 1.0 * cm, operador_nome)

    _rodape(c, page_w, serial)
    c.showPage()
    c.save()
    return buf.getvalue()
