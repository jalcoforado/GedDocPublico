from decimal import Decimal

from django.core.files.base import ContentFile
from django.test import TestCase

from apps.core.choices import StatusPedido
from apps.core.test_utils import criar_cenario_basico, criar_pedido
from apps.pagamentos import services as pagamentos_services

from . import services
from .models import ExtratoBancario, LancamentoExtrato


class ConciliacaoAutomaticaTests(TestCase):
    def setUp(self):
        self.cenario = criar_cenario_basico()
        self.usuarios = self.cenario['usuarios']

    def _autorizar(self, pedido):
        pagamentos_services.enviar_para_aprovacao(pedido, self.usuarios['SOLICITANTE'])
        pagamentos_services.aprovar_secretario(pedido, self.usuarios['SECRETARIO'])
        pagamentos_services.autorizar_lote([pedido], self.usuarios['AUTORIZADOR'])
        pedido.refresh_from_db()

    def test_baixa_automatica_por_correspondencia_exata(self):
        """RF40/RF41 — lançamento com valor, credor e data compatíveis gera baixa automática."""
        pedido = criar_pedido(self.cenario, valor=Decimal('1500.00'))
        self._autorizar(pedido)
        self.assertEqual(pedido.status, StatusPedido.AUTORIZADO)

        csv_conteudo = (
            "data;historico;valor;tipo;identificador\n"
            f"{pedido.vencimento.strftime('%d/%m/%Y')};PAGAMENTO {pedido.credor.nome.split()[0].upper()};1500,00;DEBITO;TX1\n"
        )
        extrato = ExtratoBancario.objects.create(
            conta_bancaria=self.cenario['conta'], formato=ExtratoBancario.Formato.CSV,
            periodo_inicio=pedido.vencimento, periodo_fim=pedido.vencimento,
            enviado_por=self.usuarios['TESOURARIA'],
        )
        extrato.arquivo.save('extrato.csv', ContentFile(csv_conteudo.encode('utf-8')), save=True)

        services.processar_extrato(extrato, self.usuarios['TESOURARIA'])

        pedido.refresh_from_db()
        self.assertEqual(pedido.status, StatusPedido.PAGO)
        lancamento = extrato.lancamentos.first()
        self.assertEqual(lancamento.status, LancamentoExtrato.Status.CONCILIADO_AUTOMATICO)
        self.assertEqual(lancamento.pedido_vinculado_id, pedido.pk)

    def test_lancamento_sem_correspondencia_fica_pendente(self):
        """RF42 — divergências (sem match exato) não são baixadas automaticamente."""
        pedido = criar_pedido(self.cenario, valor=Decimal('1500.00'))
        self._autorizar(pedido)

        csv_conteudo = (
            "data;historico;valor;tipo;identificador\n"
            "01/01/2026;PAGAMENTO DESCONHECIDO;77,00;DEBITO;TX9\n"
        )
        extrato = ExtratoBancario.objects.create(
            conta_bancaria=self.cenario['conta'], formato=ExtratoBancario.Formato.CSV,
            periodo_inicio=pedido.vencimento, periodo_fim=pedido.vencimento,
            enviado_por=self.usuarios['TESOURARIA'],
        )
        extrato.arquivo.save('extrato.csv', ContentFile(csv_conteudo.encode('utf-8')), save=True)

        services.processar_extrato(extrato, self.usuarios['TESOURARIA'])

        pedido.refresh_from_db()
        self.assertEqual(pedido.status, StatusPedido.AUTORIZADO)
        lancamento = extrato.lancamentos.first()
        self.assertEqual(lancamento.status, LancamentoExtrato.Status.PENDENTE)
