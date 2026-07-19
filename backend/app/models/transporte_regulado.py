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
