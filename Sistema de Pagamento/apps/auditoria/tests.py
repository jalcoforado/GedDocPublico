from decimal import Decimal

from django.test import TestCase

from apps.core.test_utils import criar_cenario_basico, criar_pedido
from apps.pagamentos import services

from .models import LogAuditoria


class AuditoriaTests(TestCase):
    def setUp(self):
        self.cenario = criar_cenario_basico()

    def test_criacao_de_pedido_gera_log_de_auditoria(self):
        """RF59 — toda inclusão relevante é registrada com usuário, data/hora e dados."""
        antes = LogAuditoria.objects.count()
        pedido = criar_pedido(self.cenario, valor=Decimal('321.00'))
        logs = LogAuditoria.objects.filter(modelo='pagamentos.PedidoPagamento', objeto_id=str(pedido.pk))
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().acao, LogAuditoria.Acao.CRIACAO)
        self.assertGreater(LogAuditoria.objects.count(), antes)

    def test_edicao_registra_dados_antes_e_depois(self):
        pedido = criar_pedido(self.cenario, valor=Decimal('100.00'))
        pedido.valor = Decimal('200.00')
        pedido.save()

        log = LogAuditoria.objects.filter(
            modelo='pagamentos.PedidoPagamento', objeto_id=str(pedido.pk), acao=LogAuditoria.Acao.EDICAO
        ).latest('criado_em')
        self.assertEqual(log.dados_antes['valor'], '100.00')
        self.assertEqual(log.dados_depois['valor'], '200.00')

    def test_log_de_auditoria_e_imutavel(self):
        """RF61 — vedada qualquer exclusão ou alteração posterior dos registros de auditoria."""
        pedido = criar_pedido(self.cenario)
        log = LogAuditoria.objects.filter(objeto_id=str(pedido.pk)).first()

        log.objeto_repr = 'adulterado'
        with self.assertRaises(RuntimeError):
            log.save()

        with self.assertRaises(RuntimeError):
            log.delete()

    def test_dados_bancarios_nao_aparecem_em_texto_puro_no_log(self):
        """RF66 — campos EncryptedTextField nunca são expostos em texto puro no log de auditoria."""
        fornecedor = self.cenario['fornecedor']
        fornecedor.banco = 'Banco Sigiloso'
        fornecedor.save()

        log = LogAuditoria.objects.filter(
            modelo='cadastros.Fornecedor', objeto_id=str(fornecedor.pk)
        ).latest('criado_em')
        self.assertNotIn('Banco Sigiloso', str(log.dados_depois))
