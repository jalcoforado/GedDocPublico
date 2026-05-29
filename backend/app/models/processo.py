from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Acao(Base):
    __tablename__ = "acao"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flag: Mapped[str] = mapped_column(String(100), nullable=False)
    acao: Mapped[str] = mapped_column(String(100), nullable=False)
    status_acao: Mapped[str] = mapped_column(String(60), nullable=False)
    status_movimentacao: Mapped[str] = mapped_column(String(60), nullable=False)
    texto_acao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Prioridade(Base):
    __tablename__ = "prioridade"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prioridade: Mapped[str] = mapped_column(String(100), nullable=False)
    fator: Mapped[int] = mapped_column(Integer, nullable=False)
    cor: Mapped[str] = mapped_column(String(10), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Processo(Base):
    __tablename__ = "processo"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_assunto: Mapped[int] = mapped_column(ForeignKey("protocolos.assunto.id"), nullable=False)
    virtual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    data_hora_abertura: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    numero_origem: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_processo: Mapped[str] = mapped_column(String(255), nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    id_unidade_proprietaria: Mapped[int] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=False
    )
    corpo: Mapped[str | None] = mapped_column(Text, nullable=True)
    id_manifestante: Mapped[int] = mapped_column(
        ForeignKey("protocolos.manifestante.id"), nullable=False
    )
    id_processo_pai: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Sigilo gradual (LAI). `nivel_sigilo` é a fonte da verdade; `publico` é
    # coluna gerada (= nivel == 'ostensivo'), read-only via ORM.
    nivel_sigilo: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ostensivo"
    )
    publico: Mapped[bool] = mapped_column(
        Boolean, Computed("nivel_sigilo = 'ostensivo'", persisted=True), nullable=False
    )
    sigilo_fundamento_legal: Mapped[str | None] = mapped_column(Text, nullable=True)
    sigilo_autoridade: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sigilo_prazo_anos: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    sigilo_data_classificacao: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    sigilo_data_desclassificacao: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    sigilo_classificado_por: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    migrado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    externo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    id_local_atual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_ultima_movimentacao: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_usuario: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Protocolo P1
    id_especie_documental: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.especie_documental.id"), nullable=True
    )
    canal_entrada: Mapped[str | None] = mapped_column(String(20), nullable=True)
    data_recepcao: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Protocolo P4
    id_ccd_classe: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.ccd_classe.id"), nullable=True
    )
    # Protocolo P2 — NUP federal (opt-in por tenant)
    nup: Mapped[str | None] = mapped_column(String(25), nullable=True)
    numero_sequencial_orgao: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # PR 4b — vínculo com a Carta de Serviços (soft-link; null em processos não
    # originados de serviço).
    id_servico: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.servico.id"), nullable=True
    )


class Movimentacao(Base):
    __tablename__ = "movimentacao"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_processo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=False
    )
    id_unidade_responsavel: Mapped[int] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=False
    )
    id_acao: Mapped[int] = mapped_column(ForeignKey("protocolos.acao.id"), nullable=False)
    id_despacho: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_encaminhamento: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_arquivamento: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_usuario: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    data_hora_movimentacao: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Despacho(Base):
    __tablename__ = "despacho"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_processo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=False
    )
    despacho: Mapped[str] = mapped_column(Text, nullable=False)
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    id_movimentacao: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Encaminhamento(Base):
    __tablename__ = "encaminhamento"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_processo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=False
    )
    id_unidade_origem: Mapped[int | None] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=True
    )
    id_unidade_destino: Mapped[int] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=False
    )
    id_prioridade: Mapped[int] = mapped_column(
        ForeignKey("protocolos.prioridade.id"), nullable=False
    )
    quantidade_folhas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data_prazo: Mapped[date | None] = mapped_column(Date, nullable=True)
    externo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recebido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    data_hora_recebimento: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    id_movimentacao: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Arquivamento(Base):
    __tablename__ = "arquivamento"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_status_arquivamento: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    local: Mapped[str | None] = mapped_column(String(255), nullable=True)
    arquivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Anexo(Base):
    __tablename__ = "anexo"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_tipo_anexo: Mapped[int | None] = mapped_column(
        ForeignKey("protocolos.tipo_anexo.id"), nullable=True
    )
    publico: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    id_usuario: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    e_doc: Mapped[str | None] = mapped_column(String(25), nullable=True)
    descricao: Mapped[str | None] = mapped_column(String(512), nullable=True)
    qtd_paginas: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AnexoProcesso(Base):
    __tablename__ = "anexo_processo"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_processo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=False
    )
    id_anexo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.anexo.id"), nullable=False
    )
    id_movimentacao: Mapped[int] = mapped_column(
        ForeignKey("protocolos.movimentacao.id"), nullable=False
    )
    id_usuario: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ordem: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anexo_herdado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Fase P6 — Desentranhamento (remoção formal de anexo de processo já formado)
    desentranhado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    id_usuario_desentranhamento: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True
    )
    motivo_desentranhamento: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    autoridade_desentranhamento: Mapped[str | None] = mapped_column(String(300), nullable=True)
