"""Gestão de Frota Pública — modelo de Veículo (fundação).

Tenant-scoped (cada prefeitura mantém sua própria frota). RLS em `frota.veiculo`
(ver migration 0031), no mesmo padrão de `protocolos.servico`.

Design: `situacao` é o estado de domínio do veículo (disponível / em uso /
manutenção / inativo / baixado); `excluido` é soft-delete. Não há flag `ativo`
separada — `situacao` já cobre disponibilidade (evita redundância).
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Veiculo(Base):
    __tablename__ = "veiculo"
    __table_args__ = {"schema": "frota"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    placa: Mapped[str] = mapped_column(String(8), nullable=False)
    renavam: Mapped[str | None] = mapped_column(String(20), nullable=True)
    chassi: Mapped[str | None] = mapped_column(String(30), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(60), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ano_fabricacao: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ano_modelo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cor: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tipo_veiculo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tipo_combustivel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    situacao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="disponivel"
    )
    # Soft-ref validada same-tenant no serviço (a FK garante integridade mas
    # NÃO filtra por tenant — mesmo critério de `servico.id_unidade_responsavel`).
    id_unidade_responsavel: Mapped[int | None] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=True
    )
    quilometragem_atual: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    data_aquisicao: Mapped[date | None] = mapped_column(Date, nullable=True)
    forma_posse: Mapped[str] = mapped_column(
        String(20), nullable=False, default="proprio"
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Motorista(Base):
    """Motorista / condutor da frota (PR Frota-2).

    `cpf` único por tenant entre não excluídos. `situacao` é o estado do
    condutor (ativo / afastado / inativo); `excluido` é soft-delete. `id_usuario`
    é opcional — vincula o motorista a um usuário do sistema, quando for o caso.
    """

    __tablename__ = "motorista"
    __table_args__ = {"schema": "frota"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cpf: Mapped[str] = mapped_column(String(11), nullable=False)
    matricula: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cnh_numero: Mapped[str] = mapped_column(String(11), nullable=False)
    cnh_categoria: Mapped[str] = mapped_column(String(5), nullable=False)
    cnh_validade: Mapped[date] = mapped_column(Date, nullable=False)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Soft-refs validadas same-tenant no serviço (a FK garante integridade mas
    # NÃO filtra por tenant — mesmo critério de `id_unidade_responsavel`).
    id_unidade: Mapped[int | None] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=True
    )
    id_usuario: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    situacao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ativo"
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SolicitacaoVeiculo(Base):
    """Solicitação de uso de veículo da frota (PR Frota-3).

    Máquina de estados em `status` (solicitada → aprovada/rejeitada/cancelada →
    em_uso → concluida), com transições guardadas no serviço de domínio.
    `id_usuario_solicitante` é sempre o usuário autenticado (definido
    server-side). `excluido` é soft-delete. Saída/retorno reais (PR Frota-5)
    movem o ciclo operacional aprovada → em_uso → concluida.
    """

    __tablename__ = "solicitacao_veiculo"
    __table_args__ = {"schema": "frota"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_usuario_solicitante: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    id_unidade_solicitante: Mapped[int | None] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=True
    )
    finalidade: Mapped[str] = mapped_column(String(255), nullable=False)
    destino: Mapped[str] = mapped_column(String(255), nullable=False)
    data_saida_prevista: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    data_retorno_prevista: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    quantidade_passageiros: Mapped[int] = mapped_column(Integer, nullable=False)
    necessita_motorista: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="solicitada"
    )
    justificativa_rejeicao: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Designação (PR Frota-4) — preenchida só quando status='aprovada'. 1:1, sem
    # histórico (redesignação sobrescreve). designador/data são server-side.
    id_veiculo_designado: Mapped[int | None] = mapped_column(
        ForeignKey("frota.veiculo.id"), nullable=True
    )
    id_motorista_designado: Mapped[int | None] = mapped_column(
        ForeignKey("frota.motorista.id"), nullable=True
    )
    id_usuario_designador: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    data_designacao: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    observacoes_designacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Saída/retorno real (PR Frota-5) — preenchidos no registro operacional.
    # datas/usuários são server-side; km validados no serviço. Saída move o
    # status para 'em_uso' e o veículo para 'em_uso'; retorno move para
    # 'concluida' e devolve o veículo a 'disponivel' atualizando a quilometragem.
    data_saida_real: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    data_retorno_real: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    km_saida: Mapped[int | None] = mapped_column(Integer, nullable=True)
    km_retorno: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observacoes_saida: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacoes_retorno: Mapped[str | None] = mapped_column(Text, nullable=True)
    id_usuario_registro_saida: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    id_usuario_registro_retorno: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class VeiculoDocumento(Base):
    """Documento administrativo do veículo (PR Frota-6).

    Controle simples de metadados — SEM upload/anexos. Cada veículo pode ter N
    documentos (CRLV, seguro, licenciamento, autorização, vistoria, outro) com
    `data_vencimento`; alertas de vencido/a vencer são calculados na aplicação.
    `status` (ativo/vencido/substituido/cancelado) é estado de domínio; `excluido`
    é soft-delete. `id_veiculo` é validado same-tenant no serviço (a FK garante
    integridade mas NÃO filtra por tenant)."""

    __tablename__ = "veiculo_documento"
    __table_args__ = {"schema": "frota"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_veiculo: Mapped[int] = mapped_column(
        ForeignKey("frota.veiculo.id"), nullable=False
    )
    tipo_documento: Mapped[str] = mapped_column(String(30), nullable=False)
    numero: Mapped[str | None] = mapped_column(String(60), nullable=True)
    orgao_emissor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    data_emissao: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ativo")
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class VeiculoManutencao(Base):
    """Manutenção preventiva/corretiva do veículo (Frota — operacional).

    Controle simples (SEM ordem de serviço complexa). `tipo`
    (preventiva/corretiva) e `status` (aberta/em_andamento/concluida/cancelada)
    são estado de domínio; `excluido` é soft-delete. `id_veiculo` validado
    same-tenant no serviço. Efeitos na `situacao` do veículo são guardados no
    serviço (abrir → 'manutencao' se 'disponivel'; concluir/cancelar →
    'disponivel' só se estava em 'manutencao')."""

    __tablename__ = "veiculo_manutencao"
    __table_args__ = {"schema": "frota"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_veiculo: Mapped[int] = mapped_column(
        ForeignKey("frota.veiculo.id"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    data_abertura: Mapped[date] = mapped_column(Date, nullable=False)
    data_prevista: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_conclusao: Mapped[date | None] = mapped_column(Date, nullable=True)
    km_atual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fornecedor: Mapped[str | None] = mapped_column(String(150), nullable=True)
    custo_estimado: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    custo_final: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="aberta")
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class VeiculoAbastecimento(Base):
    """Abastecimento do veículo (Frota — operacional).

    Registro simples (litros, valor, km, posto). NÃO altera a `situacao` do
    veículo; o serviço atualiza `quilometragem_atual` se o `km_atual` informado
    for maior. `id_veiculo`/`id_motorista` validados same-tenant no serviço.
    `excluido` é soft-delete."""

    __tablename__ = "veiculo_abastecimento"
    __table_args__ = {"schema": "frota"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_veiculo: Mapped[int] = mapped_column(
        ForeignKey("frota.veiculo.id"), nullable=False
    )
    id_motorista: Mapped[int | None] = mapped_column(
        ForeignKey("frota.motorista.id"), nullable=True
    )
    data_abastecimento: Mapped[date] = mapped_column(Date, nullable=False)
    km_atual: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_combustivel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    litros: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    posto: Mapped[str | None] = mapped_column(String(150), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class VeiculoVistoria(Base):
    """Vistoria/checklist interno do veículo (Frota — operacional).

    Checklist simples de campos fixos (Opção A): `tipo` (saida/retorno/periodica),
    `resultado` (aprovada/reprovada/com_ressalvas) e itens booleanos de
    conferência. NÃO altera a `situacao` do veículo (mesmo se 'reprovada' —
    decisão deste módulo). `id_veiculo` validado same-tenant no serviço;
    `excluido` é soft-delete."""

    __tablename__ = "veiculo_vistoria"
    __table_args__ = {"schema": "frota"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_veiculo: Mapped[int] = mapped_column(
        ForeignKey("frota.veiculo.id"), nullable=False
    )
    data_vistoria: Mapped[date] = mapped_column(Date, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    pneus_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    luzes_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    freios_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    documentacao_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    limpeza_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    equipamentos_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
