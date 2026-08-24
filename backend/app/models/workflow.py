from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definition"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dsl: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    id_usuario_criador: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )


class WorkflowInstance(Base):
    """Execução concreta de um workflow (Fase 20a; polimórfica desde P8 D1).

    `entidade_tipo`/`entidade_id` identificam a entidade dona da instância
    (``processo``, ``ocorrencia``, ``alvara`` ou ``convocacao``). `id_processo`
    é preenchido só quando `entidade_tipo == 'processo'` e existe hoje por
    compatibilidade com o engine (Task 2 da fase P8) e com o índice único
    parcial antigo da 0008 — não é mais o identificador universal.
    """
    __tablename__ = "workflow_instance"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_workflow_definition: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.workflow_definition.id"), nullable=False
    )
    id_processo: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=True
    )
    entidade_tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    entidade_id: Mapped[int] = mapped_column(Integer, nullable=False)
    estado_atual: Mapped[str] = mapped_column(String(50), nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    iniciada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finalizada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    id_usuario_inicio: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )


class TipoProcessoWorkflow(Base):
    """Mapeia tipo_processo → workflow_definition slug (Fase 20b).

    Quando um processo é aberto com tipo_processo que tem mapeamento, o engine
    auto-instancia o workflow correspondente.
    """
    __tablename__ = "tipo_processo_workflow"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_tipo_processo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.tipo_processo.id"), nullable=False
    )
    slug_workflow: Mapped[str] = mapped_column(String(80), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WorkflowTransicaoLog(Base):
    """Auditoria append-only de transições executadas (Fase 20a)."""
    __tablename__ = "workflow_transicao_log"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_workflow_instance: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.workflow_instance.id"), nullable=False
    )
    estado_de: Mapped[str] = mapped_column(String(50), nullable=False)
    estado_para: Mapped[str] = mapped_column(String(50), nullable=False)
    transicao_label: Mapped[str] = mapped_column(String(120), nullable=False)
    id_usuario: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    contexto_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    executada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class WorkflowSlaAlerta(Base):
    """Alerta de SLA estourado em um estado de workflow (Fase 21).

    Gerado pela task beat `verificar_sla_workflows`. Dedup por
    (id_workflow_instance, estado) — um alerta por (instance, estado) por
    transição. Auto-resolvido quando a instance sai daquele estado.
    """
    __tablename__ = "workflow_sla_alerta"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_workflow_instance: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.workflow_instance.id"), nullable=False
    )
    estado: Mapped[str] = mapped_column(String(50), nullable=False)
    sla_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    dias_no_estado: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolvido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolucao: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notificado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
