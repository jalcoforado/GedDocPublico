from decimal import Decimal

from django.test import TestCase

from apps.core.choices import StatusPedido
from apps.core.test_utils import criar_cenario_basico, criar_pedido

from . import services
from .exceptions import (
    DocumentacaoObrigatoriaError,
    SaldoInsuficienteError,
    SegregacaoFuncoesError,
    TransicaoInvalidaError,
)


class FluxoPedidoPagamentoTests(TestCase):
    def setUp(self):
        self.cenario = criar_cenario_basico()
        self.usuarios = self.cenario['usuarios']

    def test_envio_exige_ne_e_nf(self):
        """RF08/RN M2 — pedido sem NE ou NF não pode ser enviado para aprovação."""
        pedido = criar_pedido(self.cenario, numero_ne='', numero_nf='')
        with self.assertRaises(DocumentacaoObrigatoriaError):
            services.enviar_para_aprovacao(pedido, self.usuarios['SOLICITANTE'])

    def test_envio_exceto_ne_nf_dispensa_documentacao(self):
        pedido = criar_pedido(self.cenario, numero_ne='', numero_nf='', exceto_ne_nf=True)
        services.enviar_para_aprovacao(pedido, self.usuarios['SOLICITANTE'])
        pedido.refresh_from_db()
        self.assertTrue(pedido.enviado_para_aprovacao)

    def test_fluxo_completo_solicitacao_a_execucao(self):
        """Solicitação → aprovação do Secretário → autorização → execução (baixa financeira)."""
        pedido = criar_pedido(self.cenario, valor=Decimal('500.00'))

        services.enviar_para_aprovacao(pedido, self.usuarios['SOLICITANTE'])
        services.aprovar_secretario(pedido, self.usuarios['SECRETARIO'])
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, StatusPedido.APROVADO_SECRETARIO)

        ordem = services.autorizar_lote([pedido], self.usuarios['AUTORIZADOR'])
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, StatusPedido.AUTORIZADO)
        self.assertEqual(ordem.valor_total, Decimal('500.00'))

        services.executar_pagamento(
            pedido, self.usuarios['TESOURARIA'], forma_pagamento='PIX',
        )
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, StatusPedido.PAGO)
        self.assertEqual(pedido.conta_bancaria.saldo_atual, Decimal('99500.00'))

    def test_autorizacao_bloqueada_quando_saldo_insuficiente(self):
        """RF25 — autorização não pode exceder o saldo disponível da conta/fonte."""
        pedido = criar_pedido(self.cenario, valor=Decimal('999999.00'))
        services.enviar_para_aprovacao(pedido, self.usuarios['SOLICITANTE'])
        services.aprovar_secretario(pedido, self.usuarios['SECRETARIO'])

        with self.assertRaises(SaldoInsuficienteError):
            services.autorizar_lote([pedido], self.usuarios['AUTORIZADOR'])

        pedido.refresh_from_db()
        self.assertEqual(pedido.status, StatusPedido.APROVADO_SECRETARIO)

    def test_segregacao_de_funcoes_impede_mesmo_usuario_em_duas_etapas(self):
        """RF64 — o mesmo usuário não pode aprovar e depois autorizar o mesmo pedido."""
        pedido = criar_pedido(self.cenario, valor=Decimal('100.00'))
        services.enviar_para_aprovacao(pedido, self.usuarios['SOLICITANTE'])
        services.aprovar_secretario(pedido, self.usuarios['SECRETARIO'])

        with self.assertRaises(SegregacaoFuncoesError):
            # o próprio secretário tentando autorizar o pedido que aprovou
            services.autorizar_lote([pedido], self.usuarios['SECRETARIO'])

    def test_devolucao_exige_justificativa(self):
        pedido = criar_pedido(self.cenario)
        services.enviar_para_aprovacao(pedido, self.usuarios['SOLICITANTE'])
        with self.assertRaises(DocumentacaoObrigatoriaError):
            services.devolver(pedido, self.usuarios['SECRETARIO'], '')

    def test_nao_pode_executar_pagamento_sem_autorizacao(self):
        pedido = criar_pedido(self.cenario)
        with self.assertRaises(TransicaoInvalidaError):
            services.executar_pagamento(pedido, self.usuarios['TESOURARIA'], forma_pagamento='PIX')
