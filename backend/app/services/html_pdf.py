"""Conversão HTML → PDF via WeasyPrint (para finalização de minutas).

O editor rico (TipTap) produz um subconjunto simples de HTML (p, h2, h3, strong,
em, s, ul/ol/li, blockquote, a, img, table). Envolvemos esse HTML num shell de
impressão com CSS institucional e geramos um PDF padrão — compatível com o
carimbo (pypdf) e com o hash SHA-256 da assinatura v2 (que opera sobre os bytes
do arquivo).

Segurança: o `url_fetcher` é DESABILITADO (nenhum recurso remoto é carregado —
sem `@import url(...)`, sem `<img>` apontando pra fora), evitando SSRF/vazamento
a partir de conteúdo autorado. A ÚNICA exceção é a imagem do próprio editor
(`/api/v2/editor-imagens/{arquivo}`, sempre local ao tenant): `_inline_imagens`
lê o arquivo do disco e embute como `data:` URI ANTES de chamar o WeasyPrint —
nenhum fetch de rede acontece, a proteção contra SSRF continua de pé.
"""
from __future__ import annotations

import base64
import html as _html
import re

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
hr {{ border: none; border-top: 1px solid #ccc; margin: 12px 0; }}
img {{ max-width: 100%; }}
table {{ width: 100%; border-collapse: collapse; margin: 0 0 10px; }}
th, td {{ border: 1px solid #ccc; padding: 4px 8px; text-align: left; }}
th {{ background: #f2f2f2; }}
"""

# Casa com a URL que `api.editorImagens.upload` devolve (routers/minutas.py::imagens_router).
_IMG_SRC_RE = re.compile(
    r'src="[^"]*/api/v2/editor-imagens/([a-f0-9]{32}\.(png|jpe?g|gif|webp))"'
)
_MIME_POR_EXT = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg", "gif": "gif", "webp": "webp"}


def _inline_imagens(corpo_html: str, tenant_slug: str) -> str:
    """Troca `<img src="/api/v2/editor-imagens/...">` por `data:` URI.

    Lê o arquivo direto do disco do tenant — sem fetch de rede, então não
    reabre a porta SSRF que `_raise_no_remote` fecha. Imagem que não existir
    mais no disco vira `src` inalterado; sem `base_url`, o WeasyPrint não
    consegue resolver esse caminho relativo pra fetch nenhum (nem local nem
    remoto) — só loga erro e omite a imagem do PDF (confirmado empiricamente:
    não propaga exceção). Degradação silenciosa, mas sem SSRF.
    """
    from ..config import tenant_editor_imagens_dir

    def _sub(m: re.Match[str]) -> str:
        filename, ext = m.group(1), m.group(2)
        path = tenant_editor_imagens_dir(tenant_slug) / filename
        if not path.is_file():
            return m.group(0)
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        mime = _MIME_POR_EXT[ext.lower()]
        return f'src="data:image/{mime};base64,{data}"'

    return _IMG_SRC_RE.sub(_sub, corpo_html)


def _raise_no_remote(url: str, *args, **kwargs):
    """`url_fetcher` do WeasyPrint: bloqueia QUALQUER busca de rede.

    `data:` é a única exceção — não é rede, é o próprio HTML carregando um
    valor que já está embutido nele. Sem esse desvio, o WeasyPrint passa até
    `data:` URIs por aqui (foi assim que a imagem inlined por `_inline_imagens`
    apareceu como "Failed to load image" nos logs, bloqueada por engano).
    """
    if url.startswith("data:"):
        from weasyprint import default_url_fetcher

        return default_url_fetcher(url, *args, **kwargs)
    raise ValueError(f"Recurso remoto bloqueado na geração do PDF: {url}")


def html_to_pdf_bytes(
    corpo_html: str, *, titulo: str | None = None, tenant_slug: str | None = None
) -> bytes:
    """Renderiza o HTML da minuta como PDF (bytes). `titulo` vira o cabeçalho.

    `tenant_slug` habilita `_inline_imagens` — omitido pelos chamadores que
    nunca produzem `<img>` (ex.: ordem de pagamento), sem mudança de
    comportamento pra eles.
    """
    # Import tardio: WeasyPrint puxa libs nativas (pango/cairo) — só carrega quando usado.
    from weasyprint import HTML

    if tenant_slug:
        corpo_html = _inline_imagens(corpo_html, tenant_slug)

    cabecalho = (
        f'<h1 class="doc-titulo">{_html.escape(titulo)}</h1>' if titulo else ""
    )
    documento = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_CSS}</style></head><body>{cabecalho}{corpo_html}</body></html>"
    )
    return HTML(string=documento, url_fetcher=_raise_no_remote).write_pdf()
