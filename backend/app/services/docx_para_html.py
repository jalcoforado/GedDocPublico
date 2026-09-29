"""DOCX (exportado do Google Docs) → HTML do editor da plataforma.

Usado por `minutas.sincronizar_google_doc_para_minuta`. Função pura: bytes
entram, HTML sai — sem banco, sem Google, testável isoladamente
(`tests/test_docx_para_html.py`).

O que é trazido, dentro do que `html_sanitizer` aceita e o editor (TipTap)
reedita:
- negrito, itálico, sublinhado e tachado (`strong`/`em`/`u`/`s`);
- títulos: "Título" e "Título 1" → `h2`; níveis abaixo → `h3` (o editor só
  tem esses dois);
- alinhamento centro/direita/justificado → `style="text-align: …"`;
- listas com marcador e numeradas, pela numeração direta do parágrafo (é como
  o Google exporta) ou pelo estilo do Word; níveis aninhados saem achatados
  num nível só;
- tabelas, na ordem em que aparecem no corpo;
- quebra de linha dentro do parágrafo → `br`.

O que não vem: imagens, links (o texto vem, o destino não), cores, fontes,
recuos e cabeçalho/rodapé.

Invariante: parágrafo sem formatação e alinhado à esquerda sai exatamente
`<p>texto</p>`, igual à conversão anterior — senão a primeira sincronização
depois da troca criaria versão nova em toda minuta sem mudança real.

Todo texto é escapado: o conteúdo do Google Doc é texto, não marcação (`<nome>`
digitado lá é um placeholder, não uma tag).
"""
from __future__ import annotations

import io
from html import escape

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run

_ALINHAMENTO = {"center": "center", "right": "right", "both": "justify", "distribute": "justify"}
_TAGS = (("b", "strong"), ("i", "em"), ("u", "u"), ("s", "s"))


def _formato(run: Run) -> tuple[bool, bool, bool, bool]:
    return (bool(run.bold), bool(run.italic), bool(run.underline), bool(run.font.strike))


def _runs(p: Paragraph):
    """Runs na ordem, incluindo os de dentro de links (`w:hyperlink`)."""
    for el in p._p.iterchildren():
        if el.tag == qn("w:r"):
            yield Run(el, p)
        elif el.tag == qn("w:hyperlink"):
            for r in el.iterchildren(qn("w:r")):
                yield Run(r, p)


def _inline(p: Paragraph) -> str:
    """Conteúdo do parágrafo: runs vizinhos de mesmo formato fundidos, bordas
    sem espaço (como o `strip()` da conversão antiga)."""
    trechos: list[list] = []
    for r in _runs(p):
        texto = r.text
        if not texto:
            continue
        f = _formato(r)
        if trechos and trechos[-1][1] == f:
            trechos[-1][0] += texto
        else:
            trechos.append([texto, f])
    while trechos and not trechos[0][0].strip():
        trechos.pop(0)
    while trechos and not trechos[-1][0].strip():
        trechos.pop()
    if not trechos:
        return ""
    trechos[0][0] = trechos[0][0].lstrip()
    trechos[-1][0] = trechos[-1][0].rstrip()

    saida = []
    for texto, f in trechos:
        corpo = escape(texto, quote=False).replace("\t", " ").replace("\n", "<br>")
        abre = "".join(f"<{tag}>" for ligado, (_, tag) in zip(f, _TAGS) if ligado)
        fecha = "".join(f"</{tag}>" for ligado, (_, tag) in reversed(list(zip(f, _TAGS))) if ligado)
        saida.append(f"{abre}{corpo}{fecha}")
    return "".join(saida)


def _titulo(p: Paragraph) -> str | None:
    nome = (p.style.name if p.style is not None else "") or ""
    if nome == "Title":
        return "h2"
    if nome.startswith("Heading "):
        try:
            nivel = int(nome.split()[1])
        except (IndexError, ValueError):
            return None
        return "h2" if nivel <= 1 else "h3"
    return None


def _estilo_alinhamento(p: Paragraph) -> str:
    ppr = p._p.pPr
    jc = ppr.find(qn("w:jc")) if ppr is not None else None
    valor = _ALINHAMENTO.get(jc.get(qn("w:val"))) if jc is not None else None
    return f' style="text-align: {valor};"' if valor else ""


class _Numeracao:
    """Resolve se um parágrafo é item de lista e de que tipo (ul/ol)."""

    def __init__(self, doc) -> None:
        self._fmt: dict[tuple[str, str], str] = {}
        try:
            numbering = doc.part.numbering_part.element
        except (KeyError, NotImplementedError, AttributeError):
            return
        abstratos: dict[str, dict[str, str]] = {}
        for a in numbering.findall(qn("w:abstractNum")):
            niveis = {}
            for lvl in a.findall(qn("w:lvl")):
                nf = lvl.find(qn("w:numFmt"))
                niveis[lvl.get(qn("w:ilvl"))] = nf.get(qn("w:val")) if nf is not None else "decimal"
            abstratos[a.get(qn("w:abstractNumId"))] = niveis
        for n in numbering.findall(qn("w:num")):
            ref = n.find(qn("w:abstractNumId"))
            if ref is None:
                continue
            for ilvl, fmt in abstratos.get(ref.get(qn("w:val")), {}).items():
                self._fmt[(n.get(qn("w:numId")), ilvl)] = fmt

    @staticmethod
    def _numpr(p: Paragraph):
        ppr = p._p.pPr
        if ppr is not None and ppr.find(qn("w:numPr")) is not None:
            return ppr.find(qn("w:numPr"))
        estilo = p.style
        while estilo is not None:
            sppr = estilo.element.find(qn("w:pPr"))
            if sppr is not None and sppr.find(qn("w:numPr")) is not None:
                return sppr.find(qn("w:numPr"))
            estilo = estilo.base_style
        return None

    def tipo(self, p: Paragraph) -> str | None:
        numpr = self._numpr(p)
        if numpr is None:
            return None
        num = numpr.find(qn("w:numId"))
        if num is None or num.get(qn("w:val")) == "0":  # numId 0 = "sem numeração"
            return None
        ilvl_el = numpr.find(qn("w:ilvl"))
        ilvl = ilvl_el.get(qn("w:val")) if ilvl_el is not None else "0"
        fmt = self._fmt.get((num.get(qn("w:val")), ilvl))
        if fmt is None:
            nome = (p.style.name if p.style is not None else "") or ""
            return "ol" if "Number" in nome else "ul"
        return "ul" if fmt in ("bullet", "none") else "ol"


def _tabela(t: Table) -> str:
    linhas = []
    for row in t.rows:
        celulas = []
        for cell in row.cells:
            partes = [x for x in (_inline(p) for p in cell.paragraphs) if x]
            celulas.append(f"<td>{'<br>'.join(partes)}</td>")
        linhas.append(f"<tr>{''.join(celulas)}</tr>")
    return f"<table><tbody>{''.join(linhas)}</tbody></table>"


def docx_para_html(conteudo: bytes) -> str:
    doc = Document(io.BytesIO(conteudo))
    numeracao = _Numeracao(doc)
    saida: list[str] = []
    lista_aberta: str | None = None

    def fecha_lista() -> None:
        nonlocal lista_aberta
        if lista_aberta:
            saida.append(f"</{lista_aberta}>")
            lista_aberta = None

    for el in doc.element.body.iterchildren():
        if el.tag == qn("w:tbl"):
            fecha_lista()
            saida.append(_tabela(Table(el, doc)))
            continue
        if el.tag != qn("w:p"):
            continue
        p = Paragraph(el, doc)
        conteudo_p = _inline(p)
        if not conteudo_p:
            continue  # parágrafo vazio não fecha lista: o Google intercala linhas em branco
        tipo_lista = numeracao.tipo(p)
        if tipo_lista:
            if lista_aberta != tipo_lista:
                fecha_lista()
                saida.append(f"<{tipo_lista}>")
                lista_aberta = tipo_lista
            saida.append(f"<li>{conteudo_p}</li>")
            continue
        fecha_lista()
        tag = _titulo(p) or "p"
        saida.append(f"<{tag}{_estilo_alinhamento(p)}>{conteudo_p}</{tag}>")
    fecha_lista()
    return "".join(saida)
