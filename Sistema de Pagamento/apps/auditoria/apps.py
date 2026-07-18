from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.auditoria'
    label = 'auditoria'

    def ready(self):
        from django.apps import apps

        from .signals import registrar_auditoria

        modelos_auditados = [
            ('cadastros', 'OrgaoSecretaria'),
            ('cadastros', 'Fornecedor'),
            ('cadastros', 'ContaBancaria'),
            ('cadastros', 'NaturezaDespesa'),
            ('cadastros', 'Contrato'),
            ('cadastros', 'AlcadaAutorizacao'),
            ('accounts', 'PerfilUsuario'),
            ('pagamentos', 'PedidoPagamento'),
            ('pagamentos', 'OrdemPagamento'),
            ('financeiro', 'MovimentacaoConta'),
            ('conciliacao', 'ExtratoBancario'),
        ]
        for app_label, model_name in modelos_auditados:
            registrar_auditoria(apps.get_model(app_label, model_name))
