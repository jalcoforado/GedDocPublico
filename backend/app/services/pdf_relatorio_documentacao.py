"""PDF da lista de documentação (SI-34) — no padrão do PDF da lista de
processos: cabeçalho, recorte, totais e a lista, com o mesmo rodapé.

Como a tela e o CSV, não traz a mensagem do pedido de complementação.
"""
from __future__ import annotations

import html
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..schemas.relatorio_documentacao import RelatorioDocumentacaoResposta
from ..utils.relogio import agora_utc
from .pdf_relatorio import APRIMORA, GRAY, LIGHT, _footer, _table_style
from .relatorios_comum import hora_local
from .relatorios_documentacao import ROTULO_COMPLEMENTACAO, ROTULO_STATUS_DOC
from .sigilo import NIVEL_LABEL


def _data(d) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def gerar_documentacao_pdf(r: RelatorioDocumentacaoResposta) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm, title="Relatório de documentação",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=APRIMORA, fontSize=18, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=APRIMORA, fontSize=12, spaceAfter=4)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=GRAY)
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=9, leading=11)

    s: list = [
        Paragraph("APRIMORA — Relatório de documentação", h1),
        Paragraph(
            f"Emitido em {hora_local(agora_utc()).strftime('%d/%m/%Y %H:%M')} (hora de Brasília)", small
        ),
        Spacer(1, 0.4 * cm),
    ]
    s += [Paragraph(html.escape(linha), normal) for linha in r.descricao_filtros]
    s.append(Spacer(1, 0.4 * cm))

    t = r.totais
    totais = Table(
        [["Processos", "Pendentes", "Parciais", "Completos", "Aguardando o cidadão"],
         [str(t.total), str(t.pendentes), str(t.parciais), str(t.completos), str(t.aguardando_cidadao)]],
        colWidths=[5 * cm] * 5,
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

    if r.cortado:
        s.append(Paragraph(f"Processos (os {len(r.processos)} mais recentes de {t.total})", h2))
        s.append(Paragraph(
            "A lista do PDF tem limite; os totais acima contam o recorte inteiro. "
            "Para a lista completa, exporte o CSV.", small,
        ))
    else:
        s.append(Paragraph(f"Processos ({len(r.processos)})", h2))

    if r.processos:
        linhas = [["Número", "Aberto em", "Serviço", "Documentos", "Complementação", "Onde está"]]
        for p in r.processos:
            numero = html.escape(p.numero_processo)
            if p.nivel_sigilo != "ostensivo":
                numero += f"<br/>{html.escape(NIVEL_LABEL.get(p.nivel_sigilo, 'Sigiloso'))}"
            documentos = ROTULO_STATUS_DOC[p.status_documental]
            if p.obrigatorios_total:
                documentos += f"<br/>{p.obrigatorios_enviados} de {p.obrigatorios_total} obrigatórios"
            if p.complementacao_status:
                compl = ROTULO_COMPLEMENTACAO[p.complementacao_status]
                compl += f"<br/>pedida {_data(p.complementacao_pedida_em)}"
                if p.complementacao_respondida_em:
                    compl += f" · respondida {_data(p.complementacao_respondida_em)}"
            else:
                compl = "—"
            linhas.append([
                Paragraph(numero, normal),
                p.data_hora_abertura.strftime("%d/%m/%Y %H:%M"),
                Paragraph(html.escape(p.servico or "—"), normal),
                Paragraph(documentos, normal),
                Paragraph(compl, normal),
                Paragraph(html.escape(p.local_atual or "—"), normal),
            ])
        tabela = Table(
            linhas, colWidths=[4 * cm, 2.8 * cm, 5.5 * cm, 4 * cm, 5.7 * cm, 4.5 * cm], repeatRows=1
        )
        tabela.setStyle(_table_style())
        s.append(tabela)
    else:
        s.append(Paragraph("Nenhum processo no recorte.", small))

    doc.build(s, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
