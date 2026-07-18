from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import NotaEmpenhoReferencia, PedidoPagamento
from .serializers import PedidoPagamentoSerializer


class PedidoPagamentoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    RNF07 — interoperabilidade via API/webservice. Somente leitura;
    pensado para consumo por sistemas externos autenticados (ex.:
    sistema de execução orçamentária e contábil do Município).
    """

    serializer_class = PedidoPagamentoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = PedidoPagamento.objects.select_related('credor', 'orgao', 'natureza').order_by('-criado_em')
        status_filtro = self.request.query_params.get('status')
        if status_filtro:
            qs = qs.filter(status=status_filtro)
        orgao_id = self.request.query_params.get('orgao')
        if orgao_id:
            qs = qs.filter(orgao_id=orgao_id)
        return qs


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def validar_nota_empenho(request, numero):
    """
    RNF07 — endpoint de validação/cruzamento de NE (Seção 1.2 do
    documento de requisitos). Consulta a tabela local que representa o
    que uma integração real traria do sistema contábil municipal.
    """
    try:
        ne = NotaEmpenhoReferencia.objects.get(numero=numero)
    except NotaEmpenhoReferencia.DoesNotExist:
        return Response({'numero': numero, 'existe': False})
    return Response({
        'numero': ne.numero,
        'existe': True,
        'exercicio': ne.exercicio,
        'orgao': ne.orgao.nome,
        'valor_empenhado': str(ne.valor_empenhado),
        'liquidado': ne.liquidado,
    })
