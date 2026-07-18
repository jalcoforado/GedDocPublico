from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.cadastros.models import ContaBancaria
from apps.core.permissions import role_required

from . import services
from .forms import LancamentoManualForm


@role_required('TESOURARIA')
def lista_contas(request):
    contas = ContaBancaria.objects.filter(ativa=True)
    return render(request, 'financeiro/lista_contas.html', {'contas': contas})


@role_required('TESOURARIA')
def detalhe_conta(request, pk):
    conta = get_object_or_404(ContaBancaria, pk=pk)
    movimentacoes = conta.movimentacoes.select_related('pedido', 'responsavel').order_by('-criado_em')[:200]
    return render(request, 'financeiro/detalhe_conta.html', {'conta': conta, 'movimentacoes': movimentacoes})


@role_required('TESOURARIA')
def lancamento_manual(request, pk):
    """RF36 — lançamento manual de contingência, com responsável e justificativa obrigatórios."""
    conta = get_object_or_404(ContaBancaria, pk=pk)
    if request.method == 'POST':
        form = LancamentoManualForm(request.POST)
        if form.is_valid():
            services.lancamento_manual(
                conta, form.cleaned_data['valor'], request.user, form.cleaned_data['justificativa']
            )
            messages.success(request, 'Lançamento manual registrado.')
            return redirect('financeiro:detalhe_conta', pk=conta.pk)
    else:
        form = LancamentoManualForm()
    return render(request, 'financeiro/lancamento_manual_form.html', {'form': form, 'conta': conta})
