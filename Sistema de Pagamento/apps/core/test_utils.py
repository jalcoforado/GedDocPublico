import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model

from apps.accounts.models import PerfilUsuario
from apps.cadastros.models import ContaBancaria, FonteRecursos, Fornecedor, NaturezaDespesa, OrgaoSecretaria
from apps.core.choices import Criticidade, GrupoDespesa
from apps.financeiro import services as financeiro_services
from apps.financeiro.models import MovimentacaoConta

Usuario = get_user_model()


def criar_cenario_basico(saldo_inicial=Decimal('100000.00')):
    """Monta um cenário mínimo (cadastros + um usuário por perfil) reutilizável nos testes."""
    orgao = OrgaoSecretaria.objects.create(
        nome='Secretaria de Teste', codigo_orcamentario='99.99', unidade_gestora='UG 999', responsavel='Fulano'
    )
    fonte = FonteRecursos.objects.create(
        codigo='0001', descricao='Recursos Ordinários',
        grupos_despesa_permitidos=[GrupoDespesa.CUSTEIO],
    )
    conta = ContaBancaria.objects.create(
        nome='Conta Teste', banco='Banco Teste', agencia='0001', conta='0001-1',
        fonte_recursos=fonte, grupo_despesa=GrupoDespesa.CUSTEIO, ativa=True,
    )
    natureza = NaturezaDespesa.objects.create(
        codigo='3.3.90.30', descricao='Material de Consumo', criticidade_padrao=Criticidade.MEDIA
    )
    fornecedor = Fornecedor.objects.create(
        tipo_pessoa=Fornecedor.TipoPessoa.JURIDICA, nome='Fornecedor Teste Ltda', cnpj_cpf='11.111.111/0001-11',
    )

    usuarios = {}
    papeis = [
        ('SOLICITANTE', orgao),
        ('SECRETARIO', orgao),
        ('AUTORIZADOR', None),
        ('TESOURARIA', None),
        ('CONTROLE_INTERNO', None),
        ('ADMIN', None),
    ]
    for papel, orgao_do_papel in papeis:
        usuario = Usuario.objects.create_user(
            username=papel.lower(), email=f'{papel.lower()}@teste.com', password='senha123'
        )
        PerfilUsuario.objects.create(usuario=usuario, papel=papel, orgao=orgao_do_papel)
        usuarios[papel] = usuario

    if saldo_inicial:
        financeiro_services.registrar_movimentacao(
            conta, saldo_inicial, MovimentacaoConta.Origem.SALDO_INICIAL, usuarios['ADMIN'],
        )

    return {
        'orgao': orgao, 'fonte': fonte, 'conta': conta, 'natureza': natureza,
        'fornecedor': fornecedor, 'usuarios': usuarios,
    }


def criar_pedido(cenario, valor=Decimal('1000.00'), numero_ne='NE001', numero_nf='NF001', **kwargs):
    from apps.pagamentos.models import PedidoPagamento

    hoje = datetime.date.today()
    defaults = dict(
        orgao=cenario['orgao'], solicitante=cenario['usuarios']['SOLICITANTE'],
        credor=cenario['fornecedor'], natureza=cenario['natureza'], conta_bancaria=cenario['conta'],
        valor=valor, numero_ne=numero_ne, numero_nf=numero_nf,
        vencimento=hoje + datetime.timedelta(days=10), competencia=hoje.strftime('%m/%Y'),
        criticidade=Criticidade.MEDIA,
    )
    defaults.update(kwargs)
    return PedidoPagamento.objects.create(**defaults)
