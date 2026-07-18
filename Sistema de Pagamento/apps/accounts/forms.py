from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='E-mail institucional', widget=forms.EmailInput(
        attrs={'class': 'form-control', 'autofocus': True}
    ))
    password = forms.CharField(label='Senha', widget=forms.PasswordInput(
        attrs={'class': 'form-control'}
    ))

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': (
            'E-mail ou senha inválidos, ou conta temporariamente bloqueada '
            'após múltiplas tentativas malsucedidas.'
        ),
    }


class TrocaSenhaForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label='Nova senha', widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password2 = forms.CharField(
        label='Confirme a nova senha', widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
