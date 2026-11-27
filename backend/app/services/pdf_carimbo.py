"""Carimbamento de PDFs anexados.

Espelha o `PdfToolkit::clone()` do PHP (que usa FPDI), mas faz overlay via
pypdf + reportlab:
  1. Gera um PDF de overlay (mesmo tamanho de cada página) com cabeçalho e rodapé.
  2. Merge das páginas originais com o overlay correspondente.

Cabeçalho: número do processo + e_doc.
Rodapé: página X/Y + data/hora atual.

Cache: o carimbado é gravado em disco e reutilizado em chamadas subsequentes.
Anexo é imutável após upload, então o cache é eterno (até soft-delete).

SI-72 (versões): versão 2+ leva "versão N" no cabeçalho, e a versão
SUBSTITUÍDA leva uma faixa "DOCUMENTO SUBSTITUÍDO PELA VERSÃO N". Ser
substituída é estado que muda depois do upload (chega uma versão nova; ou a
nova é excluída e esta volta a valer), então o estado entra no NOME do cache
(`{id}-subst-v{N}.pdf`): cada estado tem o seu arquivo e nenhum caminho
precisa lembrar de invalidar nada.
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
SUBSTITUIDO = HexColor("#b45309")


def texto_substituido(versao_substituta: int) -> str:
    return (
        f"DOCUMENTO SUBSTITUÍDO PELA VERSÃO {versao_substituta}"
        " · mantido no processo como histórico"
    )


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
    versao: int = 1,
    substituido_pela_versao: int | None = None,
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
    direita = f"e-doc: {e_doc}" if e_doc else ""
    if versao > 1:
        direita = f"{direita} · versão {versao}" if direita else f"versão {versao}"
    if direita:
        c.setFont("Helvetica", 7.5)
        c.drawRightString(width - 8, height - header_h + 4, direita)

    # SI-72 — faixa da versão substituída, logo abaixo do cabeçalho.
    if substituido_pela_versao is not None:
        faixa_h = 13
        c.setFillColor(SUBSTITUIDO)
        c.rect(0, height - header_h - faixa_h, width, faixa_h, fill=1, stroke=0)
        c.setFillColor(HexColor("#ffffff"))
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString(
            width / 2, height - header_h - faixa_h + 4,
            texto_substituido(substituido_pela_versao),
        )

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
    versao: int = 1,
    substituido_pela_versao: int | None = None,
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
            versao=versao,
            substituido_pela_versao=substituido_pela_versao,
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


def nome_cache(anexo_id: int, substituido_pela_versao: int | None = None) -> str:
    """Nome do arquivo carimbado. O estado "substituído" entra no nome (SI-72):
    cada estado tem o seu cache, e voltar a ser vigente reaproveita o antigo."""
    if substituido_pela_versao is None:
        return f"{anexo_id}.pdf"
    return f"{anexo_id}-subst-v{substituido_pela_versao}.pdf"


def _cache_path(
    anexo_id: int,
    tenant_slug: str | None = None,
    substituido_pela_versao: int | None = None,
) -> Path:
    """Path do cache carimbado. Se tenant_slug, usa storage por tenant;
    senão fallback ao path legacy global."""
    nome = nome_cache(anexo_id, substituido_pela_versao)
    if tenant_slug:
        return tenant_carimbados_dir(tenant_slug) / nome
    settings = get_settings()
    legacy = Path(settings.uploads_dir) / "carimbados"
    legacy.mkdir(parents=True, exist_ok=True)
    return legacy / nome


async def carimbar_anexo_com_cache(
    *,
    anexo_id: int,
    numero_processo: str,
    e_doc: str,
    tenant_slug: str,
    versao: int = 1,
    substituido_pela_versao: int | None = None,
) -> Path:
    """Retorna o path do PDF carimbado, gerando e cacheando se necessário.

    O original é lido pela abstração de storage (`services/storage.py`), não
    por caminho local. Levanta `FileNotFoundError` se o original não existir.
    **Não autoriza**: quem chama já tem de ter passado pelo guard de sigilo.
    O cache de carimbados continua no disco local."""
    cache = _cache_path(anexo_id, tenant_slug, substituido_pela_versao)
    if cache.exists():
        return cache

    from .storage import obter_storage

    original_bytes = await obter_storage().get_bytes(tenant_slug, e_doc)
    stamped = carimbar_pdf_bytes(
        original_bytes,
        numero_processo=numero_processo,
        e_doc=e_doc,
        versao=versao,
        substituido_pela_versao=substituido_pela_versao,
    )
    cache.write_bytes(stamped)
    return cache


def invalidate_cache(anexo_id: int, tenant_slug: str | None = None) -> None:
    """Remove cache se existir (chamar no delete do anexo), inclusive os
    carimbos de "substituído" (SI-72)."""
    dirs = []
    if tenant_slug:
        dirs.append(_cache_path(anexo_id, tenant_slug).parent)
    # Também tenta o legacy global
    dirs.append(_cache_path(anexo_id, None).parent)
    for d in dirs:
        for f in (d / f"{anexo_id}.pdf", *d.glob(f"{anexo_id}-subst-v*.pdf")):
            if f.exists():
                f.unlink(missing_ok=True)
