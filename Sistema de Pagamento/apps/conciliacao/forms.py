from django import forms

from .models import ExtratoBancario


class UploadExtratoForm(forms.ModelForm):
    class Meta:
        model = ExtratoBancario
        fields = ['conta_bancaria', 'formato', 'periodo_inicio', 'periodo_fim', 'arquivo']
        widgets = {
            'conta_bancaria': forms.Select(attrs={'class': 'form-select'}),
            'formato': forms.Select(attrs={'class': 'form-select'}),
            'periodo_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'periodo_fim': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'arquivo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class VincularManualForm(forms.Form):
    pedido = forms.ModelChoiceField(queryset=None, widget=forms.Select(attrs={'class': 'form-select'}))

    def __init__(self, *args, conta_bancaria=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.core.choices import StatusPedido
        from apps.pagamentos.models import PedidoPagamento

        qs = PedidoPagamento.objects.filter(status=StatusPedido.AUTORIZADO)
        if conta_bancaria is not None:
            qs = qs.filter(conta_bancaria=conta_bancaria)
        self.fields['pedido'].queryset = qs
