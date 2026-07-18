from .models import MovimentacaoConta


def registrar_movimentacao(conta_bancaria, valor, origem, responsavel, pedido=None, justificativa=''):
    """Cria um lançamento de crédito (+) ou débito (-) na conta (RF34)."""
    return MovimentacaoConta.objects.create(
        conta_bancaria=conta_bancaria,
        valor=valor,
        origem=origem,
        pedido=pedido,
        responsavel=responsavel,
        justificativa=justificativa,
    )


def debitar_pagamento(conta_bancaria, valor, pedido, responsavel):
    """RF30 — debita o valor pago do saldo da conta no momento da baixa."""
    return registrar_movimentacao(
        conta_bancaria, -abs(valor), MovimentacaoConta.Origem.PAGAMENTO, responsavel, pedido=pedido,
    )


def estornar_pagamento(conta_bancaria, valor, pedido, responsavel, justificativa):
    """RF32 — devolve o valor à conta em caso de estorno."""
    return registrar_movimentacao(
        conta_bancaria, abs(valor), MovimentacaoConta.Origem.ESTORNO, responsavel,
        pedido=pedido, justificativa=justificativa,
    )


def debitar_por_conciliacao(conta_bancaria, valor, pedido, responsavel):
    """RF41 — baixa automática/manual de conciliação bancária."""
    return registrar_movimentacao(
        conta_bancaria, -abs(valor), MovimentacaoConta.Origem.CONCILIACAO, responsavel, pedido=pedido,
    )


def lancamento_manual(conta_bancaria, valor, responsavel, justificativa):
    """RF36 — lançamento manual de contingência; justificativa é obrigatória."""
    if not justificativa:
        raise ValueError('Justificativa é obrigatória para lançamento manual de contingência.')
    return registrar_movimentacao(
        conta_bancaria, valor, MovimentacaoConta.Origem.AJUSTE_MANUAL, responsavel, justificativa=justificativa,
    )
