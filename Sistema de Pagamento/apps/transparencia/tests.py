from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.cadastros.models import Fornecedor
from apps.core.choices import StatusPedido
from apps.core.test_utils import criar_cenario_basico, criar_pedido

from .anonimizacao import mascarar_documento


class AnonimizacaoTests(TestCase):
    def test_cpf_de_pessoa_fisica_e_mascarado(self):
        """RF58/LGPD — CPF de fornecedor pessoa física é mascarado na exposição pública."""
        fornecedor = Fornecedor(tipo_pessoa=Fornecedor.TipoPessoa.FISICA, nome='Fulano', cnpj_cpf='123.456.789-01')
        self.assertEqual(mascarar_documento(fornecedor), '123.***.***-01')

    def test_cnpj_de_pessoa_juridica_nao_e_mascarado(self):
        fornecedor = Fornecedor(tipo_pessoa=Fornecedor.TipoPessoa.JURIDICA, nome='Empresa', cnpj_cpf='11.111.111/0001-11')
        self.assertEqual(mascarar_documento(fornecedor), '11.111.111/0001-11')


class PortalPublicoTests(TestCase):
    def setUp(self):
        self.cenario = criar_cenario_basico()

    def test_portal_acessivel_sem_autenticacao(self):
        response = self.client.get(reverse('transparencia:portal'))
        self.assertEqual(response.status_code, 200)

    def test_pedido_pendente_nao_aparece_no_portal(self):
        """RF56 — apenas pagamentos autorizados/efetuados são publicados."""
        criar_pedido(self.cenario, valor=Decimal('999.00'))  # status PENDENTE, não deve aparecer
        response = self.client.get(reverse('transparencia:portal'))
        self.assertNotIn('999.00', str(response.content))

    def test_dados_bancarios_nunca_sao_expostos(self):
        response = self.client.get(reverse('transparencia:exportar_json'))
        self.assertNotIn(b'chave_pix', response.content)
        self.assertNotIn(b'agencia', response.content)
