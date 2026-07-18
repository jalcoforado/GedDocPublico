from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class LogAuditoria(models.Model):
    """
    RF59-RF61 — trilha imutável de todas as ações relevantes do Sistema.
    Nunca é editado ou apagado após criado (ver save()/delete() abaixo).
    """

    class Acao(models.TextChoices):
        CRIACAO = 'CRIACAO', 'Inclusão'
        EDICAO = 'EDICAO', 'Edição'
        EXCLUSAO = 'EXCLUSAO', 'Exclusão'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='logs_auditoria'
    )
    acao = models.CharField(max_length=10, choices=Acao.choices)
    modelo = models.CharField(max_length=100)
    objeto_id = models.CharField(max_length=50)
    objeto_repr = models.CharField(max_length=255)
    dados_antes = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    dados_depois = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['modelo', 'objeto_id']),
            models.Index(fields=['criado_em']),
        ]

    def __str__(self):
        return f"{self.criado_em:%d/%m/%Y %H:%M} — {self.get_acao_display()} — {self.modelo} #{self.objeto_id}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError('Registros de auditoria são imutáveis e não podem ser alterados (RF61).')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError('Registros de auditoria são imutáveis e não podem ser excluídos (RF61).')
