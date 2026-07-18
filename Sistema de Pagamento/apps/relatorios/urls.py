from django.urls import path

from . import views

app_name = 'relatorios'

urlpatterns = [
    path('', views.painel, name='painel'),
    path('exportar/<str:formato>/', views.exportar_pedidos, name='exportar_pedidos'),
    path('restos-a-pagar/', views.restos_a_pagar, name='restos_a_pagar'),
    path('gestao-fiscal/', views.gestao_fiscal, name='gestao_fiscal'),
]
