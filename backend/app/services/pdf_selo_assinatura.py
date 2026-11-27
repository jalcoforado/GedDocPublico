"""Selo da assinatura com senha, desenhado no ponto da página que o signatário
escolheu (SI-68).

Segue o modelo de `pdf_carimbo.py` (overlay reportlab + merge pypdf) e roda
DEPOIS dele: carimbo primeiro, selos por cima (decisão de 24/11). O arquivo
original nunca é tocado — o `documento_hash` da assinatura é o SHA-256 dele, e
o `/validar` recalcula sobre ele. O selo existe só no PDF servido.

## Coordenadas

A tela guarda a posição como o usuário vê a página no pdf.js: canto superior
esquerdo do quadrado, em fração (0–1) da página já girada pelo `/Rotate`, com
origem no canto superior esquerdo. Aqui:

1. desenha-se o selo numa página de overlay do tamanho VISTO (largura e altura
   trocadas em 90°/270°), em pontos, com a origem do reportlab (inferior
   esquerda);
2. o overlay é aplicado com a transformação que leva o espaço visto ao espaço
   do usuário do PDF, considerando a rotação e a origem da caixa (que nem sempre
   é 0,0).

A caixa usada é a `CropBox` — é ela que o pdf.js mostra (`page.view`). Sem
CropBox, o pypdf devolve a MediaBox.

O tamanho do selo é fixo em pontos e é o MESMO que a tela usa para desenhar o
quadrado (`frontend/lib/selo-assinatura.ts`); `test_si68_selo_assinatura.py`
reprova se os dois divergirem.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import validacao_publica_url
from ..models import AssinaturaAnexo, Usuario, UsuarioAssinatura

log = logging.getLogger(__name__)

# Tamanho do selo em pontos PDF (1/72"). Espelhado em
# `frontend/lib/selo-assinatura.ts` — mude os dois juntos.
SELO_LARGURA_PT = 200.0
SELO_ALTURA_PT = 62.0

_APRIMORA = HexColor("#1e3a5f")
_CINZA = HexColor("#4b5563")
_TEXTO = HexColor("#111111")
_PADDING = 6.0
_QR = SELO_ALTURA_PT - 2 * _PADDING


class SeloError(Exception):
    pass


@dataclass(frozen=True)
class SeloAssinatura:
    """O que vai desenhado num selo. `x`/`y` em fração da página vista."""

    pagina: int
    x: float
    y: float
    nome: str
    cargo: str | None
    dt_assinatura: datetime | None
    codigo_validacao: str | None
    url_validacao: str | None


def contar_paginas_pdf(pdf_bytes: bytes) -> int:
    try:
        return len(PdfReader(BytesIO(pdf_bytes)).pages)
    except Exception as e:  # noqa: BLE001 — PDF corrompido
        raise SeloError(f"Falha ao ler PDF: {type(e).__name__}") from e


def _caixa_vista(page) -> tuple[float, float, float, float, int]:
    """(llx, lly, largura, altura, rotação) da caixa que o leitor mostra."""
    box = page.cropbox
    llx, lly = float(box.left), float(box.bottom)
    w, h = float(box.width), float(box.height)
    rot = int(page.rotation or 0) % 360
    if rot not in (0, 90, 180, 270):
        rot = 0
    return llx, lly, w, h, rot


def _tamanho_visto(w: float, h: float, rot: int) -> tuple[float, float]:
    return (h, w) if rot in (90, 270) else (w, h)


def transformacao_vista_para_pdf(
    llx: float, lly: float, w: float, h: float, rot: int
) -> tuple[float, float, float, float, float, float]:
    """Matriz (a, b, c, d, e, f) que leva um ponto (u, v) do espaço VISTO
    (origem inferior esquerda da página já girada) ao espaço do usuário do PDF:
    x = a·u + c·v + e, y = b·u + d·v + f. `/Rotate` gira no sentido horário."""
    if rot == 90:
        return (0.0, 1.0, -1.0, 0.0, llx + w, lly)
    if rot == 180:
        return (-1.0, 0.0, 0.0, -1.0, llx + w, lly + h)
    if rot == 270:
        return (0.0, -1.0, 1.0, 0.0, llx, lly + h)
    return (1.0, 0.0, 0.0, 1.0, llx, lly)


def canto_do_selo_em_pontos(
    selo_x: float, selo_y: float, largura_vista: float, altura_vista: float
) -> tuple[float, float]:
    """Canto INFERIOR esquerdo do selo no espaço visto (origem inferior
    esquerda), mantendo o quadrado inteiro dentro da página."""
    esq = min(max(selo_x * largura_vista, 0.0), max(largura_vista - SELO_LARGURA_PT, 0.0))
    topo = min(max(selo_y * altura_vista, 0.0), max(altura_vista - SELO_ALTURA_PT, 0.0))
    return esq, altura_vista - topo - SELO_ALTURA_PT


def _cabe(texto: str, fonte: str, tamanho: float, largura: float) -> str:
    if stringWidth(texto, fonte, tamanho) <= largura:
        return texto
    while texto and stringWidth(texto + "…", fonte, tamanho) > largura:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def _desenhar_selo(c: canvas.Canvas, x0: float, y0: float, selo: SeloAssinatura) -> None:
    c.saveState()
    c.setFillColor(HexColor("#ffffff"))
    c.setFillAlpha(0.94)
    c.setStrokeColor(_APRIMORA)
    c.setLineWidth(0.8)
    c.roundRect(x0, y0, SELO_LARGURA_PT, SELO_ALTURA_PT, 3, fill=1, stroke=1)
    c.setFillAlpha(1)

    texto_x = x0 + _PADDING
    if selo.url_validacao:
        widget = qr.QrCodeWidget(selo.url_validacao)
        bx1, by1, bx2, by2 = widget.getBounds()
        d = Drawing(_QR, _QR, transform=[_QR / (bx2 - bx1), 0, 0, _QR / (by2 - by1), 0, 0])
        d.add(widget)
        renderPDF.draw(d, c, x0 + _PADDING, y0 + _PADDING)
        texto_x += _QR + _PADDING
    largura_texto = x0 + SELO_LARGURA_PT - _PADDING - texto_x

    y = y0 + SELO_ALTURA_PT - _PADDING - 6
    c.setFillColor(_APRIMORA)
    c.setFont("Helvetica-Bold", 5.5)
    c.drawString(texto_x, y, "ASSINADO ELETRONICAMENTE POR")

    y -= 10
    c.setFillColor(_TEXTO)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(texto_x, y, _cabe(selo.nome or "—", "Helvetica-Bold", 8, largura_texto))

    c.setFillColor(_CINZA)
    c.setFont("Helvetica", 6.5)
    if selo.cargo:
        y -= 8.5
        c.drawString(texto_x, y, _cabe(selo.cargo, "Helvetica", 6.5, largura_texto))
    if selo.dt_assinatura:
        y -= 8.5
        c.drawString(
            texto_x,
            y,
            f"em {selo.dt_assinatura.strftime('%d/%m/%Y')} às {selo.dt_assinatura.strftime('%H:%M')}",
        )
    if selo.codigo_validacao:
        y -= 8.5
        c.setFont("Helvetica", 5.5)
        rotulo = "Código de validação: "
        c.drawString(texto_x, y, rotulo)
        c.setFont("Courier", 5.5)
        dx = stringWidth(rotulo, "Helvetica", 5.5)
        c.drawString(
            texto_x + dx,
            y,
            _cabe(selo.codigo_validacao, "Courier", 5.5, largura_texto - dx),
        )
    c.restoreState()


def _overlay(largura: float, altura: float, selos: Iterable[SeloAssinatura]) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(largura, altura))
    for selo in selos:
        x0, y0 = canto_do_selo_em_pontos(selo.x, selo.y, largura, altura)
        _desenhar_selo(c, x0, y0, selo)
    c.showPage()
    c.save()
    return buf.getvalue()


def aplicar_selos_pdf_bytes(pdf_bytes: bytes, selos: list[SeloAssinatura]) -> bytes:
    """Desenha os selos nas páginas indicadas. Mesmo número de páginas do
    original — o selo nunca vira página a mais."""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception as e:  # noqa: BLE001
        raise SeloError(f"Falha ao ler PDF: {type(e).__name__}") from e

    por_pagina: dict[int, list[SeloAssinatura]] = {}
    for s in selos:
        por_pagina.setdefault(s.pagina, []).append(s)

    writer = PdfWriter()
    for idx, page in enumerate(reader.pages, start=1):
        do_selo = por_pagina.get(idx)
        if do_selo:
            llx, lly, w, h, rot = _caixa_vista(page)
            vw, vh = _tamanho_visto(w, h, rot)
            overlay = PdfReader(BytesIO(_overlay(vw, vh, do_selo))).pages[0]
            try:
                page.merge_transformed_page(
                    overlay, Transformation(transformacao_vista_para_pdf(llx, lly, w, h, rot))
                )
            except Exception:  # noqa: BLE001
                # Content stream incomum: entrega a página sem o selo em vez
                # de derrubar o documento inteiro, como o carimbo faz.
                log.warning("selo não aplicado na página %s", idx, exc_info=True)
        writer.add_page(page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()


async def selos_dos_anexos(
    db: AsyncSession,
    anexo_ids: Iterable[int],
    *,
    tenant_id: int,
    tenant_slug: str,
) -> dict[int, list[SeloAssinatura]]:
    """Selos das assinaturas EFETIVADAS e posicionadas de cada anexo, na ordem
    em que foram assinadas. Não autoriza: quem chama já passou pelo sigilo."""
    ids = sorted(set(anexo_ids))
    if not ids:
        return {}
    rows = (
        await db.execute(
            select(AssinaturaAnexo, Usuario.nome, Usuario.cargo)
            .join(
                UsuarioAssinatura,
                UsuarioAssinatura.id == AssinaturaAnexo.id_usuario_assinatura,
            )
            .join(Usuario, Usuario.id == UsuarioAssinatura.id_assinante)
            .where(
                AssinaturaAnexo.tenant_id == tenant_id,
                AssinaturaAnexo.id_anexo.in_(ids),
                AssinaturaAnexo.excluido.is_(False),
                AssinaturaAnexo.status == "assinada",
                AssinaturaAnexo.selo_pagina.is_not(None),
                UsuarioAssinatura.tenant_id == tenant_id,
                Usuario.tenant_id == tenant_id,
            )
            .order_by(AssinaturaAnexo.dt_assinatura, AssinaturaAnexo.id)
        )
    ).all()
    out: dict[int, list[SeloAssinatura]] = {}
    for aa, nome, cargo in rows:
        out.setdefault(aa.id_anexo, []).append(
            SeloAssinatura(
                pagina=aa.selo_pagina,
                x=aa.selo_x,
                y=aa.selo_y,
                nome=nome,
                cargo=cargo,
                dt_assinatura=aa.dt_assinatura,
                codigo_validacao=aa.codigo_validacao,
                url_validacao=(
                    validacao_publica_url(tenant_slug, aa.codigo_validacao)
                    if aa.codigo_validacao
                    else None
                ),
            )
        )
    return out
