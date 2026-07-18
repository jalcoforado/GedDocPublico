from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.InstitucionalLoginView.as_view(), name='login'),
    path('logout/', views.InstitucionalLogoutView.as_view(), name='logout'),
    path('trocar-senha/', views.trocar_senha, name='trocar_senha'),
]
