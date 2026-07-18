from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class MovimentacaoConta(TimeStampedModel):
    """RF34 — créditos e débitos de cada conta bancária."""

    class Origem(models.TextChoices):
        SALDO_INICIAL = 'SALDO_INICIAL', 'Saldo Inicial'
        PAGAMENTO = 'PAGAMENTO', 'Baixa de Pagamento'
        ESTORNO = 'ESTORNO', 'Estorno de Pagamento'
        CONCILIACAO = 'CONCILIACAO', 'Baixa por Conciliação Bancária'
        AJUSTE_MANUAL = 'AJUSTE_MANUAL', 'Lançamento Manual (Contingência)'

    conta_bancaria = models.ForeignKey(
        'cadastros.ContaBancaria', on_delete=models.PROTECT, related_name='movimentacoes'
    )
    valor = models.DecimalField(
        max_digits=14, decimal_places=2,
        help_text='Positivo para crédito, negativo para débito.',
    )
    origem = models.CharField(max_length=20, choices=Origem.choices)
    pedido = models.ForeignKey(
        'pagamentos.PedidoPagamento', on_delete=models.PROTECT,
        related_name='movimentacoes', null=True, blank=True,
    )
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    justificativa = models.CharField(max_length=255, blank=True)  # obrigatória para AJUSTE_MANUAL (RF36)

    class Meta:
        verbose_name = 'Movimentação de Conta'
        verbose_name_plural = 'Movimentações de Conta'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.conta_bancaria} — R$ {self.valor} ({self.get_origem_display()})"
