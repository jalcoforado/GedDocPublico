from django.contrib import admin

from .models import (
    AlcadaAutorizacao,
    ContaBancaria,
    Contrato,
    FonteRecursos,
    Fornecedor,
    NaturezaDespesa,
    OrgaoSecretaria,
)


@admin.register(OrgaoSecretaria)
class OrgaoSecretariaAdmin(admin.ModelAdmin):
    list_display = ('codigo_orcamentario', 'nome', 'unidade_gestora', 'responsavel', 'ativo')
    search_fields = ('nome', 'codigo_orcamentario')
    list_filter = ('ativo',)


@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cnpj_cpf', 'tipo_pessoa', 'situacao_cadastral')
    search_fields = ('nome', 'cnpj_cpf')
    list_filter = ('tipo_pessoa', 'situacao_cadastral')


@admin.register(FonteRecursos)
class FonteRecursosAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descricao')
    search_fields = ('codigo', 'descricao')


@admin.register(ContaBancaria)
class ContaBancariaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'banco', 'agencia', 'conta', 'fonte_recursos', 'grupo_despesa', 'ativa')
    list_filter = ('grupo_despesa', 'ativa', 'fonte_recursos')
    search_fields = ('nome', 'banco', 'conta')


@admin.register(NaturezaDespesa)
class NaturezaDespesaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descricao', 'criticidade_padrao', 'ativa')
    list_filter = ('criticidade_padrao', 'ativa')
    search_fields = ('codigo', 'descricao')


@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'fornecedor', 'orgao', 'valor_total', 'vigencia_inicio', 'vigencia_fim')
    search_fields = ('numero', 'fornecedor__nome')
    list_filter = ('orgao',)


@admin.register(AlcadaAutorizacao)
class AlcadaAutorizacaoAdmin(admin.ModelAdmin):
    list_display = ('perfil', 'natureza', 'valor_maximo')
    list_filter = ('natureza',)
