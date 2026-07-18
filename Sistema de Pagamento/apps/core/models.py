from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base with creation/update timestamps used across all apps."""

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
