"""Catálogo formal dos indicadores financeiros do módulo Despesa (§12 do brief).

**Este arquivo é a fonte única das definições.** A tela
(`/m/pagamentos/catalogo`) lê daqui pela API; o documento de plano aponta para
cá em vez de repetir o texto. Definição escrita em dois lugares vira duas
definições em algumas semanas, e aí o painel afirma uma coisa e a documentação
afirma outra — exatamente a discussão que um catálogo existe para encerrar.

O catálogo tem uma segunda função, tão importante quanto definir o que existe:
**declarar o que NÃO existe.** Seis conceitos que o brief pede estão aqui com
`disponivel=False` e o motivo. Um gestor que procura "execução orçamentária" e
não acha nada conclui que esqueceram; um que encontra a ficha dizendo "não há
dotação cadastrada no sistema" sabe o que falta e pode pedir. A omissão
silenciosa é que engana.

Nada aqui toca banco: é domínio puro, do mesmo jeito que
`pagamentos_estados.py`. Dá para ler e conferir sem subir nada.
"""
from __future__ import annotations

from ..schemas.pagamentos import IndicadorCatalogo

# Periodicidades usadas; todas as agregações do módulo são calculadas na hora
# da consulta, não materializadas — por isso "tempo real" é o padrão.
_AGORA = "Calculado no momento da consulta"

CATALOGO: tuple[IndicadorCatalogo, ...] = (
    # ------------------------------------------------------------ saldos
    IndicadorCatalogo(
        codigo="saldo_bancario", nome="Saldo bancário", grupo="Saldos",
        definicao="O dinheiro que está na conta, segundo os lançamentos registrados no Aprimora.",
        formula="saldo_inicial da conta + Σ entradas − Σ saídas (movimentações não excluídas)",
        fonte="pagamentos.conta_bancaria.saldo_inicial e pagamentos.movimentacao_conta",
        granularidade="Por conta bancária; somável por tenant",
        periodicidade=_AGORA,
        restricoes="Reflete o que foi lançado aqui, não o extrato do banco. Enquanto não houver "
                   "conciliação do dia, pode estar atrás do saldo real.",
        nao_confundir="Saldo conciliado (só o que foi conferido contra o extrato) e disponível "
                      "(que desconta compromissos).",
        disponivel=True),
    IndicadorCatalogo(
        codigo="saldo_conciliado", nome="Saldo conciliado", grupo="Saldos",
        definicao="A parte do saldo que já foi conferida contra o extrato do banco.",
        formula="saldo_inicial + Σ movimentações que têm baixa de conciliação vigente",
        fonte="pagamentos.conciliacao ligada a pagamentos.movimentacao_conta",
        granularidade="Por conta bancária",
        periodicidade=_AGORA,
        restricoes="Conciliação desfeita não conta (ela fica com excluido=true e sai da soma). "
                   "Sem nenhum extrato importado, reflete apenas o saldo inicial.",
        nao_confundir="Saldo bancário, que inclui lançamentos ainda não conferidos.",
        disponivel=True),
    IndicadorCatalogo(
        codigo="saldo_bloqueado", nome="Saldo bloqueado", grupo="Saldos",
        definicao="Dinheiro que está na conta mas foi administrativamente separado, e por isso "
                  "não pode ser usado para pagar despesa comum.",
        formula="Σ dos bloqueios ATIVOS cujo período de vigência inclui a data de hoje",
        fonte="pagamentos.bloqueio_saldo",
        granularidade="Por conta bancária",
        periodicidade=_AGORA,
        restricoes="É bloqueio registrado no Aprimora por decisão da prefeitura — não é bloqueio "
                   "judicial informado pelo banco, que o sistema não recebe.",
        nao_confundir="Comprometido, que é obrigação assumida, não dinheiro separado.",
        disponivel=True),
    IndicadorCatalogo(
        codigo="saldo_contabil", nome="Saldo contábil", grupo="Saldos",
        definicao="Saldo apurado pela contabilidade do município, segundo as normas contábeis "
                  "aplicadas ao setor público.",
        formula="—",
        fonte="Sistema contábil do município",
        granularidade="—", periodicidade="—",
        restricoes="O Aprimora ENVIA eventos para a contabilidade (export CSV e API M2M), mas "
                   "não recebe o saldo apurado de volta. Não há, hoje, saldo contábil no sistema.",
        nao_confundir="Saldo bancário, que é o movimento de caixa registrado aqui.",
        disponivel=False),

    # ------------------------------------------------------ disponibilidade
    IndicadorCatalogo(
        codigo="disponibilidade_financeira", nome="Disponibilidade financeira", grupo="Disponibilidade",
        definicao="Quanto da conta está realmente livre para assumir nova despesa, depois de "
                  "descontar o que já foi assumido e o que está bloqueado.",
        formula="saldo bancário − comprometido − bloqueado",
        fonte="Derivado (pagamentos_caixa.saldo_conta)",
        granularidade="Por conta bancária; somável, com ressalva",
        periodicidade=_AGORA,
        restricoes="Somar o disponível de várias contas NÃO diz quanto a prefeitura pode gastar "
                   "livremente: cada conta responde a uma fonte, e recurso vinculado só paga a "
                   "finalidade dele. Pode ser negativo — ver Insuficiência.",
        nao_confundir="Disponibilidade orçamentária, que é sobre dotação e não existe aqui.",
        disponivel=True),
    IndicadorCatalogo(
        codigo="disponibilidade_orcamentaria", nome="Disponibilidade orçamentária", grupo="Disponibilidade",
        definicao="Quanto ainda resta da dotação autorizada para aquela despesa no exercício.",
        formula="dotação atualizada − empenhado",
        fonte="pagamentos.dotacao + pagamentos.credito_adicional + debito.valor_empenhado",
        granularidade="Por dotação (unidade, função, subfunção, programa, ação, natureza, fonte)",
        periodicidade=_AGORA,
        restricoes="Só conta despesa VINCULADA a uma dotação e com retorno de empenho do sistema "
                   "financeiro. Despesa sem dotação não entra, e a tela informa quantas são — "
                   "ratear seria inventar. Ter dotação não é ter dinheiro em conta.",
        nao_confundir="Disponibilidade financeira, que é sobre dinheiro em conta.",
        disponivel=True),
    IndicadorCatalogo(
        codigo="dotacao_atualizada", nome="Dotação atualizada", grupo="Disponibilidade",
        definicao="A dotação do exercício depois dos créditos adicionais e das anulações.",
        formula="valor inicial + Σ (suplementar, especial, extraordinário) − Σ anulações",
        fonte="pagamentos.dotacao.valor_inicial e pagamentos.credito_adicional",
        granularidade="Por dotação; somável por exercício",
        periodicidade=_AGORA,
        restricoes="É DERIVADA, não uma coluna: somada na hora a partir dos créditos. Todo "
                   "crédito exige o ato (lei ou decreto) que o autorizou.",
        nao_confundir="Dotação inicial, que é a da lei orçamentária antes dos créditos.",
        disponivel=True),
    IndicadorCatalogo(
        codigo="execucao_orcamentaria", nome="Execução orçamentária", grupo="Disponibilidade",
        definicao="Quanto da dotação já foi comprometida por empenho.",
        formula="empenhado ÷ dotação atualizada",
        fonte="Derivado (pagamentos_orcamento.execucao_orcamentaria)",
        granularidade="Por dotação e consolidado por exercício",
        periodicidade=_AGORA,
        restricoes="Execução baixa pode significar “gastou pouco” OU “o retorno de empenho do "
                   "sistema financeiro ainda não chegou” — as duas leituras pedem ações opostas, "
                   "por isso o número vem acompanhado da contagem de despesas sem retorno.",
        nao_confundir="Despesa paga, que é execução FINANCEIRA e não orçamentária.",
        disponivel=True),
    IndicadorCatalogo(
        codigo="insuficiencia", nome="Insuficiência", grupo="Disponibilidade",
        definicao="Quanto das obrigações de uma conta não tem dinheiro que as cubra.",
        formula="max(0, comprometido + bloqueado − saldo bancário)",
        fonte="Derivado",
        granularidade="Por conta bancária",
        periodicidade=_AGORA,
        restricoes="Mede obrigações já assumidas contra o caixa de hoje. Não considera entrada "
                   "futura, porque o sistema não tem módulo de receita.",
        nao_confundir="Saldo negativo em banco, que seria o extrato no vermelho.",
        disponivel=True),
    IndicadorCatalogo(
        codigo="recursos_vinculados", nome="Recursos vinculados", grupo="Disponibilidade",
        definicao="Recurso que só pode custear a finalidade para a qual foi transferido ou "
                  "arrecadado (FUNDEB, saúde, convênio).",
        formula="Regra, não soma: cada conta pertence a uma fonte, e a autorização só oferece "
                "contas da fonte do empenho da despesa",
        fonte="pagamentos.fonte_recursos (codigo, tipo_vinculacao) ligada à conta bancária",
        granularidade="Por fonte de recursos",
        periodicidade=_AGORA,
        restricoes="PARCIAL: a REGRA está implementada e é obrigatória (só contas da fonte do "
                   "empenho pagam a despesa), mas a MEDIDA não existe — a coluna tipo_vinculacao "
                   "costuma estar vazia, e enquanto estiver o sistema não consegue dizer quanto "
                   "do disponível é livre e quanto é vinculado.",
        nao_confundir="Saldo bloqueado, que é separação administrativa dentro de uma conta.",
        disponivel=True),

    # -------------------------------------------------------- compromissos
    IndicadorCatalogo(
        codigo="comprometido", nome="Comprometido", grupo="Compromissos",
        definicao="O que já foi autorizado e ainda não foi pago — dinheiro que tem destino certo.",
        formula="Σ das parcelas em aberto (A_PAGAR ou LIBERADA) de despesas AUTORIZADAS e ainda "
                "não pagas nem conciliadas, pela conta pagadora reservada",
        fonte="pagamentos.parcela + pagamentos.debito",
        granularidade="Por conta bancária",
        periodicidade=_AGORA,
        restricoes="Conta SALDO DE PARCELA, uma vez só. Não soma autorizado + empenhado + "
                   "liquidado: uma mesma despesa está nos três estados ao mesmo tempo, e somá-los "
                   "triplicaria a obrigação.",
        nao_confundir="Valor a autorizar, que ainda depende de decisão.",
        disponivel=True),
    IndicadorCatalogo(
        codigo="valor_a_autorizar", nome="Valor a autorizar", grupo="Compromissos",
        definicao="Despesas que aguardam a decisão do ordenador.",
        formula="Σ valor_total das despesas em AGUARDANDO_AUTORIDADE",
        fonte="pagamentos.debito",
        granularidade="Por fonte de recursos (é a fonte que decide se cabe)",
        periodicidade=_AGORA,
        restricoes="Ainda não é obrigação: pode ser indeferido. Comparar com o disponível TOTAL "
                   "engana — a fonte do empenho é vinculante, então o que decide é o disponível "
                   "da fonte.",
        nao_confundir="Comprometido, que já passou pela autorização.",
        disponivel=True),
    IndicadorCatalogo(
        codigo="restos_a_pagar", nome="Restos a pagar", grupo="Compromissos",
        definicao="Despesa empenhada num exercício e não paga até 31 de dezembro, que passa para "
                  "o exercício seguinte.",
        formula="—", fonte="—", granularidade="Por exercício", periodicidade="—",
        restricoes="AINDA NÃO EXISTE. A despesa passou a ter exercício (migration 0146), então o "
                   "conceito ficou possível — falta o processo de virada de exercício, que é "
                   "outra fatia.",
        nao_confundir="Parcelas vencidas, que é atraso dentro do mesmo período.",
        disponivel=False),

    # ------------------------------------------------------------- o rito
    IndicadorCatalogo(
        codigo="solicitacao", nome="Solicitação de despesa", grupo="Rito da despesa",
        definicao="O pedido de pagamento, aberto pela unidade e ainda em tramitação.",
        formula="Despesa em RASCUNHO, AGUARDANDO_GESTOR, AGUARDANDO_VALIDACAO ou AGUARDANDO_AUTORIDADE",
        fonte="pagamentos.debito.situacao_tramitacao",
        granularidade="Por despesa", periodicidade=_AGORA,
        restricoes="Não reserva dinheiro nenhum e não entra no comprometido.",
        nao_confundir="Autorização, que é o ato do ordenador.",
        disponivel=True),
    IndicadorCatalogo(
        codigo="autorizacao", nome="Autorização administrativa", grupo="Rito da despesa",
        definicao="O ato do ordenador que autoriza a despesa e reserva a conta pagadora.",
        formula="Despesa em AUTORIZADA",
        fonte="pagamentos.debito.situacao_tramitacao + id_conta_pagadora",
        granularidade="Por despesa", periodicidade=_AGORA,
        restricoes="A conta pagadora é gravada aqui e é imutável depois. A partir deste ponto a "
                   "despesa entra no comprometido da conta.",
        nao_confundir="Reserva orçamentária — ver a ficha dela.",
        disponivel=True),
    IndicadorCatalogo(
        codigo="reserva_orcamentaria", nome="Reserva orçamentária", grupo="Rito da despesa",
        definicao="Bloqueio prévio de parte da dotação, antes do empenho, para garantir que o "
                  "crédito não seja consumido por outra despesa.",
        formula="—", fonte="Sistema orçamentário", granularidade="Por dotação", periodicidade="—",
        restricoes="NÃO EXISTE no Aprimora, mesmo com o orçamento implantado: reservar dotação é "
                   "um rito a mais, com ato próprio e cancelamento. ATENÇÃO: o módulo usa a "
                   "palavra “reserva” para outra "
                   "coisa — a reserva FINANCEIRA na conta pagadora, feita na autorização. São "
                   "conceitos diferentes: um prende dotação, o outro prende dinheiro.",
        nao_confundir="A reserva da conta pagadora, que é financeira e existe.",
        disponivel=False),
    IndicadorCatalogo(
        codigo="empenho", nome="Empenho", grupo="Rito da despesa",
        definicao="O ato que cria a obrigação de pagar e consome a dotação orçamentária.",
        formula="Σ valor_empenhado das despesas que receberam retorno do sistema financeiro",
        fonte="pagamentos.debito.numero_ne e valor_empenhado",
        granularidade="Por despesa", periodicidade="Quando o sistema financeiro devolve",
        restricoes="PARCIAL: o número do empenho é informado na solicitação; o VALOR só existe "
                   "quando o sistema financeiro o devolve pela API (campo revisado=true). "
                   "Despesa sem retorno tem valor nulo, que significa “ainda não voltou”, e não "
                   "zero. O empenho NÃO entra no cálculo de saldo: o comprometido é do que foi "
                   "solicitado e autorizado.",
        nao_confundir="Comprometido, que é financeiro e não orçamentário.",
        disponivel=True),
    IndicadorCatalogo(
        codigo="liquidacao", nome="Liquidação", grupo="Rito da despesa",
        definicao="A verificação de que o serviço foi prestado ou o bem entregue, que torna a "
                  "despesa exigível.",
        formula="Despesas com liquidacao_confirmada; valor em valor_liquidado quando houver retorno",
        fonte="pagamentos.debito.liquidacao_confirmada, data_liquidacao, valor_liquidado",
        granularidade="Por despesa", periodicidade=_AGORA,
        restricoes="PARCIAL: no rito é um marco (sim/não) e pré-requisito para autorizar; o valor "
                   "vem do retorno do sistema financeiro. Liquidação PARCIAL não é representável "
                   "— o campo guarda um valor só, o último informado.",
        nao_confundir="Pagamento, que é a saída do dinheiro.",
        disponivel=True),
    IndicadorCatalogo(
        codigo="ordem_pagamento", nome="Ordem de pagamento", grupo="Rito da despesa",
        definicao="O documento gerado na autorização, que manda a tesouraria pagar.",
        formula="Uma OP por fonte autorizada no mesmo ato",
        fonte="pagamentos.ordem_pagamento",
        granularidade="Por ordem", periodicidade=_AGORA,
        restricoes="Agrupa despesas da MESMA fonte: a fonte é vinculante, então não há OP "
                   "misturando recursos de finalidades diferentes.",
        nao_confundir="Pagamento, que é a baixa efetiva.",
        disponivel=True),
    IndicadorCatalogo(
        codigo="pagamento", nome="Pagamento", grupo="Rito da despesa",
        definicao="A saída efetiva do dinheiro da conta.",
        formula="Σ movimentações de SAÍDA com origem PAGAMENTO",
        fonte="pagamentos.movimentacao_conta",
        granularidade="Por conta, por despesa, por período",
        periodicidade=_AGORA,
        restricoes="É a MEDIDA ÚNICA de todos os gráficos de “despesa por …” do painel "
                   "(secretaria, natureza, fonte, fornecedor, contrato). Duas medidas no mesmo "
                   "painel fariam dois gráficos discordarem sobre quanto se gastou.",
        nao_confundir="Liberação para a tesouraria, que ainda não moveu dinheiro.",
        disponivel=True),
)

GRUPOS = ("Saldos", "Disponibilidade", "Compromissos", "Rito da despesa")


def listar() -> list[IndicadorCatalogo]:
    """Catálogo na ordem dos grupos, com os indisponíveis por último em cada um.

    Os que não existem ficam no fim do próprio grupo, e não numa seção
    separada: quem procura “disponibilidade orçamentária” acha a ficha ao lado
    da financeira, que é onde a confusão acontece.
    """
    ordem = {g: i for i, g in enumerate(GRUPOS)}
    return sorted(CATALOGO, key=lambda i: (ordem.get(i.grupo, 99), not i.disponivel, i.nome))
