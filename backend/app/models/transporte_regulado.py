"""Transporte Regulado — modelos de Permissionário, Empresa, Veículo, Documentos e Avaliações.

Domínio SEPARADO da Frota Interna (schema `transporte_regulado`, permissão
`transporte_regulado`). Tenant-scoped, RLS nas tabelas do schema (ver migrations
0041/0042/0043/0044), no mesmo padrão de `frota.veiculo`.

`situacao` é o estado regulatório (pendente / ativo(a) / suspenso(a) /
cassado(a) / inativo(a)); `excluido` é soft-delete. `cpf`/`cnpj` únicos por tenant
entre não excluídos.
"""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


# Enums (string-based for DB flexibility)
TIPO_DOCUMENTO_CHOICES = {
    "crlv": "CRLV",
    "cnh_copia": "Cópia CNH",
    "inspecao": "Inspeção",
    "vistoria": "Vistoria",
    "seguro": "Seguro",
    "autorizacao_especial": "Autorização Especial",
    "adaptacao": "Adaptação Mobiliário",
    "outro": "Outro",
}

STATUS_DOCUMENTO_CHOICES = {
    "pendente": "Pendente",
    "valido": "Válido",
    "vencido": "Vencido",
    "rejeitado": "Rejeitado",
}

RESULTADO_AVALIACAO_CHOICES = {
    "pendente": "Pendente",
    "aprovado": "Aprovado",
    "reprovado": "Reprovado",
    "condicional": "Condicional",
}

RESULTADO_VISTORIA_CHOICES = {
    "pendente": "Pendente",
    "aprovado": "Aprovado",
    "reprovado": "Reprovado",
    "condicional": "Condicional",
}


class Permissionario(Base):
    __tablename__ = "permissionario"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cpf: Mapped[str] = mapped_column(String(11), nullable=False)
    rg: Mapped[str | None] = mapped_column(String(20), nullable=True)
    data_nascimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cnh_numero: Mapped[str | None] = mapped_column(String(11), nullable=True)
    cnh_categoria: Mapped[str | None] = mapped_column(String(5), nullable=True)
    cnh_validade: Mapped[date | None] = mapped_column(Date, nullable=True)
    tipo_servico: Mapped[str] = mapped_column(String(30), nullable=False)
    numero_permissao: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data_inicio_permissao: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_validade_permissao: Mapped[date | None] = mapped_column(Date, nullable=True)
    situacao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pendente"
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Empresa(Base):
    """Empresa/operadora regulada. `cnpj` único por tenant entre não excluídas;
    `id_representante_permissionario` opcional (FK para `permissionario`, mesmo
    tenant — coerência garantida no serviço)."""

    __tablename__ = "empresa"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    razao_social: Mapped[str] = mapped_column(String(200), nullable=False)
    nome_fantasia: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False)
    inscricao_municipal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    inscricao_estadual: Mapped[str | None] = mapped_column(String(30), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cep: Mapped[str | None] = mapped_column(String(9), nullable=True)
    logradouro: Mapped[str | None] = mapped_column(String(200), nullable=True)
    numero: Mapped[str | None] = mapped_column(String(20), nullable=True)
    complemento: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bairro: Mapped[str | None] = mapped_column(String(100), nullable=True)
    municipio: Mapped[str | None] = mapped_column(String(100), nullable=True)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True)
    tipo_servico: Mapped[str] = mapped_column(String(30), nullable=False)
    numero_autorizacao: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data_inicio_autorizacao: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_validade_autorizacao: Mapped[date | None] = mapped_column(Date, nullable=True)
    id_representante_permissionario: Mapped[int | None] = mapped_column(
        ForeignKey("transporte_regulado.permissionario.id"), nullable=True
    )
    situacao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pendente"
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class VeiculoRegulado(Base):
    """Veículo regulado/permissionário. Nome de classe distinto de `frota.Veiculo`
    para evitar colisão de domínio (tabela `transporte_regulado.veiculo`). NÃO
    referencia `frota.veiculo`. Vínculo a permissionário e/ou empresa (ao menos um);
    `placa` única por tenant entre não excluídos; `renavam`/`chassi` únicos quando
    informados (coerências garantidas no serviço)."""

    __tablename__ = "veiculo"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_permissionario: Mapped[int | None] = mapped_column(
        ForeignKey("transporte_regulado.permissionario.id"), nullable=True
    )
    id_empresa: Mapped[int | None] = mapped_column(
        ForeignKey("transporte_regulado.empresa.id"), nullable=True
    )
    placa: Mapped[str] = mapped_column(String(7), nullable=False)
    renavam: Mapped[str | None] = mapped_column(String(11), nullable=True)
    chassi: Mapped[str | None] = mapped_column(String(17), nullable=True)
    marca: Mapped[str] = mapped_column(String(60), nullable=False)
    modelo: Mapped[str] = mapped_column(String(60), nullable=False)
    ano_fabricacao: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ano_modelo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cor: Mapped[str | None] = mapped_column(String(30), nullable=True)
    categoria: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tipo_servico: Mapped[str] = mapped_column(String(30), nullable=False)
    capacidade_passageiros: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tipo_combustivel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    adaptado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    numero_autorizacao: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data_inicio_autorizacao: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_validade_autorizacao: Mapped[date | None] = mapped_column(Date, nullable=True)
    situacao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pendente"
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class VeiculoDocumento(Base):
    """Documentos de veículos regulados (metadados apenas — sem upload/anexos).

    Tipos: CRLV, CNH, inspeção, vistoria, seguro, autorização especial, adaptação, outro.
    Status: pendente, válido, vencido, rejeitado (controlado por serviço).
    Validação: data_emissao ≤ data_validade (quando ambas informadas).
    """

    __tablename__ = "veiculo_documento"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_veiculo: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.veiculo.id"), nullable=False
    )
    tipo_documento: Mapped[str] = mapped_column(String(30), nullable=False)
    numero_documento: Mapped[str] = mapped_column(String(100), nullable=False)
    data_emissao: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_validade: Mapped[date | None] = mapped_column(Date, nullable=True)
    situacao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pendente"
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class VeiculoAvaliacao(Base):
    """Pareceres regulatórios de veículos (avaliação de conformidade, documentação, etc.).

    Resultado: pendente, aprovado, reprovado, condicional.
    Avaliador: referência para usuário (mesma tenant — validado no serviço).
    """

    __tablename__ = "veiculo_avaliacao"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_veiculo: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.veiculo.id"), nullable=False
    )
    id_usuario_avaliador: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    resultado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente")
    parecer: Mapped[str] = mapped_column(Text, nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_avaliacao: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class VeiculoVistoria(Base):
    """Vistorias regulatórias de veículos (inspeção de conformidade realizada por auditor).

    Resultado: pendente, aprovado, reprovado, condicional.
    Auditor: usuário (servidor) que realizou a vistoria (mesma tenant — validado no serviço).
    Renovação: data_validade opcional; renovada_de aponta para vistoria anterior (histórico).
    """

    __tablename__ = "veiculo_vistoria"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_veiculo: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.veiculo.id"), nullable=False
    )
    id_auditor: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    resultado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente")
    parecer: Mapped[str] = mapped_column(Text, nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_vistoria: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    data_validade: Mapped[date | None] = mapped_column(Date, nullable=True)
    renovada_de: Mapped[int | None] = mapped_column(
        ForeignKey("transporte_regulado.veiculo_vistoria.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Alvara(Base):
    """Alvarás/Autorizações de operação para permissionários/empresas.

    Vincula-se a permissionário E/OU empresa (ao menos um). numero_alvara é
    único por tenant entre não excluídos. Suporta data_validade para rastreamento
    de expiração (renovação será P2.1).
    """

    __tablename__ = "alvara"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_empresa: Mapped[int | None] = mapped_column(
        ForeignKey("transporte_regulado.empresa.id"), nullable=True
    )
    id_permissionario: Mapped[int | None] = mapped_column(
        ForeignKey("transporte_regulado.permissionario.id"), nullable=True
    )
    renovado_de: Mapped[int | None] = mapped_column(
        ForeignKey("transporte_regulado.alvara.id"), nullable=True
    )
    numero_alvara: Mapped[str] = mapped_column(String(40), nullable=False)
    data_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_validade: Mapped[date | None] = mapped_column(Date, nullable=True)
    tipo_servico: Mapped[str] = mapped_column(String(30), nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AlvaraDocumento(Base):
    """Documentos anexados a alvarás (contrato, comprovante, procuração, etc.).

    Metadados apenas (sem upload de arquivo nesta fase). Cada documento tem um
    tipo e referência para arquivo (path/filename). Soft-deleted com alvará (cascade).
    """

    __tablename__ = "alvara_documento"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_alvara: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.alvara.id", ondelete="CASCADE"), nullable=False
    )
    tipo_documento: Mapped[str] = mapped_column(String(30), nullable=False)
    arquivo: Mapped[str] = mapped_column(String(255), nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AlvaraResponsavel(Base):
    """Responsáveis (usuários do sistema) vinculados a alvarás.

    Um alvará pode ter múltiplos responsáveis (gerente, operador, autorizado, etc).
    Um usuário pode ser responsável por múltiplos alvarás. Soft-delete.
    """

    __tablename__ = "alvara_responsavel"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_alvara: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.alvara.id"), nullable=False
    )
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    cargo_funcao: Mapped[str | None] = mapped_column(String(100), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AlvaraVeiculo(Base):
    """Veículos vinculados a alvarás (P4).

    Um alvará pode estar operando com múltiplos veículos (ex: táxi amarelo com 2 táxis,
    mototáxi com 3 motos). Tabela de junção com metadados (data_vinculo).
    """

    __tablename__ = "alvara_veiculo"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_alvara: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.alvara.id"), nullable=False
    )
    id_veiculo: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.veiculo.id"), nullable=False
    )
    data_vinculo: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AlvaraAuditoria(Base):
    """Auditoria e histórico de mudanças de alvarás (P4).

    Trail append-only com snapshots de estado anterior/novo (JSONB) para rastreamento
    de quem alterou o quê e quando. Suporta diff visual para compliance/regulatório.
    """

    __tablename__ = "alvara_auditoria"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_alvara: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.alvara.id"), nullable=False
    )
    acao: Mapped[str] = mapped_column(String(100), nullable=False)
    dados_antigos: Mapped[dict | None] = mapped_column(type_=JSONB, nullable=True)
    dados_novos: Mapped[dict | None] = mapped_column(type_=JSONB, nullable=True)
    id_usuario: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# ==================== Recadastramento (P5.1) ============================


class RecadastramentoCiclo(Base):
    """Campanha de recadastramento do município.

    Não confundir com renovação de alvará (`Alvara.renovado_de`): renovação
    trata do DOCUMENTO de operação; recadastramento trata de o TITULAR
    continuar elegível. Um permissionário pode ter alvará válido e estar em
    falta com o recadastramento.

    `criterio_escalonamento`: `final_documento` (último dígito do CPF/CNPJ
    distribui em dez faixas na janela) ou `sem_escalonamento` (todos no
    `data_fim`). Nascimento e número de permissão foram descartados de
    propósito — são anuláveis, e empresa não tem nascimento.

    `situacao`: `rascunho` | `aberto` | `encerrado`.
    """

    __tablename__ = "recadastramento_ciclo"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    data_fim: Mapped[date] = mapped_column(Date, nullable=False)
    criterio_escalonamento: Mapped[str] = mapped_column(String(30), nullable=False)
    situacao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="rascunho"
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RecadastramentoConvocacao(Base):
    """Quem foi chamado num ciclo, e com que prazo.

    O vínculo com o regulado é o par de FKs anuláveis, **exatamente uma
    preenchida** — mesmo desenho do `Alvara` (que usa "ao menos uma"), e não
    `(tipo, id)` polimórfico: o par preserva integridade referencial de
    verdade. Garantido por `CHECK` no banco além da validação no serviço.

    `prazo_original` guarda o que a regra calculou. Sem ele o ajuste não é
    auditável — não dá para saber do que se afastou.
    """

    __tablename__ = "recadastramento_convocacao"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_ciclo: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.recadastramento_ciclo.id"), nullable=False
    )
    id_permissionario: Mapped[int | None] = mapped_column(
        ForeignKey("transporte_regulado.permissionario.id"), nullable=True
    )
    id_empresa: Mapped[int | None] = mapped_column(
        ForeignKey("transporte_regulado.empresa.id"), nullable=True
    )
    prazo: Mapped[date] = mapped_column(Date, nullable=False)
    prazo_original: Mapped[date] = mapped_column(Date, nullable=False)
    ajuste_justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)
    ajustado_por: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    ajustado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # `convocado` nesta fatia. P5.2 acrescenta o fechamento; P5.3, o atraso.
    situacao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="convocado"
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RecadastramentoItem(Base):
    """Item do catálogo de documentos exigidos no recadastramento.

    Catálogo **por tenant**, reusado por todo ciclo — molde do
    `pagamentos.checklist_item`. Amarrá-lo ao ciclo obrigaria a redigitar a
    lista toda campanha, e não haveria de onde herdar.

    `aplica_a`: `permissionario` | `empresa` | `ambos`. CNH é de pessoa,
    contrato social é de empresa; lista única deixaria metade dos itens sempre
    "não se aplica", e o operador marcaria por marcar.

    `ativo=False` tira o item das exigências novas **sem** apagar as marcações
    antigas, que continuam legíveis no histórico.
    """

    __tablename__ = "recadastramento_item"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    aplica_a: Mapped[str] = mapped_column(String(20), nullable=False)
    obrigatorio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RecadastramentoMarca(Base):
    """Marcação de um item do checklist numa convocação. **Log append-only.**

    Não existe linha "o item X está marcado": existe a sequência de marcações,
    e o estado corrente é a **mais recente** do par `(convocação, item)`.
    Desmarcar depois de marcar é informação — um servidor que voltou atrás
    deixou rastro, e sobrescrever a linha apagaria isso.

    Por isso a tabela **não** tem índice único em `(id_convocacao, id_item)`.
    A ausência é o desenho, não esquecimento.

    `id_usuario` é anulável, ao contrário do de `RecadastramentoDecisao`:
    marcação pode vir de rotina automática futura; decisão, nunca.
    """

    __tablename__ = "recadastramento_marca"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_convocacao: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.recadastramento_convocacao.id"), nullable=False
    )
    id_item: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.recadastramento_item.id"), nullable=False
    )
    marcado: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_usuario: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class RecadastramentoDecisao(Base):
    """Deferimento, indeferimento ou reabertura de uma convocação.

    Tabela, e não colunas na convocação — diferente do ajuste de prazo da P5.1.
    A diferença é que ajuste tem um estado corrente e um valor original,
    enquanto a decisão é uma **sequência**: indeferido, reaberto, deferido.
    Em coluna, cada reabertura apagaria a decisão anterior, que é justamente o
    histórico de que a P5.3 vai precisar.

    `RecadastramentoConvocacao.situacao` segue sendo o estado corrente,
    desnormalizado para a listagem não precisar de subconsulta por linha.
    """

    __tablename__ = "recadastramento_decisao"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_convocacao: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.recadastramento_convocacao.id"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    parecer: Mapped[str] = mapped_column(Text, nullable=False)
    # NOT NULL: decisão sem autor não é decisão.
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class RecadastramentoNotificacao(Base):
    """Que convocação foi notificada, quando, por quem, e com que notificação.

    Não guarda a mensagem: isso é da `aprimora_py.notificacao`, criada pelo
    motor existente, que já registra canal, destinatário, `enviado_em` e `erro`.
    Duplicar aqui produziria duas versões da verdade sobre o mesmo envio.

    **É log, não estado.** Sem único em `(id_convocacao, ...)`: segundo e
    terceiro aviso são linhas novas, e é justamente a contagem deles que
    justifica uma suspensão. Mesmo desenho de `RecadastramentoMarca`.

    A P5.3 dispara em lote e à mão. A automação por job, quando vier, escreve
    nesta mesma tabela — foi por isso que o registro entrou junto com o disparo
    manual, e não depois.
    """

    __tablename__ = "recadastramento_notificacao"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_convocacao: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.recadastramento_convocacao.id"), nullable=False
    )
    id_notificacao: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.notificacao.id"), nullable=False
    )
    # NOT NULL: envio em lote é ato de operador. Sem autor não há a quem
    # perguntar por que o município notificou.
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
