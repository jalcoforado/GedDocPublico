from django.core.exceptions import ValidationError
from django.db import models

from apps.core.choices import Criticidade, GrupoDespesa
from apps.core.fields import EncryptedTextField
from apps.core.models import TimeStampedModel


class OrgaoSecretaria(TimeStampedModel):
    """RF01 — Órgãos/Secretarias."""

    nome = models.CharField(max_length=200)
    codigo_orcamentario = models.CharField(max_length=30, unique=True)
    unidade_gestora = models.CharField(max_length=200)
    responsavel = models.CharField(max_length=150)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Órgão/Secretaria'
        verbose_name_plural = 'Órgãos/Secretarias'
        ordering = ['nome']

    def __str__(self):
        return f"{self.codigo_orcamentario} — {self.nome}"


class Fornecedor(TimeStampedModel):
    """RF02 — Fornecedores/Credores."""

    class TipoPessoa(models.TextChoices):
        FISICA = 'FISICA', 'Pessoa Física'
        JURIDICA = 'JURIDICA', 'Pessoa Jurídica'

    class SituacaoCadastral(models.TextChoices):
        REGULAR = 'REGULAR', 'Regular'
        PENDENTE = 'PENDENTE', 'Pendência Cadastral'
        IRREGULAR = 'IRREGULAR', 'Irregular/Sancionado'

    tipo_pessoa = models.CharField(max_length=10, choices=TipoPessoa.choices)
    cnpj_cpf = models.CharField('CNPJ/CPF', max_length=18, unique=True)
    nome = models.CharField('Razão social / Nome', max_length=200)
    situacao_cadastral = models.CharField(
        max_length=10, choices=SituacaoCadastral.choices, default=SituacaoCadastral.REGULAR
    )
    motivo_pendencia = models.CharField(max_length=255, blank=True)

    # Dados bancários criptografados em repouso (RF66).
    banco = EncryptedTextField(blank=True)
    agencia = EncryptedTextField(blank=True)
    conta = EncryptedTextField(blank=True)
    chave_pix = EncryptedTextField(blank=True)

    class Meta:
        verbose_name = 'Fornecedor/Credor'
        verbose_name_plural = 'Fornecedores/Credores'
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.cnpj_cpf})"

    @property
    def tem_pendencia(self):
        return self.situacao_cadastral != self.SituacaoCadastral.REGULAR


class FonteRecursos(TimeStampedModel):
    """Fonte/destinação de recursos (Lei 4.320/1964, arts. 100-104; MCASP)."""

    codigo = models.CharField(max_length=20, unique=True)
    descricao = models.CharField(max_length=200)
    grupos_despesa_permitidos = models.JSONField(
        default=list,
        help_text='Lista de códigos de GrupoDespesa compatíveis com esta fonte.',
    )

    class Meta:
        verbose_name = 'Fonte de Recursos'
        verbose_name_plural = 'Fontes de Recursos'
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} — {self.descricao}"

    def permite_grupo(self, grupo_despesa):
        return not self.grupos_despesa_permitidos or grupo_despesa in self.grupos_despesa_permitidos


class ContaBancaria(TimeStampedModel):
    """RF03 — Contas Bancárias municipais."""

    nome = models.CharField(max_length=150, help_text='Ex.: Conta Movimento — Secretaria de Saúde')
    banco = models.CharField(max_length=100)
    agencia = models.CharField(max_length=20)
    conta = models.CharField(max_length=30)
    fonte_recursos = models.ForeignKey(
        FonteRecursos, on_delete=models.PROTECT, related_name='contas_bancarias'
    )
    grupo_despesa = models.CharField(max_length=20, choices=GrupoDespesa.choices)
    saldo_minimo_alerta = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # RF37
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Conta Bancária'
        verbose_name_plural = 'Contas Bancárias'
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.banco} ag.{self.agencia} cc.{self.conta})"

    def clean(self):
        if self.fonte_recursos_id and not self.fonte_recursos.permite_grupo(self.grupo_despesa):
            raise ValidationError(
                'Combinação Fonte × Grupo de despesa incompatível: a fonte '
                f'"{self.fonte_recursos}" não permite o grupo "{self.get_grupo_despesa_display()}".'
            )

    @property
    def saldo_atual(self):
        agregado = self.movimentacoes.aggregate(total=models.Sum('valor'))
        return agregado['total'] or 0

    @property
    def saldo_comprometido(self):
        from apps.core.choices import StatusPedido
        agregado = self.pedidos_vinculados.filter(
            status=StatusPedido.AUTORIZADO
        ).aggregate(total=models.Sum('valor'))
        return agregado['total'] or 0

    @property
    def saldo_disponivel_efetivo(self):
        return self.saldo_atual - self.saldo_comprometido


class NaturezaDespesa(TimeStampedModel):
    """RF04 — Naturezas/Categorias de Despesa."""

    codigo = models.CharField(max_length=20, unique=True)
    descricao = models.CharField(max_length=150)
    criticidade_padrao = models.CharField(
        max_length=10, choices=Criticidade.choices, default=Criticidade.MEDIA
    )
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Natureza/Categoria de Despesa'
        verbose_name_plural = 'Naturezas/Categorias de Despesa'
        ordering = ['descricao']

    def __str__(self):
        return f"{self.codigo} — {self.descricao}"


class Contrato(TimeStampedModel):
    """RF05 — Contratos administrativos."""

    numero = models.CharField(max_length=50, unique=True)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.PROTECT, related_name='contratos')
    orgao = models.ForeignKey(OrgaoSecretaria, on_delete=models.PROTECT, related_name='contratos')
    objeto = models.CharField(max_length=255)
    vigencia_inicio = models.DateField()
    vigencia_fim = models.DateField()
    valor_total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = 'Contrato'
        verbose_name_plural = 'Contratos'
        ordering = ['-vigencia_inicio']

    def __str__(self):
        return f"Contrato {self.numero} — {self.fornecedor}"

    @property
    def saldo_consumido(self):
        from apps.core.choices import StatusPedido
        agregado = self.pedidos.exclude(
            status__in=[StatusPedido.REJEITADO, StatusPedido.CANCELADO, StatusPedido.DEVOLVIDO]
        ).aggregate(total=models.Sum('valor'))
        return agregado['total'] or 0

    @property
    def saldo_remanescente(self):
        return self.valor_total - self.saldo_consumido


class AlcadaAutorizacao(TimeStampedModel):
    """RF07 — Limites de alçada de autorização por valor e/ou natureza de despesa."""

    perfil = models.ForeignKey(
        'accounts.PerfilUsuario', on_delete=models.CASCADE, related_name='alcadas'
    )
    natureza = models.ForeignKey(
        NaturezaDespesa, on_delete=models.CASCADE, null=True, blank=True,
        help_text='Deixe em branco para aplicar como limite geral do perfil.',
    )
    valor_maximo = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = 'Alçada de Autorização'
        verbose_name_plural = 'Alçadas de Autorização'
        unique_together = [('perfil', 'natureza')]

    def __str__(self):
        alvo = self.natureza or 'Geral'
        return f"{self.perfil} — {alvo} até R$ {self.valor_maximo}"
