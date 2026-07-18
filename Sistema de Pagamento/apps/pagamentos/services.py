from django.db import transaction
from django.utils import timezone

from apps.core.choices import StatusPedido
from apps.financeiro import services as financeiro_services

from .exceptions import (
    AlcadaExcedidaError,
    DocumentacaoObrigatoriaError,
    SaldoInsuficienteError,
    SegregacaoFuncoesError,
    TransicaoInvalidaError,
)
from .models import HistoricoStatusPedido, OrdemPagamento, PedidoPagamento
from .notifications import notificar_pendencia, notificar_usuario


def _registrar_historico(pedido, status_anterior, status_novo, usuario, justificativa='', ip_origem=None):
    HistoricoStatusPedido.objects.create(
        pedido=pedido,
        status_anterior=status_anterior,
        status_novo=status_novo,
        usuario=usuario,
        justificativa=justificativa,
        ip_origem=ip_origem,
    )


def _usuarios_ja_envolvidos(pedido):
    envolvidos = {pedido.solicitante_id}
    envolvidos.update(
        pedido.historico.exclude(usuario=None).values_list('usuario_id', flat=True)
    )
    return envolvidos


def _validar_segregacao(pedido, usuario):
    """
    RF64/RN M3 — nenhum usuário pode solicitar, aprovar, autorizar e
    executar o mesmo pedido. Administrador é a exceção expressamente
    parametrizada mencionada na regra de negócio.
    """
    perfil = getattr(usuario, 'perfil', None)
    if perfil and perfil.papel == 'ADMIN':
        return
    if usuario.id in _usuarios_ja_envolvidos(pedido):
        raise SegregacaoFuncoesError(
            'Segregação de funções: este usuário já atuou em uma etapa anterior deste pedido.'
        )


def _validar_status(pedido, *status_esperados):
    if pedido.status not in status_esperados:
        raise TransicaoInvalidaError(
            f'Transição inválida: pedido está em "{pedido.get_status_display()}".'
        )


def _limite_alcada(perfil, natureza):
    especifica = perfil.alcadas.filter(natureza=natureza).first()
    if especifica:
        return especifica.valor_maximo
    geral = perfil.alcadas.filter(natureza=None).first()
    if geral:
        return geral.valor_maximo
    return perfil.limite_autorizacao


def _validar_alcada(pedido, perfil):
    limite = _limite_alcada(perfil, pedido.natureza)
    if limite is not None and pedido.valor > limite:
        raise AlcadaExcedidaError(
            f'Valor de R$ {pedido.valor} excede a alçada de autorização de R$ {limite} deste perfil.'
        )


@transaction.atomic
def enviar_para_aprovacao(pedido, usuario):
    """RF12/RF14 — envia o pedido recém-criado para a fila do Secretário."""
    if pedido.enviado_para_aprovacao or pedido.status != StatusPedido.PENDENTE:
        raise TransicaoInvalidaError('Pedido já foi enviado ou não está mais pendente de envio.')
    if not pedido.exceto_ne_nf and not (pedido.numero_ne and pedido.numero_nf):
        raise DocumentacaoObrigatoriaError(
            'Número da Nota de Empenho (NE) e da Nota Fiscal (NF) são obrigatórios para envio à aprovação.'
        )
    pedido.enviado_para_aprovacao = True
    pedido.save(update_fields=['enviado_para_aprovacao'])
    _registrar_historico(pedido, pedido.status, pedido.status, usuario, 'Enviado para aprovação do Secretário.')
    notificar_pendencia(pedido, papel_destino='SECRETARIO', orgao=pedido.orgao)
    return pedido


@transaction.atomic
def aprovar_secretario(pedido, usuario, justificativa=''):
    _validar_status(pedido, StatusPedido.PENDENTE)
    if not pedido.enviado_para_aprovacao:
        raise TransicaoInvalidaError('Pedido ainda não foi enviado pelo solicitante.')
    _validar_segregacao(pedido, usuario)
    status_anterior = pedido.status
    pedido.status = StatusPedido.APROVADO_SECRETARIO
    pedido.save(update_fields=['status'])
    _registrar_historico(pedido, status_anterior, pedido.status, usuario, justificativa)
    notificar_pendencia(pedido, papel_destino='AUTORIZADOR')
    return pedido


@transaction.atomic
def devolver(pedido, usuario, justificativa):
    """RN M3 — devolução exige justificativa obrigatória e volta ao solicitante."""
    if not justificativa:
        raise DocumentacaoObrigatoriaError('Justificativa é obrigatória para devolução do pedido.')
    _validar_status(pedido, StatusPedido.PENDENTE, StatusPedido.APROVADO_SECRETARIO)
    status_anterior = pedido.status
    pedido.status = StatusPedido.DEVOLVIDO
    pedido.enviado_para_aprovacao = False
    pedido.save(update_fields=['status', 'enviado_para_aprovacao'])
    _registrar_historico(pedido, status_anterior, pedido.status, usuario, justificativa)
    notificar_usuario(pedido.solicitante, pedido, f'Seu pedido foi devolvido: {justificativa}')
    return pedido


@transaction.atomic
def rejeitar(pedido, usuario, justificativa):
    """RN M3 — rejeição exige justificativa obrigatória; status terminal."""
    if not justificativa:
        raise DocumentacaoObrigatoriaError('Justificativa é obrigatória para rejeição do pedido.')
    _validar_status(pedido, StatusPedido.PENDENTE, StatusPedido.APROVADO_SECRETARIO)
    status_anterior = pedido.status
    pedido.status = StatusPedido.REJEITADO
    pedido.save(update_fields=['status'])
    _registrar_historico(pedido, status_anterior, pedido.status, usuario, justificativa)
    notificar_usuario(pedido.solicitante, pedido, f'Seu pedido foi rejeitado: {justificativa}')
    return pedido


@transaction.atomic
def cancelar(pedido, usuario):
    """RF12 — cancelamento pelo próprio solicitante, apenas enquanto não enviado."""
    if not pedido.pode_editar:
        raise TransicaoInvalidaError('Pedido não pode mais ser cancelado pelo solicitante.')
    status_anterior = pedido.status
    pedido.status = StatusPedido.CANCELADO
    pedido.save(update_fields=['status'])
    _registrar_historico(pedido, status_anterior, pedido.status, usuario, 'Cancelado pelo solicitante.')
    return pedido


@transaction.atomic
def autorizar_lote(pedidos, usuario, ip_origem=None):
    """
    RF20-RF27 — autorização em lote pela Alta Gestão. Valida, para cada
    conta bancária envolvida, se o saldo disponível comporta a soma dos
    pedidos selecionados (RF25, bloqueante) e a alçada do autorizador
    (RF07) antes de confirmar qualquer autorização do lote.
    """
    pedidos = list(pedidos)
    if not pedidos:
        raise TransicaoInvalidaError('Nenhum pedido selecionado.')

    perfil = getattr(usuario, 'perfil', None)
    if perfil is None:
        raise TransicaoInvalidaError('Usuário sem perfil configurado.')

    for pedido in pedidos:
        _validar_status(pedido, StatusPedido.APROVADO_SECRETARIO)
        _validar_segregacao(pedido, usuario)
        _validar_alcada(pedido, perfil)

    totais_por_conta = {}
    for pedido in pedidos:
        totais_por_conta.setdefault(pedido.conta_bancaria_id, {'conta': pedido.conta_bancaria, 'total': 0})
        totais_por_conta[pedido.conta_bancaria_id]['total'] += pedido.valor

    for info in totais_por_conta.values():
        conta = info['conta']
        if info['total'] > conta.saldo_disponivel_efetivo:
            raise SaldoInsuficienteError(
                f'Saldo insuficiente na conta "{conta}": disponível R$ {conta.saldo_disponivel_efetivo}, '
                f'necessário R$ {info["total"]} para os pedidos selecionados.'
            )

    valor_total = sum(p.valor for p in pedidos)
    ordem = OrdemPagamento.objects.create(autorizador=usuario, valor_total=valor_total, ip_origem=ip_origem)
    ordem.pedidos.set(pedidos)

    for pedido in pedidos:
        status_anterior = pedido.status
        pedido.status = StatusPedido.AUTORIZADO
        pedido.save(update_fields=['status'])
        _registrar_historico(
            pedido, status_anterior, pedido.status, usuario,
            f'Autorizado via Ordem de Pagamento {ordem.numero}.', ip_origem=ip_origem,
        )
    notificar_pendencia(pedidos[0], papel_destino='TESOURARIA')
    return ordem


@transaction.atomic
def executar_pagamento(pedido, usuario, forma_pagamento, data_pagamento=None, comprovante=None):
    """RF29-RF31 — efetivação financeira do pagamento pela Tesouraria."""
    _validar_status(pedido, StatusPedido.AUTORIZADO)
    _validar_segregacao(pedido, usuario)

    status_anterior = pedido.status
    pedido.status = StatusPedido.PAGO
    pedido.forma_pagamento = forma_pagamento
    pedido.data_pagamento = data_pagamento or timezone.localdate()
    if comprovante is not None:
        pedido.comprovante_pagamento = comprovante
    pedido.save(update_fields=['status', 'forma_pagamento', 'data_pagamento', 'comprovante_pagamento'])

    financeiro_services.debitar_pagamento(pedido.conta_bancaria, pedido.valor, pedido, usuario)
    _registrar_historico(
        pedido, status_anterior, pedido.status, usuario,
        f'Pago via {pedido.get_forma_pagamento_display()}.',
    )
    return pedido


@transaction.atomic
def estornar_pagamento(pedido, usuario, justificativa):
    """
    RF32 — estorno de pagamento já baixado, preservando o histórico
    anterior (nenhum registro de HistoricoStatusPedido é alterado/apagado;
    apenas um novo evento é adicionado). O pedido retorna a "Autorizado"
    para permitir novo processamento.
    """
    if not justificativa:
        raise DocumentacaoObrigatoriaError('Justificativa é obrigatória para estorno de pagamento.')
    _validar_status(pedido, StatusPedido.PAGO)

    status_anterior = pedido.status
    pedido.status = StatusPedido.AUTORIZADO
    pedido.estornado = True
    pedido.justificativa_estorno = justificativa
    pedido.save(update_fields=['status', 'estornado', 'justificativa_estorno'])

    financeiro_services.estornar_pagamento(pedido.conta_bancaria, pedido.valor, pedido, usuario, justificativa)
    _registrar_historico(pedido, status_anterior, pedido.status, usuario, justificativa)
    return pedido


@transaction.atomic
def baixar_por_conciliacao(pedido, data_pagamento, usuario, observacao=''):
    """
    RF41/RF43 — baixa disparada pela conciliação bancária (automática ou
    confirmada manualmente pela Tesouraria), não pela execução direta do
    pagamento. Não exige forma_pagamento explícita: o meio de pagamento é
    o identificado no próprio extrato bancário.
    """
    _validar_status(pedido, StatusPedido.AUTORIZADO)

    status_anterior = pedido.status
    pedido.status = StatusPedido.PAGO
    pedido.data_pagamento = data_pagamento
    pedido.save(update_fields=['status', 'data_pagamento'])

    financeiro_services.debitar_por_conciliacao(pedido.conta_bancaria, pedido.valor, pedido, usuario)
    _registrar_historico(
        pedido, status_anterior, pedido.status, usuario,
        observacao or 'Baixa automática por conciliação bancária.',
    )
    return pedido
