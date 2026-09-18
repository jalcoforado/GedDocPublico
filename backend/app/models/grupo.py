from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Grupo(Base):
    __tablename__ = "grupo"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_nivel: Mapped[int] = mapped_column(ForeignKey("utils.nivel.id"), nullable=False)
    id_sistema: Mapped[int] = mapped_column(ForeignKey("utils.sistema.id"), nullable=False)
    grupo: Mapped[str] = mapped_column(String(255), nullable=False)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Transacao(Base):
    __tablename__ = "transacao"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transacao: Mapped[str] = mapped_column(String(255), nullable=False)
    codigo: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class GrupoTransacao(Base):
    __tablename__ = "grupo_transacao"
    __table_args__ = (
        UniqueConstraint("id_grupo", "id_transacao", name="uk_grupo_transacao"),
        {"schema": "utils"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_grupo: Mapped[int] = mapped_column(ForeignKey("utils.grupo.id"), nullable=False)
    id_transacao: Mapped[int] = mapped_column(
        ForeignKey("utils.transacao.id"), nullable=False
    )
    inserir: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    atualizar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    excluir: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SistemaTransacao(Base):
    __tablename__ = "sistema_transacao"
    __table_args__ = (
        UniqueConstraint("id_sistema", "id_transacao", name="uk_sistema_transacao"),
        {"schema": "utils"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_sistema: Mapped[int] = mapped_column(ForeignKey("utils.sistema.id"), nullable=False)
    id_transacao: Mapped[int] = mapped_column(
        ForeignKey("utils.transacao.id"), nullable=False
    )
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class UsuarioGrupo(Base):
    __tablename__ = "usuario_grupo"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_usuario: Mapped[int] = mapped_column(ForeignKey("utils.usuario.id"), nullable=False)
    id_grupo: Mapped[int] = mapped_column(ForeignKey("utils.grupo.id"), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    app: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # E1 (benchmark SUiTE) — coluna LEGADA (já existia em ci/legacy-schema.sql,
    # com auditoria própria no PHP; nunca usada neste piloto — 0 de 104 linhas
    # preenchidas). Migration 0117 só acrescenta FK + índice, não a cria.
    # Nulo = vínculo global (concede em qualquer lotação, comportamento de
    # sempre); preenchido = só vale quando a lotação ATIVA da sessão for
    # esta. Os dois eixos se somam por união, nunca por interseção — ver
    # services/permissoes.py::load_permissions.
    id_unidade_trabalho: Mapped[int | None] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=True
    )


class UsuarioUnidadeTrabalho(Base):
    __tablename__ = "usuario_unidade_trabalho"
    __table_args__ = {"schema": "utils"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_usuario: Mapped[int] = mapped_column(ForeignKey("utils.usuario.id"), nullable=False)
    id_unidade_trabalho: Mapped[int] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=False
    )
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
