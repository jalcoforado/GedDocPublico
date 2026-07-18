from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """
    View decorator enforcing RBAC by PerfilUsuario.papel (RF64/M13).
    Controle Interno and Administrador always pass, since they have
    cross-cutting read/manage access by design.
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            perfil = getattr(request.user, 'perfil', None)
            if perfil is None:
                raise PermissionDenied("Usuário sem perfil configurado.")
            if perfil.papel in roles or perfil.papel in ('CONTROLE_INTERNO', 'ADMIN'):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("Perfil sem permissão para esta ação.")

        return _wrapped

    return decorator


class RoleRequiredMixin:
    """Class-based view mixin equivalent to role_required."""

    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        from django.contrib.auth.views import redirect_to_login

        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        perfil = getattr(request.user, 'perfil', None)
        if perfil is None:
            raise PermissionDenied("Usuário sem perfil configurado.")
        if perfil.papel in self.allowed_roles or perfil.papel in ('CONTROLE_INTERNO', 'ADMIN'):
            return super().dispatch(request, *args, **kwargs)
        raise PermissionDenied("Perfil sem permissão para esta ação.")
