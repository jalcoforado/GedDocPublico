from datetime import timedelta

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.utils import timezone

from .models import TentativaAcessoLog


class LockoutEmailBackend(ModelBackend):
    """
    Autentica por e-mail (USERNAME_FIELD) e aplica bloqueio temporário após
    N tentativas malsucedidas dentro de uma janela de tempo (RF65).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = (username or '').strip().lower()
        if not email:
            return None

        ip = _client_ip(request)

        if self._esta_bloqueado(email):
            return None

        user = super().authenticate(request, username=email, password=password, **kwargs)

        TentativaAcessoLog.objects.create(
            email=email, sucesso=user is not None, ip_origem=ip
        )
        return user

    def _esta_bloqueado(self, email):
        janela = timezone.now() - timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        tentativas_recentes = TentativaAcessoLog.objects.filter(
            email=email, criado_em__gte=janela
        ).order_by('-criado_em')[: settings.LOGIN_ATTEMPT_LIMIT]

        if len(tentativas_recentes) < settings.LOGIN_ATTEMPT_LIMIT:
            return False
        return all(not t.sucesso for t in tentativas_recentes)


def _client_ip(request):
    if request is None:
        return None
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
