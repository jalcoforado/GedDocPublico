from django import forms

from apps.cadastros.models import ContaBancaria, Contrato, Fornecedor

from .models import AnexoPedido, PedidoPagamento


class PedidoPagamentoForm(forms.ModelForm):
    class Meta:
        model = PedidoPagamento
        fields = [
            'credor', 'natureza', 'contrato', 'conta_bancaria', 'valor',
            'numero_ne', 'numero_nf', 'exceto_ne_nf', 'vencimento', 'competencia',
            'criticidade', 'urgente', 'justificativa_urgencia',
        ]
        widgets = {
            'vencimento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'competencia': forms.TextInput(attrs={'placeholder': 'MM/AAAA', 'class': 'form-control'}),
            'justificativa_urgencia': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['credor'].queryset = Fornecedor.objects.all()
        self.fields['contrato'].queryset = Contrato.objects.all()
        self.fields['conta_bancaria'].queryset = ContaBancaria.objects.filter(ativa=True)
        for name, field in self.fields.items():
            if name not in ('exceto_ne_nf', 'urgente'):
                field.widget.attrs.setdefault('class', 'form-select' if isinstance(field.widget, forms.Select) else 'form-control')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('urgente') and not cleaned.get('justificativa_urgencia'):
            self.add_error('justificativa_urgencia', 'Justificativa obrigatória quando o pedido é marcado como urgente (RF13).')
        return cleaned


class AnexoPedidoForm(forms.ModelForm):
    class Meta:
        model = AnexoPedido
        fields = ['tipo', 'arquivo', 'servidor_responsavel']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'servidor_responsavel': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('tipo') == AnexoPedido.Tipo.ATESTO and not cleaned.get('servidor_responsavel'):
            self.add_error(
                'servidor_responsavel',
                'Identificação do servidor responsável é obrigatória para o termo de atesto.',
            )
        return cleaned


class JustificativaForm(forms.Form):
    justificativa = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}))


class ExecucaoPagamentoForm(forms.Form):
    forma_pagamento = forms.ChoiceField(
        choices=PedidoPagamento.FormaPagamento.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    data_pagamento = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    comprovante = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-control'}))
