from django.contrib.auth import login as auth_login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import LoginForm, TrocaSenhaForm


class InstitucionalLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


class InstitucionalLogoutView(LogoutView):
    next_page = reverse_lazy('accounts:login')


@login_required
def trocar_senha(request):
    if request.method == 'POST':
        form = TrocaSenhaForm(request.user, request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.must_change_password = False
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Senha atualizada com sucesso.')
            return redirect('core:home')
    else:
        form = TrocaSenhaForm(request.user)
    return render(request, 'accounts/trocar_senha.html', {'form': form})
