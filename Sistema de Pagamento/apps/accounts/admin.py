from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import PerfilUsuario, TentativaAcessoLog, Usuario


class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    inlines = [PerfilUsuarioInline]
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_active', 'must_change_password')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Informações pessoais', {'fields': ('first_name', 'last_name')}),
        ('Permissões', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Segurança', {'fields': ('must_change_password',)}),
        ('Datas', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )


@admin.register(TentativaAcessoLog)
class TentativaAcessoLogAdmin(admin.ModelAdmin):
    list_display = ('email', 'sucesso', 'ip_origem', 'criado_em')
    list_filter = ('sucesso',)
    search_fields = ('email',)
    ordering = ('-criado_em',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
