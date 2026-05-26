"""Carimbamento de PDFs anexados.

Espelha o `PdfToolkit::clone()` do PHP (que usa FPDI), mas faz overlay via
pypdf + reportlab:
  1. Gera um PDF de overlay (mesmo tamanho de cada página) com cabeçalho e rodapé.
  2. Merge das páginas originais com o overlay correspondente.

Cabeçalho: número do processo + e_doc.
Rodapé: página X/Y + data/hora atual.

Cache: o carimbado é gravado em disco e reutilizado em chamadas subsequentes.
Anexo é imutável após upload, então o cache é eterno (até soft-delete).
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

from ..config import get_settings, tenant_carimbados_dir

APRIMORA = HexColor("#1e3a5f")
GRAY = HexColor("#6b7280")


class CarimboError(Exception):
    pass


def _gerar_overlay_pagina(
    width: float,
    height: float,
    *,
    numero_processo: str,
    e_doc: str,
    pagina_idx: int,
    total_paginas: int,
    emitido_em: str,
) -> bytes:
    """Cria um PDF de uma página única do tamanho dado, contendo só o carimbo."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))

    # Cabeçalho (faixa superior fina)
    header_h = 14
    c.setFillColor(APRIMORA)
    c.rect(0, height - header_h, width, header_h, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(8, height - header_h + 4, f"APRIMORA · Processo {numero_processo}")
    if e_doc:
        c.setFont("Helvetica", 7.5)
        c.drawRightString(width - 8, height - header_h + 4, f"e-doc: {e_doc}")

    # Rodapé (faixa inferior fina)
    footer_h = 12
    c.setFillColor(HexColor("#f3f4f6"))
    c.rect(0, 0, width, footer_h, fill=1, stroke=0)
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(8, 3, f"Página {pagina_idx}/{total_paginas}")
    c.drawRightString(width - 8, 3, f"Carimbado em {emitido_em}")

    c.showPage()
    c.save()
    return buf.getvalue()


def carimbar_pdf_bytes(
    pdf_bytes: bytes,
    *,
    numero_processo: str,
    e_doc: str,
) -> bytes:
    """Recebe bytes do PDF original, devolve bytes do PDF carimbado."""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception as e:  # PDF corrompido
        raise CarimboError(f"Falha ao ler PDF: {type(e).__name__}: {e}")

    total = len(reader.pages)
    if total == 0:
        raise CarimboError("PDF sem páginas")

    writer = PdfWriter()
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    for idx, page in enumerate(reader.pages, start=1):
        # mediabox pode ter coords negativas em alguns PDFs; usamos width/height absolutos
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        overlay_bytes = _gerar_overlay_pagina(
            w,
            h,
            numero_processo=numero_processo,
            e_doc=e_doc,
            pagina_idx=idx,
            total_paginas=total,
            emitido_em=now_str,
        )
        overlay_page = PdfReader(BytesIO(overlay_bytes)).pages[0]
        try:
            page.merge_page(overlay_page)
        except Exception:
            # Algumas páginas podem ter content stream incomum; pula carimbo nesta página
            # em vez de quebrar o PDF inteiro.
            pass
        writer.add_page(page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _cache_path(anexo_id: int, tenant_slug: str | None = None) -> Path:
    """Path do cache carimbado. Se tenant_slug, usa storage por tenant;
    senão fallback ao path legacy global."""
    if tenant_slug:
        return tenant_carimbados_dir(tenant_slug) / f"{anexo_id}.pdf"
    settings = get_settings()
    legacy = Path(settings.uploads_dir) / "carimbados"
    legacy.mkdir(parents=True, exist_ok=True)
    return legacy / f"{anexo_id}.pdf"


def carimbar_anexo_com_cache(
    *,
    anexo_id: int,
    source_pdf_path: Path,
    numero_processo: str,
    e_doc: str,
    tenant_slug: str | None = None,
) -> Path:
    """Retorna o path do PDF carimbado, gerando e cacheando se necessário."""
    cache = _cache_path(anexo_id, tenant_slug)
    if cache.exists():
        return cache

    original_bytes = source_pdf_path.read_bytes()
    stamped = carimbar_pdf_bytes(
        original_bytes,
        numero_processo=numero_processo,
        e_doc=e_doc,
    )
    cache.write_bytes(stamped)
    return cache


def invalidate_cache(anexo_id: int, tenant_slug: str | None = None) -> None:
    """Remove cache se existir (chamar no delete do anexo)."""
    cache = _cache_path(anexo_id, tenant_slug)
    if cache.exists():
        cache.unlink(missing_ok=True)
    # Também tenta o legacy global
    if tenant_slug:
        legacy = _cache_path(anexo_id, None)
        if legacy.exists():
            legacy.unlink(missing_ok=True)
