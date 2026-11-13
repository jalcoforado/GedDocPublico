"""PDF do relatório montado (SI-35) — no padrão dos outros PDFs de relatório:
título, recorte, totais, agrupamento (se houver) e a lista, com o mesmo rodapé.

As colunas são as que a pessoa escolheu; a largura é dividida entre elas e a
fonte encolhe quando são muitas, para caber em A4 deitado.
"""
from __future__ import annotations

import html
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..schemas.relatorio_montado import ResultadoMontado
from ..utils.relogio import agora_utc
from .pdf_relatorio import APRIMORA, GRAY, LIGHT, _footer
from .relatorios_comum import hora_local
from .sigilo import NIVEL_LABEL


def formatar_valor(v, tipo: str) -> str:
    """Valor da célula para leitura humana — o mesmo no PDF e no CSV."""
    if v is None or v == "":
        return ""
    if tipo == "data_hora":
        s = str(v)
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]} {s[11:16]}"
    if tipo == "data":
        s = str(v)
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return str(v)


def gerar_montado_pdf(r: ResultadoMontado, nome: str | None = None) -> bytes:
    buf = BytesIO()
    titulo = nome or "Relatório montado"
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm, title=titulo,
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=APRIMORA, fontSize=18, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=APRIMORA, fontSize=12, spaceAfter=4)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=GRAY)
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=9, leading=11)

    n_cols = len(r.colunas) + 1
    corpo = 8 if n_cols <= 8 else 7 if n_cols <= 12 else 6
    celula = ParagraphStyle("cel", parent=styles["Normal"], fontSize=corpo, leading=corpo + 2)
    cabeca = ParagraphStyle(
        "cab", parent=celula, fontName="Helvetica-Bold", textColor=colors.white
    )

    s: list = [
        Paragraph(f"APRIMORA — {html.escape(titulo)}", h1),
        Paragraph(
            f"Emitido em {hora_local(agora_utc()).strftime('%d/%m/%Y %H:%M')} (hora de Brasília)", small
        ),
        Spacer(1, 0.4 * cm),
    ]
    s += [Paragraph(html.escape(linha), normal) for linha in r.descricao_filtros]
    s.append(Spacer(1, 0.4 * cm))

    t = r.totais
    totais = Table(
        [["Processos", "Em andamento", "Em trânsito", "Arquivados"],
         [str(t.total), str(t.em_andamento), str(t.em_transito), str(t.arquivados)]],
        colWidths=[5 * cm] * 4,
    )
    totais.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), GRAY),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 16),
        ("TEXTCOLOR", (0, 1), (-1, 1), APRIMORA),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    s += [totais, Spacer(1, 0.5 * cm)]

    if r.agrupamento:
        s.append(Paragraph(f"Por {html.escape((r.rotulo_agrupamento or '').lower())}", h2))
        g = Table(
            [[r.rotulo_agrupamento or "", "Processos", "%"]]
            + [[Paragraph(html.escape(i.label), normal), str(i.count), f"{i.pct:.1f}".replace(".", ",")]
               for i in r.agrupamento],
            colWidths=[12 * cm, 3 * cm, 2.5 * cm], repeatRows=1,
        )
        g.setStyle(_estilo_tabela())
        s += [g, Spacer(1, 0.5 * cm)]

    if r.cortado:
        s.append(Paragraph(f"Processos (os {len(r.linhas)} primeiros de {t.total})", h2))
        s.append(Paragraph(
            "A lista do PDF tem limite; os totais acima contam o recorte inteiro. "
            "Para a lista completa, exporte o CSV.", small,
        ))
    else:
        s.append(Paragraph(f"Processos ({len(r.linhas)})", h2))

    if r.linhas:
        largura = landscape(A4)[0] - 3 * cm
        primeira = min(4 * cm, largura / n_cols * 1.4)
        resto = (largura - primeira) / max(1, n_cols - 1)
        linhas = [[Paragraph("Número", cabeca)] + [Paragraph(html.escape(c.rotulo), cabeca) for c in r.colunas]]
        for ln in r.linhas:
            numero = html.escape(ln.numero_processo)
            if ln.nivel_sigilo != "ostensivo":
                numero += f"<br/>{html.escape(NIVEL_LABEL.get(ln.nivel_sigilo, 'Sigiloso'))}"
            linhas.append(
                [Paragraph(numero, celula)]
                + [Paragraph(html.escape(formatar_valor(ln.valores.get(c.chave), c.tipo)) or "—", celula)
                   for c in r.colunas]
            )
        tabela = Table(linhas, colWidths=[primeira] + [resto] * (n_cols - 1), repeatRows=1)
        tabela.setStyle(_estilo_tabela())
        s.append(tabela)
    else:
        s.append(Paragraph("Nenhum processo no recorte.", small))

    doc.build(s, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _estilo_tabela() -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), APRIMORA),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])
