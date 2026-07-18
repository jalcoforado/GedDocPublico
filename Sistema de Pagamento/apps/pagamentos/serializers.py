from rest_framework import serializers

from .models import NotaEmpenhoReferencia, PedidoPagamento


class PedidoPagamentoSerializer(serializers.ModelSerializer):
    credor_nome = serializers.CharField(source='credor.nome', read_only=True)
    orgao_nome = serializers.CharField(source='orgao.nome', read_only=True)
    natureza_descricao = serializers.CharField(source='natureza.descricao', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PedidoPagamento
        fields = [
            'id', 'protocolo', 'credor_nome', 'orgao_nome', 'natureza_descricao',
            'valor', 'numero_ne', 'numero_nf', 'vencimento', 'competencia',
            'criticidade', 'status', 'status_display', 'data_pagamento',
        ]
        read_only_fields = fields


class NotaEmpenhoReferenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotaEmpenhoReferencia
        fields = ['numero', 'exercicio', 'valor_empenhado', 'liquidado']
