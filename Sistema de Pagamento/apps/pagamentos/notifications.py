from django.core.mail import send_mail
from django.conf import settings


def notificar_pendencia(pedido, papel_destino, orgao=None):
    """
    RF19 — notifica por e-mail os responsáveis pela próxima etapa. O
    "alerta no Sistema" citado no requisito é atendido pela própria fila
    do perfil (pedidos pendentes ficam visíveis no painel do responsável).
    Backend de e-mail é console por padrão neste ambiente (ver settings).
    """
    from apps.accounts.models import PerfilUsuario

    destinatarios = PerfilUsuario.objects.filter(papel=papel_destino, ativo=True)
    if orgao is not None:
        destinatarios = destinatarios.filter(orgao=orgao)
    emails = list(destinatarios.values_list('usuario__email', flat=True))
    if not emails:
        return
    send_mail(
        subject=f"[Pagamentos Municipais] Pedido {pedido.protocolo} pendente",
        message=(
            f"O pedido {pedido.protocolo} ({pedido.credor}, R$ {pedido.valor}) "
            f"está pendente de sua ação no Sistema de Pagamentos Municipais."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=emails,
        fail_silently=True,
    )


def notificar_usuario(usuario, pedido, mensagem):
    if not usuario or not usuario.email:
        return
    send_mail(
        subject=f"[Pagamentos Municipais] Pedido {pedido.protocolo}",
        message=mensagem,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[usuario.email],
        fail_silently=True,
    )
