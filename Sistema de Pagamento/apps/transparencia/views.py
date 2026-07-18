from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render

from apps.cadastros.models import OrgaoSecretaria
from apps.core.choices import StatusPedido
from apps.pagamentos.models import PedidoPagamento
from apps.relatorios.exports import response_csv

from .anonimizacao import mascarar_documento

STATUS_PUBLICOS = [StatusPedido.AUTORIZADO, StatusPedido.PAGO]


def _queryset_publico(request):
    """RF56 — dados pormenorizados dos pagamentos autorizados/efetuados."""
    pedidos = PedidoPagamento.objects.filter(status__in=STATUS_PUBLICOS).select_related(
        'credor', 'orgao', 'natureza'
    ).order_by('-vencimento')

    q = request.GET.get('q')
    if q:
        pedidos = pedidos.filter(Q(credor__nome__icontains=q) | Q(orgao__nome__icontains=q))
    orgao_id = request.GET.get('orgao')
    if orgao_id:
        pedidos = pedidos.filter(orgao_id=orgao_id)
    ano = request.GET.get('ano')
    if ano:
        pedidos = pedidos.filter(vencimento__year=ano)
    return pedidos


def _serializar_publico(pedido):
    """Nunca inclui dados bancários — apenas os campos exigidos pelo art. 48-A da LC 101/2000."""
    return {
        'protocolo': pedido.protocolo,
        'credor': pedido.credor.nome,
        'documento': mascarar_documento(pedido.credor),
        'valor': str(pedido.valor),
        'natureza': pedido.natureza.descricao,
        'orgao': pedido.orgao.nome,
        'vencimento': pedido.vencimento.isoformat(),
        'status': pedido.get_status_display(),
    }


def portal(request):
    """RF56 — portal público de acesso, sem necessidade de autenticação."""
    pedidos = _queryset_publico(request)
    paginator = Paginator(pedidos, 50)
    pagina = paginator.get_page(request.GET.get('page'))
    linhas = [_serializar_publico(p) for p in pagina.object_list]
    contexto = {
        'pagina': pagina,
        'linhas': linhas,
        'orgaos': OrgaoSecretaria.objects.filter(ativo=True),
        'filtros': request.GET,
    }
    return render(request, 'transparencia/portal.html', contexto)


def exportar_csv(request):
    """RF57 — dados em formato aberto (CSV)."""
    pedidos = _queryset_publico(request)
    headers = ['Protocolo', 'Credor', 'Documento', 'Valor', 'Natureza', 'Órgão', 'Vencimento', 'Status']
    linhas = [
        [d['protocolo'], d['credor'], d['documento'], d['valor'], d['natureza'], d['orgao'], d['vencimento'], d['status']]
        for d in (_serializar_publico(p) for p in pedidos)
    ]
    return response_csv('pagamentos_transparencia.csv', headers, linhas)


def exportar_json(request):
    """RF57 — dados em formato aberto (JSON)."""
    pedidos = _queryset_publico(request)
    return JsonResponse({'resultados': [_serializar_publico(p) for p in pedidos]})
