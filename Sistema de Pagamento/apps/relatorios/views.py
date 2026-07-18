from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.cadastros.models import ContaBancaria
from apps.core.choices import StatusPedido
from apps.core.permissions import role_required
from apps.pagamentos.models import PedidoPagamento

from .exports import response_csv, response_excel, response_pdf

STATUS_ABERTOS = [
    StatusPedido.PENDENTE, StatusPedido.APROVADO_SECRETARIO, StatusPedido.AUTORIZADO,
]


@login_required
def painel(request):
    """RF52 — indicadores gerenciais de despesas pendentes e saldo consolidado."""
    abertos = PedidoPagamento.objects.filter(status__in=STATUS_ABERTOS)

    por_orgao = abertos.values('orgao__nome').annotate(total=Count('id'), valor=Sum('valor')).order_by('-valor')
    por_natureza = abertos.values('natureza__descricao').annotate(total=Count('id'), valor=Sum('valor')).order_by('-valor')
    por_criticidade = abertos.values('criticidade').annotate(total=Count('id'), valor=Sum('valor')).order_by('criticidade')

    contas = ContaBancaria.objects.filter(ativa=True)
    saldo_total = sum((c.saldo_atual for c in contas), 0)
    comprometido_total = sum((c.saldo_comprometido for c in contas), 0)
    disponivel_total = sum((c.saldo_disponivel_efetivo for c in contas), 0)

    hoje = timezone.localdate()
    vencidos = abertos.filter(vencimento__lt=hoje).count()  # RF51
    proximos_vencimento = abertos.filter(vencimento__gte=hoje, vencimento__lte=hoje + timezone.timedelta(days=7)).count()

    contexto = {
        'por_orgao': list(por_orgao),
        'por_natureza': list(por_natureza),
        'por_criticidade': list(por_criticidade),
        'saldo_total': saldo_total,
        'comprometido_total': comprometido_total,
        'disponivel_total': disponivel_total,
        'vencidos': vencidos,
        'proximos_vencimento': proximos_vencimento,
        'total_pendentes': abertos.count(),
    }
    return render(request, 'relatorios/painel.html', contexto)


@role_required('AUTORIZADOR', 'TESOURARIA', 'CONTROLE_INTERNO')
def exportar_pedidos(request, formato):
    """RF53 — exportação de pedidos em PDF, Excel ou CSV."""
    pedidos = PedidoPagamento.objects.select_related('credor', 'orgao', 'natureza').order_by('-criado_em')

    status_filtro = request.GET.get('status')
    if status_filtro:
        pedidos = pedidos.filter(status=status_filtro)

    headers = ['Protocolo', 'Credor', 'Órgão', 'Natureza', 'Valor', 'Status', 'Vencimento']
    linhas = [
        [p.protocolo, p.credor.nome, p.orgao.nome, p.natureza.descricao, str(p.valor), p.get_status_display(), p.vencimento.strftime('%d/%m/%Y')]
        for p in pedidos
    ]

    if formato == 'csv':
        return response_csv('pedidos_pagamento.csv', headers, linhas)
    if formato == 'xlsx':
        return response_excel('pedidos_pagamento.xlsx', headers, linhas)
    if formato == 'pdf':
        return response_pdf('relatorios/pedidos_pdf.html', {'pedidos': pedidos}, 'pedidos_pagamento.pdf')
    from django.http import HttpResponseBadRequest
    return HttpResponseBadRequest('Formato inválido. Use csv, xlsx ou pdf.')


@role_required('CONTROLE_INTERNO', 'TESOURARIA')
def restos_a_pagar(request):
    """RF54 — Restos a Pagar processados e não processados (arts. 100-104 da Lei nº 4.320/1964)."""
    ano = int(request.GET.get('ano', timezone.localdate().year - 1))

    processados = PedidoPagamento.objects.filter(
        status=StatusPedido.PAGO, vencimento__year__lte=ano
    ).exclude(data_pagamento__year=ano).select_related('credor', 'orgao')
    nao_processados = PedidoPagamento.objects.filter(
        status=StatusPedido.AUTORIZADO, vencimento__year__lte=ano
    ).select_related('credor', 'orgao')

    contexto = {
        'ano': ano,
        'processados': processados,
        'nao_processados': nao_processados,
        'total_processados': processados.aggregate(total=Sum('valor'))['total'] or 0,
        'total_nao_processados': nao_processados.aggregate(total=Sum('valor'))['total'] or 0,
    }
    return render(request, 'relatorios/restos_a_pagar.html', contexto)


@role_required('CONTROLE_INTERNO', 'TESOURARIA')
def gestao_fiscal(request):
    """RF55 — dados consolidados compatíveis com o Relatório de Gestão Fiscal (arts. 54-55 da LC 101/2000)."""
    contas = ContaBancaria.objects.filter(ativa=True)
    disponibilidade_caixa = sum((c.saldo_disponivel_efetivo for c in contas), 0)

    ano_anterior = timezone.localdate().year - 1
    restos_nao_processados = PedidoPagamento.objects.filter(
        status=StatusPedido.AUTORIZADO, vencimento__year__lte=ano_anterior
    ).aggregate(total=Sum('valor'))['total'] or 0

    contexto = {
        'contas': contas,
        'disponibilidade_caixa': disponibilidade_caixa,
        'restos_nao_processados': restos_nao_processados,
        'ano_anterior': ano_anterior,
    }
    return render(request, 'relatorios/gestao_fiscal.html', contexto)
