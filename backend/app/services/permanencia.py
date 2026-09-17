"""Quanto tempo o processo ficou em cada etapa, e quanto disso foi espera.

Por que dois tempos, e não um
-----------------------------
"O processo levou 40 dias" não diz a quem cobrar. Quarenta dias parados numa
caixa de entrada e quarenta dias com um analista lendo são problemas
diferentes, com donos diferentes e correções opostas: o primeiro é gargalo de
**fila** (falta quem pegue), o segundo é gargalo de **trabalho** (falta
capacidade de quem já pegou). Hoje não mostramos nenhum dos dois.

Como a distinção cai de graça na estrutura que já existe
--------------------------------------------------------
Receber um processo **cria uma movimentação própria** (ação `RECEBIMENTO`,
`acoes_processo.py`), carimbada com o mesmo instante que grava
`encaminhamento.data_hora_recebimento`. Então espera e análise não são dois
pedaços dentro de um nó — são **nós vizinhos**:

    ENCAMINHAMENTO ──── espera ────> RECEBIMENTO ──── análise ────> (próxima)
    t0                              t1                             t2

A permanência de um nó é, portanto, a distância até o nó seguinte. O que
classifica cada trecho é o `status_movimentacao` do catálogo `protocolos.acao`
(`inicial` / `encaminhado` / `recebido` / `final`) — e não o `flag`. A diferença
importa: `flag` é o nome da ação e muda quando alguém cadastra uma ação nova;
`status_movimentacao` é a natureza dela. Ação desconhecida cai em análise, que
é o padrão seguro: conta como tempo de alguém, não some da soma.

Este módulo não conhece ORM, sessão nem schema Pydantic. É função pura sobre
uma lista de instantes, e é por isso que dá para testá-lo sem banco.

O clamp em zero não é paranoia
------------------------------
`segundos` nunca é negativo, por três motivos reais e nenhum hipotético:

1. **Os carimbos vêm de relógios diferentes.** `acoes_processo` grava com
   `datetime.now()`; `workflow_engine` grava a mesma coluna com
   `datetime.utcnow()`. Hoje coincidem porque o container roda em UTC (medido
   em 2026-09-16: delta 0 s), mas basta alguém definir `TZ` para que passem a
   divergir em 3 h — e aí a movimentação do workflow fica *antes* da anterior.
2. **Processo migrado** (`processo.migrado`) traz data do sistema legado, sem
   garantia de monotonicidade.
3. **Seed** escreve datas explícitas, inclusive fora de ordem.

Diante de qualquer um dos três, a escolha é entre exibir número negativo e
exibir zero. Negativo vira bug reportado; zero é a leitura honesta de "não sei
dizer, e não foi tempo nenhum que eu consiga provar".
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Sequence

# Valores de `protocolos.acao.status_movimentacao`. Os quatro do catálogo são
# `inicial`, `encaminhado`, `recebido` e `final`; só estes dois são especiais.
ESPERA = "encaminhado"
ENCERRADO = "final"

Natureza = Literal["espera", "analise", "encerrado"]


@dataclass(frozen=True)
class No:
    """O mínimo que o cálculo precisa de um nó da linha do tempo.

    `id` existe para que o chamador reencontre o resultado sem depender da
    ordem em que passou os nós — a timeline do detalhe vem em ordem
    decrescente, e parear por índice seria um erro esperando acontecer.
    """

    id: int
    momento: datetime
    status_movimentacao: str


@dataclass(frozen=True)
class Permanencia:
    """Quanto tempo o processo ficou NESTE nó."""

    segundos: int
    natureza: Natureza
    # `aberto` = não há nó posterior, então este tempo ainda está correndo.
    aberto: bool


@dataclass(frozen=True)
class Resumo:
    """O agregado do processo inteiro."""

    # Espera + análise. NÃO é a distância entre a abertura e agora: trecho
    # posterior ao arquivamento não é tempo de tramitação de ninguém, e somá-lo
    # faria um processo arquivado há dois anos parecer o mais lento da casa.
    total_ativo_segundos: int
    espera_segundos: int
    analise_segundos: int
    # Quantas vezes o processo foi encaminhado.
    tramitacoes: int
    em_curso: bool


def _natureza(status_movimentacao: str) -> Natureza:
    if status_movimentacao == ESPERA:
        return "espera"
    if status_movimentacao == ENCERRADO:
        return "encerrado"
    return "analise"


def calcular(
    nos: Sequence[No], *, agora: datetime
) -> tuple[dict[int, Permanencia], Resumo]:
    """Permanência de cada nó e o agregado do processo.

    `nos` pode vir em qualquer ordem; o resultado é indexado por `No.id`.
    """
    if not nos:
        return {}, Resumo(
            total_ativo_segundos=0,
            espera_segundos=0,
            analise_segundos=0,
            tramitacoes=0,
            em_curso=False,
        )

    # Desempate por `id` para que dois carimbos idênticos — que acontecem, já
    # que receber grava o mesmo instante em duas linhas — tenham ordem estável.
    ordenados = sorted(nos, key=lambda n: (n.momento, n.id))

    por_id: dict[int, Permanencia] = {}
    espera = 0
    analise = 0
    tramitacoes = 0

    for i, no in enumerate(ordenados):
        proximo = ordenados[i + 1].momento if i + 1 < len(ordenados) else None
        aberto = proximo is None
        natureza = _natureza(no.status_movimentacao)

        if natureza == "encerrado" and aberto:
            # Processo arquivado e parado. O tempo desde o arquivamento passa,
            # mas não é permanência: ninguém o está segurando.
            segundos = 0
        else:
            fim = proximo if proximo is not None else agora
            segundos = max(0, int((fim - no.momento).total_seconds()))

        por_id[no.id] = Permanencia(
            segundos=segundos, natureza=natureza, aberto=aberto
        )

        if natureza == "espera":
            espera += segundos
            tramitacoes += 1
        elif natureza == "analise":
            analise += segundos

    ultimo = ordenados[-1]
    return por_id, Resumo(
        total_ativo_segundos=espera + analise,
        espera_segundos=espera,
        analise_segundos=analise,
        tramitacoes=tramitacoes,
        em_curso=_natureza(ultimo.status_movimentacao) != "encerrado",
    )
