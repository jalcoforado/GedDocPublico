from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.permissions import role_required

from . import services
from .forms import UploadExtratoForm, VincularManualForm
from .models import ExtratoBancario, LancamentoExtrato


@role_required('TESOURARIA')
def lista_extratos(request):
    extratos = ExtratoBancario.objects.select_related('conta_bancaria').order_by('-periodo_fim')
    return render(request, 'conciliacao/lista_extratos.html', {'extratos': extratos})


@role_required('TESOURARIA')
def upload_extrato(request):
    if request.method == 'POST':
        form = UploadExtratoForm(request.POST, request.FILES)
        if form.is_valid():
            extrato = form.save(commit=False)
            extrato.enviado_por = request.user
            extrato.save()
            try:
                services.processar_extrato(extrato, request.user)
                messages.success(request, 'Extrato processado. Lançamentos com correspondência exata já foram baixados automaticamente.')
            except Exception as exc:
                messages.error(request, f'Falha ao processar o extrato: {exc}')
            return redirect('conciliacao:detalhe_extrato', pk=extrato.pk)
    else:
        form = UploadExtratoForm()
    return render(request, 'conciliacao/upload_extrato_form.html', {'form': form})


@role_required('TESOURARIA')
def detalhe_extrato(request, pk):
    extrato = get_object_or_404(ExtratoBancario, pk=pk)
    lancamentos = extrato.lancamentos.select_related('pedido_vinculado').order_by('data')
    return render(request, 'conciliacao/detalhe_extrato.html', {'extrato': extrato, 'lancamentos': lancamentos})


@role_required('TESOURARIA')
def pendencias(request):
    """RF42 — lançamentos sem correspondência automática, para tratamento manual."""
    lancamentos = LancamentoExtrato.objects.filter(
        status=LancamentoExtrato.Status.PENDENTE, tipo=LancamentoExtrato.Tipo.DEBITO
    ).select_related('extrato', 'extrato__conta_bancaria').order_by('data')
    return render(request, 'conciliacao/pendencias.html', {'lancamentos': lancamentos})


@role_required('TESOURARIA')
def vincular_manual(request, pk):
    lancamento = get_object_or_404(LancamentoExtrato, pk=pk)
    if request.method == 'POST':
        form = VincularManualForm(request.POST, conta_bancaria=lancamento.extrato.conta_bancaria)
        if form.is_valid():
            try:
                services.vincular_manualmente(lancamento, form.cleaned_data['pedido'], request.user)
                messages.success(request, 'Lançamento conciliado manualmente e pagamento baixado.')
                return redirect('conciliacao:pendencias')
            except ValueError as exc:
                messages.error(request, str(exc))
    else:
        form = VincularManualForm(conta_bancaria=lancamento.extrato.conta_bancaria)
    return render(request, 'conciliacao/vincular_manual_form.html', {'form': form, 'lancamento': lancamento})


@role_required('TESOURARIA')
def ignorar(request, pk):
    lancamento = get_object_or_404(LancamentoExtrato, pk=pk)
    if request.method == 'POST':
        services.ignorar_lancamento(lancamento)
        messages.success(request, 'Lançamento marcado como ignorado.')
    return redirect('conciliacao:pendencias')
