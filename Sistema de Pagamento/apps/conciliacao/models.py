from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class ExtratoBancario(TimeStampedModel):
    """RF38, RF46 — extrato bancário enviado/importado para uma conta e período."""

    class Formato(models.TextChoices):
        PDF = 'PDF', 'PDF (texto)'
        CSV = 'CSV', 'CSV'
        OPEN_FINANCE = 'OPEN_FINANCE', 'Open Finance (API)'

    class StatusProcessamento(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente de Processamento'
        PROCESSADO = 'PROCESSADO', 'Processado'
        ERRO = 'ERRO', 'Erro no Processamento'

    conta_bancaria = models.ForeignKey(
        'cadastros.ContaBancaria', on_delete=models.PROTECT, related_name='extratos'
    )
    arquivo = models.FileField(upload_to='extratos/%Y/%m/', blank=True, null=True)
    formato = models.CharField(max_length=15, choices=Formato.choices)
    periodo_inicio = models.DateField()
    periodo_fim = models.DateField()
    status_processamento = models.CharField(
        max_length=15, choices=StatusProcessamento.choices, default=StatusProcessamento.PENDENTE
    )
    erro_mensagem = models.TextField(blank=True)
    enviado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    processado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Extrato Bancário'
        verbose_name_plural = 'Extratos Bancários'
        ordering = ['-periodo_fim']

    def __str__(self):
        return f"{self.conta_bancaria} — {self.periodo_inicio} a {self.periodo_fim}"


class LancamentoExtrato(TimeStampedModel):
    """RF39 — lançamentos extraídos do extrato (data, histórico, valor, tipo, identificador)."""

    class Tipo(models.TextChoices):
        CREDITO = 'CREDITO', 'Crédito'
        DEBITO = 'DEBITO', 'Débito'

    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente de Conciliação'
        CONCILIADO_AUTOMATICO = 'CONCILIADO_AUTOMATICO', 'Conciliado Automaticamente'
        CONCILIADO_MANUAL = 'CONCILIADO_MANUAL', 'Conciliado Manualmente'
        IGNORADO = 'IGNORADO', 'Ignorado (não é pagamento a fornecedor)'

    extrato = models.ForeignKey(ExtratoBancario, on_delete=models.CASCADE, related_name='lancamentos')
    data = models.DateField()
    historico = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    identificador_transacao = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.PENDENTE)
    pedido_vinculado = models.ForeignKey(
        'pagamentos.PedidoPagamento', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lancamentos_conciliados',
    )

    class Meta:
        verbose_name = 'Lançamento de Extrato'
        verbose_name_plural = 'Lançamentos de Extrato'
        ordering = ['data']

    def __str__(self):
        return f"{self.data} — {self.historico} — R$ {self.valor} ({self.get_tipo_display()})"


class ConciliacaoLog(TimeStampedModel):
    """RF44 — histórico completo de conciliações, automáticas e manuais."""

    class Tipo(models.TextChoices):
        AUTOMATICA = 'AUTOMATICA', 'Automática'
        MANUAL = 'MANUAL', 'Manual'

    lancamento = models.ForeignKey(LancamentoExtrato, on_delete=models.CASCADE, related_name='logs')
    pedido = models.ForeignKey('pagamentos.PedidoPagamento', on_delete=models.CASCADE, related_name='logs_conciliacao')
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)

    class Meta:
        verbose_name = 'Log de Conciliação'
        verbose_name_plural = 'Logs de Conciliação'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.lancamento} ↔ {self.pedido.protocolo}"
