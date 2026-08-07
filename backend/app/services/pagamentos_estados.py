"""As três dimensões de situação do débito — domínio puro (spec §4.1).

Até a F1 um único `Debito.status` de 16 valores respondia por três perguntas
independentes: onde está a decisão, onde está na fila cronológica e onde está a
execução. Como os valores eram mutuamente exclusivos, um débito `PAGO_PARCIAL`
não conseguia dizer sua situação de tramitação e nenhum conseguia dizer sua
posição na fila.

Este módulo não toca banco e não importa SQLAlchemy de propósito: é a única
parte do fluxo que dá para exercitar sem arreio, e é onde as regras que não
podem se perder ficam legíveis.

`status_legado()` deriva o valor antigo das três dimensões. A coluna `status`
continua existindo e mantida em sincronia até a F5, porque
`pagamentos_conciliacao`, `pagamentos_excecoes`, `pagamentos_caixa`,
`pagamentos_export`, `pagamentos_filas` e o frontend inteiro a leem. Migrar
todos na mesma fatia daria um diff que ninguém revisa com atenção.
"""
from __future__ import annotations

# ---------------------------------------------------------------- tramitação
RASCUNHO = "RASCUNHO"
AGUARDANDO_GESTOR = "AGUARDANDO_GESTOR"
AJUSTE_GESTOR = "AJUSTE_GESTOR"
AGUARDANDO_VALIDACAO = "AGUARDANDO_VALIDACAO"
AJUSTE_VALIDACAO = "AJUSTE_VALIDACAO"
AGUARDANDO_AUTORIDADE = "AGUARDANDO_AUTORIDADE"
AJUSTE_AUTORIDADE = "AJUSTE_AUTORIDADE"
AUTORIZADA = "AUTORIZADA"
REJEITADA_GESTOR = "REJEITADA_GESTOR"
INDEFERIDA_AUTORIDADE = "INDEFERIDA_AUTORIDADE"
CANCELADA = "CANCELADA"

TRAMITACAO = frozenset({
    RASCUNHO, AGUARDANDO_GESTOR, AJUSTE_GESTOR, AGUARDANDO_VALIDACAO,
    AJUSTE_VALIDACAO, AGUARDANDO_AUTORIDADE, AJUSTE_AUTORIDADE, AUTORIZADA,
    REJEITADA_GESTOR, INDEFERIDA_AUTORIDADE, CANCELADA,
})

TERMINAIS = frozenset({REJEITADA_GESTOR, INDEFERIDA_AUTORIDADE, CANCELADA})

# Grafo do rito. `AUTORIZADA` é terminal para a TRAMITAÇÃO — o que vem depois é
# execução, que é outra dimensão.
#
# A linha que carrega a fatia é a de AGUARDANDO_VALIDACAO: duas saídas, nenhuma
# terminal. Acrescentar um terminal aqui reabre exatamente o defeito que a F1
# fecha, e `test_validacao_nao_alcanca_nenhum_terminal` reprova.
TRANSICOES_TRAMITACAO: dict[str, frozenset[str]] = {
    RASCUNHO:              frozenset({AGUARDANDO_GESTOR, CANCELADA}),
    AGUARDANDO_GESTOR:     frozenset({AGUARDANDO_VALIDACAO, AJUSTE_GESTOR,
                                      REJEITADA_GESTOR, CANCELADA}),
    AJUSTE_GESTOR:         frozenset({AGUARDANDO_GESTOR, CANCELADA}),
    AGUARDANDO_VALIDACAO:  frozenset({AGUARDANDO_AUTORIDADE, AJUSTE_VALIDACAO}),
    AJUSTE_VALIDACAO:      frozenset({AGUARDANDO_VALIDACAO, AGUARDANDO_GESTOR, CANCELADA}),
    AGUARDANDO_AUTORIDADE: frozenset({AUTORIZADA, AJUSTE_AUTORIDADE,
                                      INDEFERIDA_AUTORIDADE, CANCELADA}),
    AJUSTE_AUTORIDADE:     frozenset({AGUARDANDO_AUTORIDADE, AGUARDANDO_GESTOR, CANCELADA}),
    AUTORIZADA:            frozenset(),
    REJEITADA_GESTOR:      frozenset(),
    INDEFERIDA_AUTORIDADE: frozenset(),
    CANCELADA:             frozenset(),
}

# Etapa do stepper de cinco passos.
ETAPA_POR_TRAMITACAO: dict[str, str] = {
    RASCUNHO:              "UNIDADE",
    AGUARDANDO_GESTOR:     "GESTOR",
    AJUSTE_GESTOR:         "UNIDADE",
    AGUARDANDO_VALIDACAO:  "VALIDACAO",
    AJUSTE_VALIDACAO:      "UNIDADE",
    AGUARDANDO_AUTORIDADE: "AUTORIDADE",
    AJUSTE_AUTORIDADE:     "UNIDADE",
    AUTORIZADA:            "TESOURARIA",
    REJEITADA_GESTOR:      "GESTOR",
    INDEFERIDA_AUTORIDADE: "AUTORIDADE",
    CANCELADA:             "UNIDADE",
}

# --------------------------------------------------------------------- fila
NAO_REGISTRADA = "NAO_REGISTRADA"
REGISTRADA = "REGISTRADA"
BLOQUEADA = "BLOQUEADA"
ELEGIVEL = "ELEGIVEL"
AGUARDANDO_DISPONIBILIDADE = "AGUARDANDO_DISPONIBILIDADE"
EXCECAO_AUTORIZADA = "EXCECAO_AUTORIZADA"
CONCLUIDA = "CONCLUIDA"
RETIRADA = "RETIRADA"

FILA = frozenset({
    NAO_REGISTRADA, REGISTRADA, BLOQUEADA, ELEGIVEL,
    AGUARDANDO_DISPONIBILIDADE, EXCECAO_AUTORIZADA, CONCLUIDA, RETIRADA,
})

# ---------------------------------------------------------------- pagamento
NAO_INICIADA = "NAO_INICIADA"
PROGRAMADA = "PROGRAMADA"
ENVIADA_BANCO = "ENVIADA_BANCO"
EM_PROCESSAMENTO = "EM_PROCESSAMENTO"
PAGA_PARCIAL = "PAGA_PARCIAL"
PAGA = "PAGA"
FALHOU = "FALHOU"
PAG_CANCELADA = "CANCELADA"
ESTORNADA = "ESTORNADA"
CONCILIADA = "CONCILIADA"

PAGAMENTO = frozenset({
    NAO_INICIADA, PROGRAMADA, ENVIADA_BANCO, EM_PROCESSAMENTO,
    PAGA_PARCIAL, PAGA, FALHOU, PAG_CANCELADA, ESTORNADA, CONCILIADA,
})


def transicao_permitida(atual: str, novo: str) -> bool:
    return novo in TRANSICOES_TRAMITACAO.get(atual, frozenset())


# --------------------------------------------------- derivação do status legado
_LEGADO_TRAMITACAO = {
    RASCUNHO: "RASCUNHO",
    AGUARDANDO_GESTOR: "EM_VALIDACAO",
    AGUARDANDO_VALIDACAO: "EM_VALIDACAO",
    AJUSTE_GESTOR: "DEVOLVIDO",
    AJUSTE_VALIDACAO: "DEVOLVIDO",
    AJUSTE_AUTORIDADE: "DEVOLVIDO",
    AGUARDANDO_AUTORIDADE: "VALIDADO",
    AUTORIZADA: "AUTORIZADO",
    REJEITADA_GESTOR: "REJEITADO",
    INDEFERIDA_AUTORIDADE: "REJEITADO",
    CANCELADA: "CANCELADO",
}

# Quando a execução começou, ela manda no valor legado — era assim que o campo
# único se comportava, e os consumidores que ainda o leem contam com isso.
_LEGADO_PAGAMENTO = {
    PROGRAMADA: "ENVIADO_TESOURARIA",
    ENVIADA_BANCO: "EM_PROCESSAMENTO",
    EM_PROCESSAMENTO: "EM_PROCESSAMENTO",
    PAGA_PARCIAL: "PAGO_PARCIAL",
    PAGA: "PAGO",
    FALHOU: "EM_PROCESSAMENTO",
    ESTORNADA: "ESTORNADO",
    CONCILIADA: "CONCILIADO",
}


def status_legado(tramitacao: str, fila: str, pagamento: str) -> str:
    """Valor de `Debito.status` correspondente às três dimensões.

    Precedência: cancelamento > programado-aguardando-autoridade > execução
    iniciada > bloqueio de fila > tramitação. Cancelamento vem primeiro
    porque `CANCELADO` é o único estado que o legado trata como absoluto.
    """
    if tramitacao == CANCELADA:
        return "CANCELADO"
    # Quando está programado para pagar mas ainda aguardando autoridade,
    # é AGUARDANDO_AUTORIZACAO (não ENVIADO_TESOURARIA que vem após autorizar)
    if tramitacao == AGUARDANDO_AUTORIDADE and pagamento == PROGRAMADA:
        return "AGUARDANDO_AUTORIZACAO"
    if pagamento in _LEGADO_PAGAMENTO:
        return _LEGADO_PAGAMENTO[pagamento]
    if fila == BLOQUEADA and tramitacao not in TERMINAIS:
        return "SUSPENSO"
    return _LEGADO_TRAMITACAO[tramitacao]
