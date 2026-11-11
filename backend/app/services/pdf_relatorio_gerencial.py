"""PDF da página gerencial de relatórios (SI-34) — a tela inteira, uma página."""
from __future__ import annotations

import html
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..schemas.relatorio_gerencial import GerencialResposta
from ..utils.relogio import agora_utc
from .relatorios_comum import hora_local

APRIMORA = HexColor("#1e3a5f")
GRAY = HexColor("#6b7280")
LIGHT = HexColor("#f3f4f6")


def _dias(v: float | None) -> str:
    return "—" if v is None else f"{v:.1f} dias".replace(".", ",")


def _horas_de_minutos(m: float) -> str:
    return _dias(m / 1440) if m else "—"


def gerar_gerencial_pdf(r: GerencialResposta) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm, title="Relatório gerencial de processos",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=APRIMORA, fontSize=17, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=APRIMORA, fontSize=12, spaceAfter=2)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=GRAY)
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=9, leading=11)

    def tabela(dados, larguras):
        t = Table(dados, colWidths=larguras, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
            ("TEXTCOLOR", (0, 0), (-1, 0), GRAY),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    s: list = [
        Paragraph("APRIMORA — Relatório gerencial de processos", h1),
        Paragraph(
            f"Emitido em {hora_local(agora_utc()).strftime('%d/%m/%Y %H:%M')} (hora de Brasília)",
            small,
        ),
        Spacer(1, 0.3 * cm),
    ]
    s += [Paragraph(html.escape(linha), normal) for linha in r.descricao_filtros]

    e = r.entrada
    s += [Spacer(1, 0.4 * cm), Paragraph(f"Entrada — {e.abertos} abertos no período (pela abertura)", h2)]
    if e.por_canal:
        s.append(tabela(
            [["Canal", "Processos"]] + [[c.rotulo, str(c.count)] for c in e.por_canal],
            [12 * cm, 5 * cm],
        ))

    a = r.andamento
    s += [
        Spacer(1, 0.4 * cm),
        Paragraph("Andamento — situação de hoje", h2),
        tabela(
            [["Em andamento", "Em trânsito", f"Parados há {a.dias_parado}+ dias"],
             [str(a.em_andamento), str(a.em_transito), str(a.parados)]],
            [5.6 * cm] * 3,
        ),
    ]

    sa = r.saida
    s += [
        Spacer(1, 0.4 * cm),
        Paragraph("Saída — arquivados no período (pelo arquivamento)", h2),
        tabela(
            [["Arquivados", "Tempo médio da abertura ao arquivamento"],
             [str(sa.arquivados), _dias(sa.dias_medio_ate_arquivar)]],
            [5.6 * cm, 11.4 * cm],
        ),
    ]

    g = r.gargalos
    s += [Spacer(1, 0.4 * cm), Paragraph("Gargalos — entradas nas unidades no período (abertura ou recebimento)", h2)]
    if g.unidades:
        s.append(tabela(
            [["Unidade", "Entradas", "Com prazo", "Atrasos", "Permanência média"]]
            + [[Paragraph(html.escape(u.unidade or "—"), normal), str(u.chegadas),
                str(u.com_prazo), str(u.atrasos), _dias(u.dias_medio)] for u in g.unidades],
            [7 * cm, 2.4 * cm, 2.4 * cm, 2.2 * cm, 3 * cm],
        ))
        if g.cortado:
            s.append(Paragraph("Recorte grande: a análise cobre os processos mais recentes.", small))
    else:
        s.append(Paragraph("Nenhuma entrada em unidade no período.", small))

    t = r.assinaturas
    s += [
        Spacer(1, 0.4 * cm),
        Paragraph("Assinaturas — pedidas no período (pelo pedido)", h2),
        tabela(
            [["Pedidas", "Pendentes", "Concluídas", "Canceladas", "Tempo médio"],
             [str(t.total), str(t.pendentes), str(t.concluidas), str(t.canceladas),
              _horas_de_minutos(t.minutos_medio_conclusao)]],
            [3.4 * cm] * 5,
        ),
    ]
    doc.build(s)
    return buf.getvalue()
