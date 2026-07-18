from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def home(request):
    """
    Landing page after login — links out to each module's queue based on
    the user's papel. Detailed KPIs live in apps.relatorios (M10); this
    page is the cross-module entry point.
    """
    perfil = getattr(request.user, 'perfil', None)
    return render(request, 'core/home.html', {'perfil': perfil})
