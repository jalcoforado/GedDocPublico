from django.contrib.auth import get_user_model

from apps.core.permissions import role_required
from django.shortcuts import render

from .models import LogAuditoria

Usuario = get_user_model()


@role_required('CONTROLE_INTERNO')
def consulta(request):
    """RF60 — consulta da trilha de auditoria, com filtros por usuário, período e tipo de ação."""
    logs = LogAuditoria.objects.select_related('usuario').all()

    usuario_id = request.GET.get('usuario')
    acao = request.GET.get('acao')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    modelo = request.GET.get('modelo')

    if usuario_id:
        logs = logs.filter(usuario_id=usuario_id)
    if acao:
        logs = logs.filter(acao=acao)
    if data_inicio:
        logs = logs.filter(criado_em__date__gte=data_inicio)
    if data_fim:
        logs = logs.filter(criado_em__date__lte=data_fim)
    if modelo:
        logs = logs.filter(modelo=modelo)

    logs = logs[:500]

    contexto = {
        'logs': logs,
        'usuarios': Usuario.objects.filter(is_active=True).order_by('email'),
        'acoes': LogAuditoria.Acao.choices,
        'modelos': LogAuditoria.objects.order_by().values_list('modelo', flat=True).distinct(),
        'filtros': request.GET,
    }
    return render(request, 'auditoria/consulta.html', contexto)
