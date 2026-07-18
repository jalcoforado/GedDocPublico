from django.db import transaction
from django.utils import timezone

from apps.core.choices import StatusPedido
from apps.pagamentos import services as pagamentos_services
from apps.pagamentos.models import PedidoPagamento

from .matching import encontrar_correspondencia_exata
from .models import ConciliacaoLog, ExtratoBancario, LancamentoExtrato
from .parsers import get_parser


@transaction.atomic
def processar_extrato(extrato, usuario):
    """RF38/RF39 — lê o arquivo do extrato e cria os lançamentos (sem conciliar ainda)."""
    parser = get_parser(extrato.formato)
    try:
        dados = parser.parse(extrato.arquivo)
    except Exception as exc:  # captura falhas de parsing e registra no extrato
        extrato.status_processamento = ExtratoBancario.StatusProcessamento.ERRO
        extrato.erro_mensagem = str(exc)
        extrato.save(update_fields=['status_processamento', 'erro_mensagem'])
        raise

    for item in dados:
        LancamentoExtrato.objects.create(
            extrato=extrato,
            data=item['data'],
            historico=item['historico'],
            valor=item['valor'],
            tipo=item['tipo'],
            identificador_transacao=item.get('identificador_transacao', ''),
        )

    extrato.status_processamento = ExtratoBancario.StatusProcessamento.PROCESSADO
    extrato.processado_em = timezone.now()
    extrato.save(update_fields=['status_processamento', 'processado_em'])
    conciliar_automaticamente(extrato, usuario)
    return extrato


@transaction.atomic
def conciliar_automaticamente(extrato, usuario):
    """RF40/RF41 — tenta baixa automática para lançamentos de débito com correspondência exata."""
    candidatos = list(
        PedidoPagamento.objects.filter(
            status=StatusPedido.AUTORIZADO, conta_bancaria=extrato.conta_bancaria
        )
    )
    conciliados = 0
    for lancamento in extrato.lancamentos.filter(
        tipo=LancamentoExtrato.Tipo.DEBITO, status=LancamentoExtrato.Status.PENDENTE
    ):
        pedido = encontrar_correspondencia_exata(lancamento, candidatos)
        if pedido is None:
            continue
        pagamentos_services.baixar_por_conciliacao(pedido, lancamento.data, usuario)
        lancamento.status = LancamentoExtrato.Status.CONCILIADO_AUTOMATICO
        lancamento.pedido_vinculado = pedido
        lancamento.save(update_fields=['status', 'pedido_vinculado'])
        ConciliacaoLog.objects.create(
            lancamento=lancamento, pedido=pedido, tipo=ConciliacaoLog.Tipo.AUTOMATICA, responsavel=None,
        )
        candidatos.remove(pedido)
        conciliados += 1
    return conciliados


@transaction.atomic
def vincular_manualmente(lancamento, pedido, usuario):
    """RF43 — vínculo manual pela Tesouraria em caso de divergência (ex.: parcelas, centavos)."""
    if lancamento.status != LancamentoExtrato.Status.PENDENTE:
        raise ValueError('Lançamento já foi conciliado.')
    pagamentos_services.baixar_por_conciliacao(
        pedido, lancamento.data, usuario, observacao=f'Vinculado manualmente ao lançamento "{lancamento.historico}".'
    )
    lancamento.status = LancamentoExtrato.Status.CONCILIADO_MANUAL
    lancamento.pedido_vinculado = pedido
    lancamento.save(update_fields=['status', 'pedido_vinculado'])
    ConciliacaoLog.objects.create(
        lancamento=lancamento, pedido=pedido, tipo=ConciliacaoLog.Tipo.MANUAL, responsavel=usuario,
    )
    return lancamento


def ignorar_lancamento(lancamento):
    """Marca um lançamento do extrato como não correspondente a um pagamento a fornecedor."""
    lancamento.status = LancamentoExtrato.Status.IGNORADO
    lancamento.save(update_fields=['status'])
    return lancamento
