"""PDF dos relatórios: órgão no título, quem emitiu e "Página X de Y".

Sem banco: monta respostas vazias/mínimas dos três relatórios, gera o PDF e
lê o texto de volta com pypdf (já dependência do carimbo).
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from pypdf import PdfReader

from app.schemas.relatorio import RelatorioFiltro, RelatorioResposta, RelatorioTotais
from app.schemas.relatorio_assinaturas import (
    AssinaturasFiltro,
    AssinaturasTotais,
    RelatorioAssinaturasResposta,
)
from app.schemas.relatorio_tramitacao import RelatorioTramitacaoResposta
from app.services.pdf_emissao import Emissao
from app.services.pdf_relatorio import gerar_relatorio_pdf
from app.services.pdf_relatorio_assinaturas import gerar_assinaturas_pdf
from app.services.pdf_relatorio_tramitacao import gerar_tramitacao_pdf

EMISSAO = Emissao(
    orgao="Prefeitura de Exemplo",
    emitido_por="Ana <Souza>",
    emitido_em=datetime(2026, 11, 12, 9, 30),
)


def _texto(pdf: bytes) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)


def _respostas():
    processos = RelatorioResposta(
        filtros_aplicados=RelatorioFiltro(),
        descricao_filtros=[],
        nome_unidade=None,
        totais=RelatorioTotais(
            total=0, em_andamento=0, em_transito=0, arquivados=0, sigilosos=0, externos=0
        ),
        por_tipo_processo=[],
        por_unidade_proprietaria=[],
        por_local_atual=[],
        por_assunto=[],
        por_servico=[],
        processos=[],
    )
    tramitacao = RelatorioTramitacaoResposta(
        filtros_aplicados=RelatorioFiltro(),
        descricao_filtros=[],
        nome_unidade=None,
        qtd_processos=0,
        qtd_listados=0,
        cortado=False,
        qtd_processos_com_atraso=0,
        minutos_medio_por_processo=0.0,
        por_unidade=[],
        processos=[],
    )
    assinaturas = RelatorioAssinaturasResposta.model_construct(
        filtros_aplicados=AssinaturasFiltro(),
        descricao_filtros=[],
        totais=AssinaturasTotais.model_construct(
            total=0, pendentes=0, concluidas=0, canceladas=0, minutos_medio_conclusao=None
        ),
        por_assinante=[],
        por_solicitante=[],
        solicitacoes=[],
    )
    return [
        (gerar_relatorio_pdf, processos, "Relatório de processos"),
        (gerar_tramitacao_pdf, tramitacao, "Relatório de tramitação"),
        (gerar_assinaturas_pdf, assinaturas, "Relatório de assinaturas"),
    ]


def test_cabecalho_com_orgao_emissor_e_total_de_paginas():
    for gerar, resposta, nome in _respostas():
        txt = _texto(gerar(resposta, EMISSAO))
        assert f"Prefeitura de Exemplo — {nome}" in txt, nome
        # Nome com "<" não pode quebrar o parser de marcação do reportlab.
        assert "Emitido em 12/11/2026 09:30 por Ana <Souza>" in txt, nome
        assert "Página 1 de 1" in txt, nome
        assert "APRIMORA —" not in txt, nome


def test_sem_emissao_continua_gerando():
    """O default não quebra chamadores antigos: cai em "Aprimora — …"."""
    for gerar, resposta, nome in _respostas():
        txt = _texto(gerar(resposta))
        assert f"Aprimora — {nome}" in txt
        assert "Página 1 de 1" in txt
