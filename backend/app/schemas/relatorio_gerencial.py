"""Página gerencial de relatórios (SI-34) — uma tela, cinco seções.

Cada seção conta pela SUA data (decisão de 2026-11-11): entrada pela
abertura, saída pelo arquivamento, gargalos pela chegada na unidade,
assinaturas pelo pedido. "Andamento" é a situação de HOJE e não usa período.
Um seletor único de data no topo faria a saída contar "abertos em outubro que
um dia foram arquivados" — número plausível que responde outra pergunta.
"""
from pydantic import BaseModel

from .relatorio_assinaturas import AssinaturasTotais


class CanalContagem(BaseModel):
    canal: str | None  # None = não informado (processos anteriores ao campo)
    rotulo: str
    count: int


class SecaoEntrada(BaseModel):
    abertos: int
    por_canal: list[CanalContagem]


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
    gargalos: SecaoGargalos
    assinaturas: AssinaturasTotais
