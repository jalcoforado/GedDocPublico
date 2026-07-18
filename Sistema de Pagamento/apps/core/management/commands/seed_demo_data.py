import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import PerfilUsuario
from apps.cadastros.models import (
    AlcadaAutorizacao,
    ContaBancaria,
    Contrato,
    FonteRecursos,
    Fornecedor,
    NaturezaDespesa,
    OrgaoSecretaria,
)
from apps.conciliacao import services as conciliacao_services
from apps.conciliacao.models import ExtratoBancario
from apps.core.choices import Criticidade, GrupoDespesa, StatusPedido
from apps.financeiro import services as financeiro_services
from apps.financeiro.models import MovimentacaoConta
from apps.pagamentos import services as pagamentos_services
from apps.pagamentos.models import NotaEmpenhoReferencia, PedidoPagamento

Usuario = get_user_model()

SENHA_PADRAO = 'Municipio@123'


class Command(BaseCommand):
    help = 'Cria dados de demonstração: cadastros básicos, usuários por perfil e pedidos em vários status.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('Criando cadastros básicos...')
        orgao_saude, orgao_educacao = self._criar_orgaos()
        fonte = self._criar_fonte()
        conta = self._criar_conta_bancaria(fonte)
        naturezas = self._criar_naturezas()
        fornecedores = self._criar_fornecedores()
        self._criar_contrato(fornecedores['clinica'], orgao_saude)

        self.stdout.write('Criando usuários de demonstração...')
        usuarios = self._criar_usuarios(orgao_saude, orgao_educacao)

        self.stdout.write('Criando nota de empenho de referência (stub SIAFIC)...')
        NotaEmpenhoReferencia.objects.get_or_create(
            numero='2026NE000123',
            defaults=dict(orgao=orgao_saude, exercicio=2026, valor_empenhado=Decimal('50000.00'), liquidado=True),
        )

        self.stdout.write('Criando pedidos de pagamento em vários status...')
        self._criar_pedidos(orgao_saude, usuarios, fornecedores, naturezas, conta)

        self.stdout.write('Processando extrato bancário de exemplo (demonstra conciliação automática)...')
        self._criar_extrato_exemplo(conta, usuarios['tesouraria'])

        self.stdout.write(self.style.SUCCESS('Dados de demonstração criados com sucesso.'))
        self._imprimir_credenciais()

    # -- Cadastros ---------------------------------------------------

    def _criar_orgaos(self):
        saude, _ = OrgaoSecretaria.objects.get_or_create(
            codigo_orcamentario='02.10',
            defaults=dict(nome='Secretaria Municipal de Saúde', unidade_gestora='UG 002', responsavel='Secretário de Saúde'),
        )
        educacao, _ = OrgaoSecretaria.objects.get_or_create(
            codigo_orcamentario='02.20',
            defaults=dict(nome='Secretaria Municipal de Educação', unidade_gestora='UG 003', responsavel='Secretário de Educação'),
        )
        return saude, educacao

    def _criar_fonte(self):
        fonte, _ = FonteRecursos.objects.get_or_create(
            codigo='0001',
            defaults=dict(
                descricao='Recursos Ordinários (Tesouro Municipal)',
                grupos_despesa_permitidos=[GrupoDespesa.CUSTEIO, GrupoDespesa.INVESTIMENTO, GrupoDespesa.PESSOAL],
            ),
        )
        return fonte

    def _criar_conta_bancaria(self, fonte):
        conta, criada = ContaBancaria.objects.get_or_create(
            nome='Conta Movimento — Recursos Ordinários',
            defaults=dict(
                banco='Banco do Brasil', agencia='1234-5', conta='98765-4',
                fonte_recursos=fonte, grupo_despesa=GrupoDespesa.CUSTEIO,
                saldo_minimo_alerta=Decimal('10000.00'), ativa=True,
            ),
        )
        if criada:
            admin_user = self._get_or_create_admin_placeholder()
            financeiro_services.registrar_movimentacao(
                conta, Decimal('200000.00'), MovimentacaoConta.Origem.SALDO_INICIAL, admin_user,
                justificativa='Saldo inicial de demonstração.',
            )
        return conta

    def _get_or_create_admin_placeholder(self):
        # usado apenas para atribuir responsável ao saldo inicial, antes dos perfis existirem
        usuario, criado = Usuario.objects.get_or_create(
            email='admin@municipio.gov.br',
            defaults=dict(username='admin', first_name='Administrador', is_staff=True, is_superuser=True),
        )
        if criado:
            usuario.set_password(SENHA_PADRAO)
            usuario.must_change_password = True
            usuario.save()
        return usuario

    def _criar_naturezas(self):
        dados = [
            ('3.3.90.30', 'Material de Consumo — Medicamentos', Criticidade.URGENTE),
            ('3.3.90.39', 'Serviços de Terceiros — Pessoa Jurídica', Criticidade.MEDIA),
            ('3.3.90.33', 'Transporte Escolar', Criticidade.ALTA),
            ('3.3.90.36', 'Serviços de Terceiros — Pessoa Física', Criticidade.BAIXA),
        ]
        naturezas = {}
        for codigo, descricao, criticidade in dados:
            n, _ = NaturezaDespesa.objects.get_or_create(
                codigo=codigo, defaults=dict(descricao=descricao, criticidade_padrao=criticidade)
            )
            naturezas[codigo] = n
        return naturezas

    def _criar_fornecedores(self):
        clinica, _ = Fornecedor.objects.get_or_create(
            cnpj_cpf='12.345.678/0001-90',
            defaults=dict(
                tipo_pessoa=Fornecedor.TipoPessoa.JURIDICA, nome='Clínica Saúde & Vida Ltda',
                situacao_cadastral=Fornecedor.SituacaoCadastral.REGULAR,
                banco='Caixa Econômica Federal', agencia='0001', conta='11111-1', chave_pix='12.345.678/0001-90',
            ),
        )
        transportadora, _ = Fornecedor.objects.get_or_create(
            cnpj_cpf='98.765.432/0001-10',
            defaults=dict(
                tipo_pessoa=Fornecedor.TipoPessoa.JURIDICA, nome='Transportes Escolares Bom Caminho Ltda',
                situacao_cadastral=Fornecedor.SituacaoCadastral.REGULAR,
                banco='Bradesco', agencia='4321', conta='22222-2', chave_pix='98.765.432/0001-10',
            ),
        )
        autonomo, _ = Fornecedor.objects.get_or_create(
            cnpj_cpf='123.456.789-01',
            defaults=dict(
                tipo_pessoa=Fornecedor.TipoPessoa.FISICA, nome='João da Silva Consultoria',
                situacao_cadastral=Fornecedor.SituacaoCadastral.PENDENTE, motivo_pendencia='Certidão vencida',
                banco='Itaú', agencia='5555', conta='33333-3', chave_pix='123.456.789-01',
            ),
        )
        return {'clinica': clinica, 'transportadora': transportadora, 'autonomo': autonomo}

    def _criar_contrato(self, fornecedor, orgao):
        Contrato.objects.get_or_create(
            numero='CT-2026-001',
            defaults=dict(
                fornecedor=fornecedor, orgao=orgao, objeto='Fornecimento de medicamentos',
                vigencia_inicio=datetime.date(2026, 1, 1), vigencia_fim=datetime.date(2026, 12, 31),
                valor_total=Decimal('100000.00'),
            ),
        )

    # -- Usuários ------------------------------------------------------

    def _criar_usuarios(self, orgao_saude, orgao_educacao):
        definicoes = [
            ('solicitante@municipio.gov.br', 'Solicitante', PerfilUsuario.Papel.SOLICITANTE, orgao_saude),
            ('secretario@municipio.gov.br', 'Secretário Saúde', PerfilUsuario.Papel.SECRETARIO, orgao_saude),
            ('autorizador@municipio.gov.br', 'Autorizador Final', PerfilUsuario.Papel.AUTORIZADOR, None),
            ('tesouraria@municipio.gov.br', 'Tesouraria', PerfilUsuario.Papel.TESOURARIA, None),
            ('controle@municipio.gov.br', 'Controle Interno', PerfilUsuario.Papel.CONTROLE_INTERNO, None),
        ]
        usuarios = {}
        for email, nome, papel, orgao in definicoes:
            usuario, criado = Usuario.objects.get_or_create(
                email=email, defaults=dict(username=email.split('@')[0], first_name=nome)
            )
            if criado:
                usuario.set_password(SENHA_PADRAO)
                usuario.must_change_password = True
                usuario.save()
            PerfilUsuario.objects.get_or_create(
                usuario=usuario,
                defaults=dict(
                    papel=papel, orgao=orgao,
                    nivel_fiducia=PerfilUsuario.NivelFiducia.ELEVADO if papel == PerfilUsuario.Papel.AUTORIZADOR else PerfilUsuario.NivelFiducia.INTERMEDIARIO,
                    limite_autorizacao=Decimal('500000.00') if papel == PerfilUsuario.Papel.AUTORIZADOR else None,
                ),
            )
            usuarios[papel.lower()] = usuario

        admin_user = self._get_or_create_admin_placeholder()
        PerfilUsuario.objects.get_or_create(usuario=admin_user, defaults=dict(papel=PerfilUsuario.Papel.ADMIN))
        usuarios['admin'] = admin_user
        return usuarios

    # -- Pedidos ---------------------------------------------------------

    def _criar_pedidos(self, orgao, usuarios, fornecedores, naturezas, conta):
        hoje = timezone.localdate()
        solicitante = usuarios['solicitante']
        secretario = usuarios['secretario']
        autorizador = usuarios['autorizador']
        tesouraria = usuarios['tesouraria']

        base = dict(orgao=orgao, solicitante=solicitante, conta_bancaria=conta)

        # 1) rascunho, ainda não enviado
        PedidoPagamento.objects.get_or_create(
            numero_nf='NF-0001', numero_ne='2026NE000123', defaults=dict(
                **base, credor=fornecedores['clinica'], natureza=naturezas['3.3.90.30'],
                valor=Decimal('4500.00'), vencimento=hoje + datetime.timedelta(days=20),
                competencia=hoje.strftime('%m/%Y'), criticidade=Criticidade.URGENTE, urgente=True,
                justificativa_urgencia='Reposição de estoque crítico de medicamentos.',
            ),
        )

        # 2) enviado, aguardando aprovação do secretário
        p2, criado2 = PedidoPagamento.objects.get_or_create(
            numero_nf='NF-0002', numero_ne='2026NE000124', defaults=dict(
                **base, credor=fornecedores['transportadora'], natureza=naturezas['3.3.90.33'],
                valor=Decimal('12000.00'), vencimento=hoje + datetime.timedelta(days=15),
                competencia=hoje.strftime('%m/%Y'), criticidade=Criticidade.ALTA,
            ),
        )
        if criado2:
            pagamentos_services.enviar_para_aprovacao(p2, solicitante)

        # 3) aprovado pelo secretário, aguardando autorização
        p3, criado3 = PedidoPagamento.objects.get_or_create(
            numero_nf='NF-0003', numero_ne='2026NE000125', defaults=dict(
                **base, credor=fornecedores['clinica'], natureza=naturezas['3.3.90.39'],
                valor=Decimal('8000.00'), vencimento=hoje + datetime.timedelta(days=10),
                competencia=hoje.strftime('%m/%Y'), criticidade=Criticidade.MEDIA,
            ),
        )
        if criado3:
            pagamentos_services.enviar_para_aprovacao(p3, solicitante)
            pagamentos_services.aprovar_secretario(p3, secretario)

        # 4) autorizado, na fila da tesouraria — será conciliado automaticamente pelo extrato de exemplo
        p4, criado4 = PedidoPagamento.objects.get_or_create(
            numero_nf='NF-0004', numero_ne='2026NE000126', defaults=dict(
                **base, credor=fornecedores['transportadora'], natureza=naturezas['3.3.90.33'],
                valor=Decimal('15000.00'), vencimento=hoje, competencia=hoje.strftime('%m/%Y'),
                criticidade=Criticidade.ALTA,
            ),
        )
        if criado4:
            pagamentos_services.enviar_para_aprovacao(p4, solicitante)
            pagamentos_services.aprovar_secretario(p4, secretario)
            pagamentos_services.autorizar_lote([p4], autorizador)
        self._pedido_conciliacao = p4

        # 5) já pago
        p5, criado5 = PedidoPagamento.objects.get_or_create(
            numero_nf='NF-0005', numero_ne='2026NE000127', defaults=dict(
                **base, credor=fornecedores['clinica'], natureza=naturezas['3.3.90.30'],
                valor=Decimal('3000.00'), vencimento=hoje - datetime.timedelta(days=5),
                competencia=hoje.strftime('%m/%Y'), criticidade=Criticidade.BAIXA,
            ),
        )
        if criado5:
            pagamentos_services.enviar_para_aprovacao(p5, solicitante)
            pagamentos_services.aprovar_secretario(p5, secretario)
            pagamentos_services.autorizar_lote([p5], autorizador)
            pagamentos_services.executar_pagamento(p5, tesouraria, forma_pagamento=PedidoPagamento.FormaPagamento.PIX)

    # -- Extrato de exemplo (demonstra conciliação automática) --------

    def _criar_extrato_exemplo(self, conta, tesouraria):
        pedido = getattr(self, '_pedido_conciliacao', None)
        if pedido is None or ExtratoBancario.objects.filter(conta_bancaria=conta).exists():
            return
        primeiro_nome = pedido.credor.nome.split()[0].upper()
        valor_br = f"{pedido.valor:.2f}".replace('.', ',')  # CSVExtratoParser espera vírgula decimal
        linhas = [
            'data;historico;valor;tipo;identificador',
            f"{pedido.vencimento.strftime('%d/%m/%Y')};PAGAMENTO {primeiro_nome};{valor_br};DEBITO;TX0001",
        ]
        conteudo = '\n'.join(linhas)

        extrato = ExtratoBancario.objects.create(
            conta_bancaria=conta, formato=ExtratoBancario.Formato.CSV,
            periodo_inicio=pedido.vencimento, periodo_fim=pedido.vencimento,
            enviado_por=tesouraria,
        )
        extrato.arquivo.save('extrato_exemplo.csv', ContentFile(conteudo.encode('utf-8')), save=True)
        conciliacao_services.processar_extrato(extrato, tesouraria)

    def _imprimir_credenciais(self):
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Credenciais de demonstração (senha padrão para todos, troca obrigatória no 1º login):'))
        for email in [
            'solicitante@municipio.gov.br', 'secretario@municipio.gov.br', 'autorizador@municipio.gov.br',
            'tesouraria@municipio.gov.br', 'controle@municipio.gov.br', 'admin@municipio.gov.br',
        ]:
            self.stdout.write(f'  {email} / {SENHA_PADRAO}')
