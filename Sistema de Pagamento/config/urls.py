from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.pagamentos.api import PedidoPagamentoViewSet, validar_nota_empenho

router = DefaultRouter()
router.register('pedidos', PedidoPagamentoViewSet, basename='api-pedidos')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('contas/', include('apps.accounts.urls')),
    path('cadastros/', include('apps.cadastros.urls')),
    path('pagamentos/', include('apps.pagamentos.urls')),
    path('financeiro/', include('apps.financeiro.urls')),
    path('conciliacao/', include('apps.conciliacao.urls')),
    path('auditoria/', include('apps.auditoria.urls')),
    path('relatorios/', include('apps.relatorios.urls')),
    path('transparencia/', include('apps.transparencia.urls')),
    path('api/', include(router.urls)),
    path('api/ne-validation/<str:numero>/', validar_nota_empenho, name='api-ne-validation'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
