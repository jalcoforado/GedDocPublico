from django.urls import path

from . import views

app_name = 'transparencia'

urlpatterns = [
    path('', views.portal, name='portal'),
    path('exportar.csv', views.exportar_csv, name='exportar_csv'),
    path('exportar.json', views.exportar_json, name='exportar_json'),
]
