from django import forms


class LancamentoManualForm(forms.Form):
    valor = forms.DecimalField(
        max_digits=14, decimal_places=2,
        help_text='Use valor negativo para débito, positivo para crédito.',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )
    justificativa = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}))
