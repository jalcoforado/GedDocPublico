from django.contrib import admin

from .models import LogAuditoria


@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('criado_em', 'usuario', 'acao', 'modelo', 'objeto_id', 'ip_origem')
    list_filter = ('acao', 'modelo')
    search_fields = ('objeto_repr', 'objeto_id')
    readonly_fields = [f.name for f in LogAuditoria._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
