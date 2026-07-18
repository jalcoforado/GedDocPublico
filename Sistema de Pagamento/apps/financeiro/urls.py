from django.urls import path

from . import views

app_name = 'financeiro'

urlpatterns = [
    path('', views.lista_contas, name='lista_contas'),
    path('<int:pk>/', views.detalhe_conta, name='detalhe_conta'),
    path('<int:pk>/lancamento-manual/', views.lancamento_manual, name='lancamento_manual'),
]
