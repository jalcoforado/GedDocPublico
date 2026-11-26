"""SI-31 — template montado por blocos.

O frontend grava cada bloco como `<div class="bloco bloco-<tipo>">` com o
miolo em `<h2>`/`<p>` alinhados, `<strong>` e `<hr>`. O que se trava aqui: o
`sanitizar_html` (que roda ao criar a minuta a partir do modelo) deixa tudo
isso passar — sem o embrulho, o modelo não volta a abrir em blocos; sem o
`text-align`, a assinatura e a data saem à esquerda no PDF.

O HTML abaixo é o que `blocosParaHtml` (frontend/lib/template-blocos.ts) gera;
o teste do frontend trava o outro lado.
"""
from __future__ import annotations

from app.services.html_sanitizer import sanitizar_html
from app.services.placeholders import PLACEHOLDERS_DISPONIVEIS

BLOCOS = (
    '<div class="bloco bloco-titulo"><h2 style="text-align: center">Ofício</h2></div>'
    '<div class="bloco bloco-texto"><p>Encaminho o processo {{processo.numero}}.</p></div>'
    '<div class="bloco bloco-campo"><p><strong>Requerente:</strong> {{requerente.nome}}</p></div>'
    '<div class="bloco bloco-separador"><hr></div>'
    '<div class="bloco bloco-data_local"><p style="text-align: right">Itaitinga, {{data_hoje}}.</p></div>'
    '<div class="bloco bloco-assinatura">'
    '<p style="text-align: center">________________________________________</p>'
    '<p style="text-align: center"><strong>{{usuario.nome}}</strong></p>'
    '<p style="text-align: center">Secretário</p></div>'
)


def test_sanitizador_preserva_embrulho_e_alinhamento():
    limpo = sanitizar_html(BLOCOS)
    for tipo in ("titulo", "texto", "campo", "separador", "data_local", "assinatura"):
        assert f'<div class="bloco bloco-{tipo}">' in limpo
    assert '<h2 style="text-align: center;">Ofício</h2>' in limpo or '<h2 style="text-align: center">Ofício</h2>' in limpo
    assert limpo.count("text-align: center") == 4
    assert "text-align: right" in limpo
    assert "<hr>" in limpo and "<strong>Requerente:</strong>" in limpo


def test_campos_que_os_blocos_usam_existem_no_catalogo():
    """Data e local usa `data_hoje`; Assinatura nasce com `usuario.nome`."""
    chaves = {p["chave"] for p in PLACEHOLDERS_DISPONIVEIS}
    assert {"data_hoje", "usuario.nome", "processo.numero"} <= chaves
