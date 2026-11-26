"""SI-67 — o que o editor de documento grava sobrevive até o PDF.

- Recuo do parágrafo (régua do editor): `margin-left`, `margin-right` e
  `text-indent` passam pelo sanitizador; outra propriedade de CSS continua
  sendo removida.
- Imagem redimensionada no editor (e o bloco Imagem do modelo): `width` e
  `height` numéricos passam; qualquer outra forma cai.
- O PDF sai com esses atributos (WeasyPrint com `presentational_hints`).
"""
from __future__ import annotations

from app.services.html_pdf import html_to_pdf_bytes
from app.services.html_sanitizer import sanitizar_html

IMG = "/api/v2/editor-imagens/" + "a" * 32 + ".png"


def test_recuo_do_paragrafo_passa():
    html = (
        '<p style="margin-left: 1.25cm; text-indent: 1.25cm; margin-right: 0.5cm">Texto</p>'
        '<h2 style="text-align: center; margin-left: 2cm">Título</h2>'
    )
    limpo = sanitizar_html(html)
    assert "margin-left: 1.25cm" in limpo
    assert "text-indent: 1.25cm" in limpo
    assert "margin-right: 0.5cm" in limpo
    assert "text-align: center" in limpo
    assert "margin-left: 2cm" in limpo


def test_outra_propriedade_de_css_continua_saindo():
    limpo = sanitizar_html(
        '<p style="margin-left: 1cm; color: red; background: url(http://x/y.png)">T</p>'
    )
    assert "margin-left: 1cm" in limpo
    assert "color" not in limpo
    assert "url(" not in limpo


def test_tamanho_numerico_da_imagem_passa():
    limpo = sanitizar_html(f'<p><img src="{IMG}" alt="" width="227" height="113.5"></p>')
    assert 'width="227"' in limpo
    assert 'height="113.5"' in limpo


def test_tamanho_que_nao_e_numero_cai():
    limpo = sanitizar_html(
        f'<p><img src="{IMG}" width="100%" height="1px;onload=x" onerror="alert(1)"></p>'
    )
    assert "width" not in limpo
    assert "height" not in limpo
    assert "onerror" not in limpo
    assert IMG in limpo


def test_pdf_sai_com_recuo_e_imagem_dimensionada():
    corpo = sanitizar_html(
        '<p style="text-indent: 1.25cm">Parágrafo com recuo.</p>'
        f'<p style="text-align: center"><img src="{IMG}" alt="" width="227"></p>'
    )
    pdf = html_to_pdf_bytes(corpo, titulo="Ofício")
    assert pdf.startswith(b"%PDF")
