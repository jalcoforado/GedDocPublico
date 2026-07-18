from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """RF63 — exige a troca da senha padrão no primeiro acesso."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        exempt_paths = (
            reverse('accounts:trocar_senha'),
            reverse('accounts:logout'),
        )
        if (
            user is not None
            and user.is_authenticated
            and getattr(user, 'must_change_password', False)
            and request.path not in exempt_paths
            and not request.path.startswith('/static/')
            and not request.path.startswith('/admin/')
        ):
            return redirect(reverse('accounts:trocar_senha'))
        return self.get_response(request)
