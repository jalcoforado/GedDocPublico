def perfil_usuario(request):
    perfil = getattr(getattr(request, 'user', None), 'perfil', None) if request.user.is_authenticated else None
    return {'perfil_usuario': perfil}
