from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class UsuarioManager(UserManager):
    def get_by_natural_key(self, username):
        return self.get(email__iexact=username)


class Usuario(AbstractUser):
    """
    Custom user — login institucional por e-mail (RF62). SSO/Active
    Directory real não está conectado neste ambiente; a autenticação usa
    e-mail+senha do Django, com um ponto de extensão documentado no README
    para plugar um backend SSO/SAML futuramente.
    """

    email = models.EmailField('e-mail institucional', unique=True)
    must_change_password = models.BooleanField(
        'deve trocar a senha no próximo login', default=True
    )  # RF63

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = UsuarioManager()

    def __str__(self):
        return f"{self.get_full_name() or self.username} <{self.email}>"


class PerfilUsuario(TimeStampedModel):
    """Papel/perfil de acesso do usuário no fluxo (M13, M4)."""

    class Papel(models.TextChoices):
        SOLICITANTE = 'SOLICITANTE', 'Solicitante'
        SECRETARIO = 'SECRETARIO', 'Secretário da Pasta'
        AUTORIZADOR = 'AUTORIZADOR', 'Autorizador Final'
        TESOURARIA = 'TESOURARIA', 'Tesouraria'
        CONTROLE_INTERNO = 'CONTROLE_INTERNO', 'Controle Interno/Auditoria'
        ADMIN = 'ADMIN', 'Administrador do Sistema'

    class NivelFiducia(models.TextChoices):
        BASICO = 'BASICO', 'Básico'
        INTERMEDIARIO = 'INTERMEDIARIO', 'Intermediário'
        ELEVADO = 'ELEVADO', 'Elevado'

    usuario = models.OneToOneField(
        Usuario, on_delete=models.CASCADE, related_name='perfil'
    )
    papel = models.CharField(max_length=20, choices=Papel.choices)
    orgao = models.ForeignKey(
        'cadastros.OrgaoSecretaria',
        on_delete=models.PROTECT,
        related_name='usuarios',
        null=True,
        blank=True,
        help_text='Obrigatório para Solicitante e Secretário (escopo por órgão).',
    )
    nivel_fiducia = models.CharField(
        max_length=20, choices=NivelFiducia.choices, default=NivelFiducia.BASICO
    )
    limite_autorizacao = models.DecimalField(
        'limite de alçada (valor máximo autorizável)',
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='RF07 — usado apenas para o papel Autorizador Final.',
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuário'

    def __str__(self):
        return f"{self.usuario} — {self.get_papel_display()}"


class TentativaAcessoLog(models.Model):
    """RF65 — tentativas de acesso malsucedidas, para bloqueio temporário."""

    email = models.EmailField()
    sucesso = models.BooleanField()
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Tentativa de Acesso'
        verbose_name_plural = 'Tentativas de Acesso'
        indexes = [models.Index(fields=['email', 'criado_em'])]

    def __str__(self):
        status = 'sucesso' if self.sucesso else 'falha'
        return f"{self.email} — {status} em {self.criado_em:%d/%m/%Y %H:%M}"
