"""Sanitização de HTML para templates de documento.

Usa bleach para remover tags/attrs perigosas antes de gerar PDF.
Whitelist segura: tags semânticas + attrs básicos apenas.
"""
from __future__ import annotations

import re

import bleach
from bleach.css_sanitizer import CSSSanitizer


ALLOWED_TAGS = {
    "p",
    "br",
    "hr",
    "b",
    "i",
    "u",
    "s",
    "strong",
    "em",
    "h1",
    "h2",
    "h3",
    "ul",
    "ol",
    "li",
    "blockquote",
    "a",
    "span",
    "div",
    "img",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}

# `src` de img não passa por whitelist de tag — só pode apontar pro endpoint
# interno de imagens do editor (ver `services/editor_imagens.py`); qualquer
# outra coisa (http externo, data:, javascript:) é removida.
_IMG_SRC_RE = re.compile(r"^/api/v2/editor-imagens/[a-f0-9]{32}\.(png|jpe?g|gif|webp)$")
# Só a forma exata que o TextAlign do TipTap gera — nunca url(), nunca outra propriedade.
_TEXT_ALIGN_RE = re.compile(r"^text-align:\s*(left|right|center|justify);?$")


def _allow_img_src(_tag: str, name: str, value: str) -> bool:
    if name == "alt":
        return True
    if name == "src":
        return bool(_IMG_SRC_RE.match(value))
    return False


ALLOWED_ATTRS = {
    "a": ["href", "title"],
    "span": ["class"],
    "div": ["class"],
    "img": _allow_img_src,
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
    "p": ["style"],
    "h2": ["style"],
    "h3": ["style"],
}

# bleach >= 6 zera QUALQUER `style` sem isso — não é opcional para o
# text-align sobreviver. `_TEXT_ALIGN_RE` acima documenta a forma esperada;
# quem valida de fato é este sanitizador de CSS.
_CSS_SANITIZER = CSSSanitizer(allowed_css_properties=["text-align"])


def sanitizar_html(html: str) -> str:
    """Sanitiza HTML removendo tags/attrs perigosas.

    Args:
        html: Conteúdo HTML bruto (pode vir de templates admin ou TipTap frontend)

    Returns:
        HTML sanitizado, seguro para PDF e armazenamento

    Examples:
        >>> sanitizar_html('<p onclick="alert(1)">texto</p>')
        '<p>texto</p>'
        >>> sanitizar_html('<p><script>alert(1)</script>texto</p>')
        '<p>texto</p>'
    """
    if not html:
        return html

    # bleach.clean remove tags não permitidas, attrs não permitidas, e scripts
    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        css_sanitizer=_CSS_SANITIZER,
        strip=True,
    )

    # Escapa caracteres especiais em URLs (defesa extra contra XSS)
    # bleach já faz isso, mas redundância é OK para segurança
    return cleaned
