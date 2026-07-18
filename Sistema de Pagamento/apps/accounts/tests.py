from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import PerfilUsuario

Usuario = get_user_model()


class LoginLockoutTests(TestCase):
    """RF65 — bloqueio temporário após tentativas malsucedidas de login."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='u1', email='u1@teste.com', password='SenhaCorreta1')

    def test_bloqueio_apos_exceder_limite_de_tentativas(self):
        url = reverse('accounts:login')
        for _ in range(settings.LOGIN_ATTEMPT_LIMIT):
            self.client.post(url, {'username': 'u1@teste.com', 'password': 'senha-errada'})

        # mesmo com a senha correta, o usuário deve estar temporariamente bloqueado
        response = self.client.post(url, {'username': 'u1@teste.com', 'password': 'SenhaCorreta1'}, follow=True)
        self.assertFalse(response.context['user'].is_authenticated)

    def test_login_com_senha_correta_funciona_normalmente(self):
        url = reverse('accounts:login')
        response = self.client.post(url, {'username': 'u1@teste.com', 'password': 'SenhaCorreta1'}, follow=True)
        self.assertTrue(response.context['user'].is_authenticated)


class TrocaSenhaObrigatoriaTests(TestCase):
    """RF63 — exige troca de senha padrão no primeiro acesso."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='novo', email='novo@teste.com', password='SenhaPadrao1', must_change_password=True,
        )
        PerfilUsuario.objects.create(usuario=self.usuario, papel='SOLICITANTE')

    def test_usuario_e_redirecionado_para_troca_de_senha(self):
        self.client.login(username='novo@teste.com', password='SenhaPadrao1')
        response = self.client.get(reverse('core:home'), follow=True)
        self.assertRedirects(response, reverse('accounts:trocar_senha'))
