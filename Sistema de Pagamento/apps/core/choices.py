from django.db import models


class Criticidade(models.TextChoices):
    """RF04, RF48 — classificação de criticidade de despesas/naturezas."""

    URGENTE = 'URGENTE', 'Urgente'
    ALTA = 'ALTA', 'Alta'
    MEDIA = 'MEDIA', 'Média'
    BAIXA = 'BAIXA', 'Baixa'


class StatusPedido(models.TextChoices):
    """RF49 — status do pedido de pagamento ao longo do fluxo."""

    PENDENTE = 'PENDENTE', 'Pendente'
    APROVADO_SECRETARIO = 'APROVADO_SECRETARIO', 'Aprovado pelo Secretário'
    AUTORIZADO = 'AUTORIZADO', 'Autorizado'
    PAGO = 'PAGO', 'Pago'
    DEVOLVIDO = 'DEVOLVIDO', 'Devolvido'
    REJEITADO = 'REJEITADO', 'Rejeitado'
    CANCELADO = 'CANCELADO', 'Cancelado'


class GrupoDespesa(models.TextChoices):
    """Grupo de financiamento/despesa usado para checar compatibilidade com a fonte de recursos."""

    PESSOAL = 'PESSOAL', 'Pessoal e Encargos Sociais'
    CUSTEIO = 'CUSTEIO', 'Outras Despesas Correntes (Custeio)'
    INVESTIMENTO = 'INVESTIMENTO', 'Investimentos'
    DIVIDA = 'DIVIDA', 'Amortização da Dívida'
    OUTRAS = 'OUTRAS', 'Outras Despesas de Capital'
