from django import template

register = template.Library()

_CRITICIDADE_CLASSES = {
    'URGENTE': 'bg-danger',
    'ALTA': 'bg-warning text-dark',
    'MEDIA': 'bg-info text-dark',
    'BAIXA': 'bg-secondary',
}

_STATUS_CLASSES = {
    'PENDENTE': 'bg-secondary',
    'APROVADO_SECRETARIO': 'bg-info text-dark',
    'AUTORIZADO': 'bg-primary',
    'PAGO': 'bg-success',
    'DEVOLVIDO': 'bg-warning text-dark',
    'REJEITADO': 'bg-danger',
    'CANCELADO': 'bg-dark',
}


@register.filter
def criticidade_class(valor):
    return _CRITICIDADE_CLASSES.get(valor, 'bg-secondary')


@register.filter
def status_class(valor):
    return _STATUS_CLASSES.get(valor, 'bg-secondary')
