from django.contrib import admin

from .models import AnexoPedido, HistoricoStatusPedido, NotaEmpenhoReferencia, OrdemPagamento, PedidoPagamento


class AnexoInline(admin.TabularInline):
    model = AnexoPedido
    extra = 0


class HistoricoInline(admin.TabularInline):
    model = HistoricoStatusPedido
    extra = 0
    readonly_fields = ('status_anterior', 'status_novo', 'usuario', 'justificativa', 'ip_origem', 'criado_em')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PedidoPagamento)
class PedidoPagamentoAdmin(admin.ModelAdmin):
    list_display = ('protocolo', 'credor', 'orgao', 'valor', 'status', 'criticidade', 'vencimento')
    list_filter = ('status', 'criticidade', 'orgao')
    search_fields = ('protocolo', 'numero_ne', 'numero_nf', 'credor__nome')
    inlines = [AnexoInline, HistoricoInline]
    readonly_fields = ('protocolo',)


@admin.register(OrdemPagamento)
class OrdemPagamentoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'autorizador', 'valor_total', 'criado_em')
    search_fields = ('numero',)
    readonly_fields = ('numero',)


@admin.register(NotaEmpenhoReferencia)
class NotaEmpenhoReferenciaAdmin(admin.ModelAdmin):
    list_display = ('numero', 'orgao', 'exercicio', 'valor_empenhado', 'liquidado')
    list_filter = ('exercicio', 'liquidado', 'orgao')
    search_fields = ('numero',)
