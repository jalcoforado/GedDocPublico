from django.db.models.fields.files import FieldFile
from django.db.models.signals import post_delete, post_save, pre_save

from apps.core.fields import EncryptedTextField
from apps.core.middleware import get_current_ip, get_current_user


def _serializar_instancia(instance):
    """
    Snapshot de todos os campos concretos do modelo (inclusive os com
    editable=False, como protocolo/numero) — usa field.value_from_object
    ao invés de model_to_dict para não perder esses campos. Campos
    EncryptedTextField (RF66) nunca têm o valor decriptado exposto no log.
    """
    dados = {}
    for field in instance._meta.fields:
        valor = field.value_from_object(instance)
        if isinstance(field, EncryptedTextField):
            dados[field.name] = '***CRIPTOGRAFADO***' if valor else ''
        elif isinstance(valor, FieldFile):
            dados[field.name] = valor.name or ''
        else:
            dados[field.name] = valor
    return dados


def _snapshot_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            anterior = sender.objects.get(pk=instance.pk)
            instance._auditoria_antes = _serializar_instancia(anterior)
        except sender.DoesNotExist:
            instance._auditoria_antes = None
    else:
        instance._auditoria_antes = None


def _registrar_post_save(sender, instance, created, **kwargs):
    from .models import LogAuditoria

    LogAuditoria.objects.create(
        usuario=get_current_user(),
        acao=LogAuditoria.Acao.CRIACAO if created else LogAuditoria.Acao.EDICAO,
        modelo=f'{sender._meta.app_label}.{sender.__name__}',
        objeto_id=str(instance.pk),
        objeto_repr=str(instance)[:255],
        dados_antes=getattr(instance, '_auditoria_antes', None),
        dados_depois=_serializar_instancia(instance),
        ip_origem=get_current_ip(),
    )


def _registrar_post_delete(sender, instance, **kwargs):
    from .models import LogAuditoria

    LogAuditoria.objects.create(
        usuario=get_current_user(),
        acao=LogAuditoria.Acao.EXCLUSAO,
        modelo=f'{sender._meta.app_label}.{sender.__name__}',
        objeto_id=str(instance.pk),
        objeto_repr=str(instance)[:255],
        dados_antes=_serializar_instancia(instance),
        dados_depois=None,
        ip_origem=get_current_ip(),
    )


def registrar_auditoria(model):
    """Liga os signals de auditoria a um modelo. Chamado em AuditoriaConfig.ready()."""
    pre_save.connect(_snapshot_pre_save, sender=model, weak=False)
    post_save.connect(_registrar_post_save, sender=model, weak=False)
    post_delete.connect(_registrar_post_delete, sender=model, weak=False)
