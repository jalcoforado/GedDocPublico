from django.urls import path

from . import views

app_name = 'pagamentos'

urlpatterns = [
    path('<int:pk>/', views.detalhe, name='detalhe'),

    path('solicitante/', views.solicitante_lista, name='solicitante_lista'),
    path('solicitante/novo/', views.solicitante_criar, name='solicitante_criar'),
    path('solicitante/<int:pk>/editar/', views.solicitante_editar, name='solicitante_editar'),
    path('solicitante/<int:pk>/anexar/', views.solicitante_anexar, name='solicitante_anexar'),
    path('solicitante/<int:pk>/enviar/', views.solicitante_enviar, name='solicitante_enviar'),
    path('solicitante/<int:pk>/cancelar/', views.solicitante_cancelar, name='solicitante_cancelar'),

    path('secretario/', views.secretario_fila, name='secretario_fila'),
    path('secretario/<int:pk>/aprovar/', views.secretario_aprovar, name='secretario_aprovar'),
    path('secretario/<int:pk>/devolver/', views.secretario_devolver, name='secretario_devolver'),
    path('secretario/<int:pk>/rejeitar/', views.secretario_rejeitar, name='secretario_rejeitar'),

    path('autorizador/', views.autorizador_painel, name='autorizador_painel'),
    path('autorizador/autorizar/', views.autorizador_autorizar, name='autorizador_autorizar'),
    path('ordem/<int:pk>/', views.ordem_detalhe, name='ordem_detalhe'),
    path('ordem/<int:pk>/pdf/', views.ordem_pdf, name='ordem_pdf'),

    path('tesouraria/', views.tesouraria_fila, name='tesouraria_fila'),
    path('tesouraria/<int:pk>/executar/', views.tesouraria_executar, name='tesouraria_executar'),
    path('tesouraria/<int:pk>/estornar/', views.tesouraria_estornar, name='tesouraria_estornar'),
]
