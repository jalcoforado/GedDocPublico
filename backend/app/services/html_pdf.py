"""Conversão HTML → PDF via WeasyPrint (para finalização de minutas).

O editor rico (TipTap) produz um subconjunto simples de HTML (p, h2, h3, strong,
em, s, ul/ol/li, blockquote, a). Envolvemos esse HTML num shell de impressão com
CSS institucional e geramos um PDF padrão — compatível com o carimbo (pypdf) e com
o hash SHA-256 da assinatura v2 (que opera sobre os bytes do arquivo).

Segurança: o `url_fetcher` é DESABILITADO (nenhum recurso remoto é carregado —
sem `<img src=http…>`, sem `@import url(...)`), evitando SSRF/vazamento a partir de
conteúdo autorado. Apenas layout/tipografia locais.
"""
from __future__ import annotations

import html as _html

# Cor institucional (mesma do carimbo — services/pdf_carimbo.py).
_BRAND = "#1e3a5f"

_CSS = f"""
@page {{
    size: A4;
    margin: 2.5cm 2cm;
}}
body {{
    font-family: "DejaVu Sans", "Liberation Sans", Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #1a1a1a;
}}
h1.doc-titulo {{
    font-size: 15pt;
    color: {_BRAND};
    border-bottom: 2px solid {_BRAND};
    padding-bottom: 6px;
    margin: 0 0 18px 0;
}}
h2 {{ font-size: 13pt; color: {_BRAND}; margin: 16px 0 8px; }}
h3 {{ font-size: 12pt; color: {_BRAND}; margin: 14px 0 6px; }}
p {{ margin: 0 0 10px; text-align: justify; }}
ul, ol {{ margin: 0 0 10px 22px; }}
blockquote {{
    margin: 0 0 10px; padding: 4px 12px;
    border-left: 3px solid {_BRAND}; color: #444;
}}
a {{ color: {_BRAND}; }}
"""


def _raise_no_remote(url: str, *_args, **_kwargs):  # noqa: ANN001, ANN002, ANN003
    raise ValueError(f"Recurso remoto bloqueado na geração do PDF: {url}")


def html_to_pdf_bytes(corpo_html: str, *, titulo: str | None = None) -> bytes:
    """Renderiza o HTML da minuta como PDF (bytes). `titulo` vira o cabeçalho."""
    # Import tardio: WeasyPrint puxa libs nativas (pango/cairo) — só carrega quando usado.
    from weasyprint import HTML

    cabecalho = (
        f'<h1 class="doc-titulo">{_html.escape(titulo)}</h1>' if titulo else ""
    )
    documento = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_CSS}</style></head><body>{cabecalho}{corpo_html}</body></html>"
    )
    return HTML(string=documento, url_fetcher=_raise_no_remote).write_pdf()
