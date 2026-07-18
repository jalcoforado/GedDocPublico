from django.conf import settings
from django.db import models

from apps.core.choices import Criticidade, StatusPedido
from apps.core.models import TimeStampedModel


def anexo_upload_path(instance, filename):
    return f"anexos/{instance.pedido.protocolo or instance.pedido_id}/{filename}"


class PedidoPagamento(TimeStampedModel):
    """
    Agregado central do sistema (M2/M3/M4/M5/M9) — representa um pedido de
    pagamento da solicitação até a baixa financeira. Todas as transições de
    status passam pela camada apps.pagamentos.services, nunca são feitas
    diretamente por views/admin, para garantir a validação das regras de
    negócio (segregação de funções, saldo, alçada).
    """

    class FormaPagamento(models.TextChoices):
        TED = 'TED', 'TED'
        PIX = 'PIX', 'PIX'
        BOLETO = 'BOLETO', 'Boleto'
        CHEQUE = 'CHEQUE', 'Cheque'

    protocolo = models.CharField(max_length=30, unique=True, editable=False, blank=True)  # RF11

    orgao = models.ForeignKey('cadastros.OrgaoSecretaria', on_delete=models.PROTECT, related_name='pedidos')
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='pedidos_solicitados'
    )
    credor = models.ForeignKey('cadastros.Fornecedor', on_delete=models.PROTECT, related_name='pedidos')
    natureza = models.ForeignKey('cadastros.NaturezaDespesa', on_delete=models.PROTECT, related_name='pedidos')
    contrato = models.ForeignKey(
        'cadastros.Contrato', on_delete=models.PROTECT, related_name='pedidos', null=True, blank=True
    )
    conta_bancaria = models.ForeignKey(
        'cadastros.ContaBancaria', on_delete=models.PROTECT, related_name='pedidos_vinculados'
    )

    valor = models.DecimalField(max_digits=14, decimal_places=2)
    numero_ne = models.CharField('Número da Nota de Empenho', max_length=40, blank=True)
    numero_nf = models.CharField('Número da Nota Fiscal', max_length=40, blank=True)
    exceto_ne_nf = models.BooleanField(
        'Dispensado de NE/NF (despesa de pequeno vulto)', default=False,
        help_text='Exceção cadastrada pelo Administrador — RN do módulo M2.',
    )

    vencimento = models.DateField()
    competencia = models.CharField(max_length=7, help_text='Formato MM/AAAA')

    criticidade = models.CharField(max_length=10, choices=Criticidade.choices, default=Criticidade.MEDIA)
    urgente = models.BooleanField(default=False)
    justificativa_urgencia = models.TextField(blank=True)  # RF13

    status = models.CharField(max_length=25, choices=StatusPedido.choices, default=StatusPedido.PENDENTE)
    enviado_para_aprovacao = models.BooleanField(default=False)  # RF12/RF14

    forma_pagamento = models.CharField(max_length=10, choices=FormaPagamento.choices, blank=True)
    data_pagamento = models.DateField(null=True, blank=True)
    comprovante_pagamento = models.FileField(upload_to='comprovantes/%Y/%m/', blank=True, null=True)

    estornado = models.BooleanField(default=False)
    justificativa_estorno = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Pedido de Pagamento'
        verbose_name_plural = 'Pedidos de Pagamento'
        ordering = ['-criticidade', 'vencimento']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['vencimento']),
            models.Index(fields=['orgao', 'status']),
        ]

    def __str__(self):
        return f"{self.protocolo or 'RASCUNHO'} — {self.credor} — R$ {self.valor}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and not self.protocolo:
            self.protocolo = f"PAG-{self.criado_em.year}-{self.pk:06d}"
            # .update() em vez de save() para não disparar um 2º ciclo de
            # signals de auditoria (post_save) para a mesma criação lógica.
            PedidoPagamento.objects.filter(pk=self.pk).update(protocolo=self.protocolo)

    @property
    def pode_editar(self):
        return not self.enviado_para_aprovacao and self.status == StatusPedido.PENDENTE


class AnexoPedido(TimeStampedModel):
    """RF09 — documentos digitais anexados ao pedido (NF, NE, comprovantes, atesto)."""

    class Tipo(models.TextChoices):
        NF = 'NF', 'Nota Fiscal'
        NE = 'NE', 'Nota de Empenho'
        COMPROVANTE = 'COMPROVANTE', 'Comprovante'
        ATESTO = 'ATESTO', 'Termo de Atesto de Recebimento'
        OUTRO = 'OUTRO', 'Outro'

    pedido = models.ForeignKey(PedidoPagamento, on_delete=models.CASCADE, related_name='anexos')
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    arquivo = models.FileField(upload_to=anexo_upload_path)
    servidor_responsavel = models.CharField(
        'Servidor responsável pelo atesto', max_length=150, blank=True,
        help_text='Obrigatório quando tipo = Termo de Atesto (RN do módulo M2).',
    )
    enviado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        verbose_name = 'Anexo do Pedido'
        verbose_name_plural = 'Anexos do Pedido'

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.pedido.protocolo}"


class HistoricoStatusPedido(models.Model):
    """
    Registro de toda transição de status (M3 SLA, M4 trilha de autorização,
    M12 auditoria). Nunca é editado ou apagado após criado.
    """

    pedido = models.ForeignKey(PedidoPagamento, on_delete=models.CASCADE, related_name='historico')
    status_anterior = models.CharField(max_length=25, choices=StatusPedido.choices, null=True, blank=True)
    status_novo = models.CharField(max_length=25, choices=StatusPedido.choices)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    justificativa = models.TextField(blank=True)
    ip_origem = models.GenericIPAddressField(null=True, blank=True)  # RF26
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Histórico de Status'
        verbose_name_plural = 'Históricos de Status'
        ordering = ['criado_em']

    def __str__(self):
        return f"{self.pedido.protocolo}: {self.status_anterior} → {self.status_novo}"


class OrdemPagamento(TimeStampedModel):
    """
    RF33 / RN M4 — documento formal correspondente ao despacho da
    autoridade competente (art. 64 da Lei nº 4.320/1964), gerado a cada
    autorização em lote e reemitível/exportável a qualquer momento.
    """

    numero = models.CharField(max_length=30, unique=True, editable=False, blank=True)
    autorizador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ordens_emitidas')
    pedidos = models.ManyToManyField(PedidoPagamento, related_name='ordens_pagamento')
    valor_total = models.DecimalField(max_digits=14, decimal_places=2)
    ip_origem = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'Ordem de Pagamento'
        verbose_name_plural = 'Ordens de Pagamento'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.numero} — R$ {self.valor_total}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and not self.numero:
            self.numero = f"OP-{self.criado_em.year}-{self.pk:06d}"
            OrdemPagamento.objects.filter(pk=self.pk).update(numero=self.numero)


class NotaEmpenhoReferencia(TimeStampedModel):
    """
    RNF07 — representa localmente o que uma integração real traria do
    sistema municipal de execução orçamentária/contábil (SIAFIC ou
    equivalente), para permitir a validação/cruzamento do número da NE
    informado no pedido (ver Seção 1.2 do documento de requisitos). Não é
    uma integração real — é o contrato de dados que a integração ocuparia.
    """

    numero = models.CharField(max_length=40, unique=True)
    orgao = models.ForeignKey('cadastros.OrgaoSecretaria', on_delete=models.CASCADE, related_name='notas_empenho')
    exercicio = models.PositiveIntegerField()
    valor_empenhado = models.DecimalField(max_digits=14, decimal_places=2)
    liquidado = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Nota de Empenho (referência externa)'
        verbose_name_plural = 'Notas de Empenho (referência externa)'

    def __str__(self):
        return f"NE {self.numero}/{self.exercicio}"
