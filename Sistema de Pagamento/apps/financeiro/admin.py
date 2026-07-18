from django.contrib import admin

from .models import MovimentacaoConta


@admin.register(MovimentacaoConta)
class MovimentacaoContaAdmin(admin.ModelAdmin):
    list_display = ('conta_bancaria', 'valor', 'origem', 'pedido', 'responsavel', 'criado_em')
    list_filter = ('origem', 'conta_bancaria')
    search_fields = ('conta_bancaria__nome', 'pedido__protocolo')

    def has_change_permission(self, request, obj=None):
        return False
