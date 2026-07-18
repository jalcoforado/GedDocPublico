from django.contrib import admin

from .models import ConciliacaoLog, ExtratoBancario, LancamentoExtrato


class LancamentoInline(admin.TabularInline):
    model = LancamentoExtrato
    extra = 0
    readonly_fields = ('data', 'historico', 'valor', 'tipo', 'status', 'pedido_vinculado')
    can_delete = False


@admin.register(ExtratoBancario)
class ExtratoBancarioAdmin(admin.ModelAdmin):
    list_display = ('conta_bancaria', 'periodo_inicio', 'periodo_fim', 'formato', 'status_processamento')
    list_filter = ('status_processamento', 'formato', 'conta_bancaria')
    inlines = [LancamentoInline]


@admin.register(ConciliacaoLog)
class ConciliacaoLogAdmin(admin.ModelAdmin):
    list_display = ('lancamento', 'pedido', 'tipo', 'responsavel', 'criado_em')
    list_filter = ('tipo',)

    def has_change_permission(self, request, obj=None):
        return False
