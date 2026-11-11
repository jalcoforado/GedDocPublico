"""Página gerencial de relatórios (SI-34) — uma tela, cinco seções.

Cada seção conta pela SUA data (decisão de 2026-11-11): entrada pela
abertura, saída pelo arquivamento, gargalos pela chegada na unidade,
assinaturas pelo pedido. "Andamento" é a situação de HOJE e não usa período.
Um seletor único de data no topo faria a saída contar "abertos em outubro que
um dia foram arquivados" — número plausível que responde outra pergunta.
"""
from datetime import date
from typing import Literal

from pydantic import BaseModel

from .relatorio_assinaturas import AssinaturasTotais


class CanalContagem(BaseModel):
    canal: str | None  # None = não informado (processos anteriores ao campo)
    rotulo: str
    count: int


class AssuntoContagem(BaseModel):
    id_assunto: int
    assunto: str | None
    count: int


class SecaoEntrada(BaseModel):
    abertos: int
    por_canal: list[CanalContagem]
    # Os cinco assuntos com mais processos abertos no período.
    top_assuntos: list[AssuntoContagem]


class SecaoPrazos(BaseModel):
    """Prazo do SERVIÇO (`prazos.calcular_prazo`): abertura + N dias corridos.

    Só processos com prazo entram nas contas de prazo; os `*_sem_prazo` dizem
    quantos ficaram de fora, para um "95% no prazo" não esconder que fala de
    um quinto dos processos.
    """
    # Arquivados no período (pela data de arquivamento).
    concluidos_no_prazo: int
    concluidos_atrasados: int
    concluidos_sem_prazo: int
    # Não arquivados, hoje (sem período).
    dentro_do_prazo: int
    vencendo: int
    atrasados: int
    em_aberto_sem_prazo: int


class PontoTendencia(BaseModel):
    inicio: date  # segunda-feira da semana, ou dia 1 do mês (dia local)
    abertos: int
    arquivados: int


class SecaoTendencia(BaseModel):
    granularidade: Literal["semana", "mes"]
    # O período do gráfico: o do filtro, ou as últimas 12 semanas sem filtro.
    desde: date
    ate: date
    pontos: list[PontoTendencia]


class Comparacao(BaseModel):
    """Mesmo recorte no período imediatamente anterior, de mesmo tamanho.
    Diferença em números, não em %: com bases pequenas a % engana."""
    desde: date
    ate: date
    abertos: int
    arquivados: int


class SecaoAndamento(BaseModel):
    em_andamento: int
    em_transito: int
    parados: int
    dias_parado: int


class SecaoSaida(BaseModel):
    arquivados: int
    # Da abertura ao arquivamento, só dos arquivados no período.
    dias_medio_ate_arquivar: float | None


class GargaloUnidade(BaseModel):
    id_unidade: int | None
    unidade: str | None
    # Entradas na unidade no período: abertura (na unidade dona) ou recebimento
    # — as estadias da tramitação. Envio pendente ou recusado não entra.
    chegadas: int
    com_prazo: int
    atrasos: int  # das entradas com prazo, quantas saíram (ou seguem) após o fim do dia
    dias_medio: float | None  # permanência média das estadias já encerradas


class SecaoGargalos(BaseModel):
    unidades: list[GargaloUnidade]
    # A base é o relatório de tramitação, que tem teto de processos.
    cortado: bool


class GerencialResposta(BaseModel):
    descricao_filtros: list[str]
    entrada: SecaoEntrada
    andamento: SecaoAndamento
    saida: SecaoSaida
    prazos: SecaoPrazos
    tendencia: SecaoTendencia
    # Só quando o filtro tem início e fim.
    comparacao: Comparacao | None
    gargalos: SecaoGargalos
    assinaturas: AssinaturasTotais
