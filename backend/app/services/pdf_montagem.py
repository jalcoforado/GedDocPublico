"""Monta um PDF completo do processo: capa + anexos PDF carimbados.

Espelha `Imprimir::montarProcesso()` do PHP. Versão atual:
- Inclui capa (sempre).
- Inclui todos os anexos PDF ativos do processo, na ordem de `anexo_processo.ordem`.
- Anexos não-PDF são pulados (silenciosamente). Conversão de imagem→PDF
  fica para iteração futura.
- Anexos com PDF corrompido são pulados (carimbo falha, log no stdout).

Reusa o cache de carimbado: se o anexo já foi carimbado antes, leitura instantânea.
"""
from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader, PdfWriter

from ..config import resolve_anexo_path
from ..schemas.processo import ProcessoDetail
from .pdf_capa import gerar_capa_pdf
from .pdf_carimbo import CarimboError, carimbar_anexo_com_cache


def gerar_processo_completo_pdf(detail: ProcessoDetail, *, tenant_slug: str) -> bytes:
    writer = PdfWriter()

    # 1. Capa
    capa_bytes = gerar_capa_pdf(detail)
    for p in PdfReader(BytesIO(capa_bytes)).pages:
        writer.add_page(p)

    # 2. Anexos PDF na ordem definida em anexo_processo.ordem.
    pdf_anexos = [
        a for a in detail.anexos
        if a.e_doc and a.e_doc.lower().endswith(".pdf")
    ]
    pdf_anexos.sort(key=lambda a: (a.ordem if a.ordem is not None else 9999, a.id))

    for anexo in pdf_anexos:
        # Storage por tenant (Fase 14) primeiro, legacy (Sobral) como fallback —
        # mesma resolução usada pelo download avulso (services/anexos.py).
        source_path = resolve_anexo_path(tenant_slug, anexo.e_doc or "")
        if source_path is None:
            continue
        try:
            carimbado_path = carimbar_anexo_com_cache(
                anexo_id=anexo.id,
                source_pdf_path=source_path,
                numero_processo=detail.numero_processo,
                e_doc=anexo.e_doc or "",
                tenant_slug=tenant_slug,
            )
        except CarimboError:
            # PDF corrompido — pula em vez de quebrar a montagem inteira.
            continue
        try:
            for p in PdfReader(str(carimbado_path)).pages:
                writer.add_page(p)
        except Exception:
            continue

    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()
