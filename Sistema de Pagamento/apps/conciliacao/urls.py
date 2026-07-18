from django.urls import path

from . import views

app_name = 'conciliacao'

urlpatterns = [
    path('', views.lista_extratos, name='lista_extratos'),
    path('novo/', views.upload_extrato, name='upload_extrato'),
    path('<int:pk>/', views.detalhe_extrato, name='detalhe_extrato'),
    path('pendencias/', views.pendencias, name='pendencias'),
    path('lancamento/<int:pk>/vincular/', views.vincular_manual, name='vincular_manual'),
    path('lancamento/<int:pk>/ignorar/', views.ignorar, name='ignorar'),
]
