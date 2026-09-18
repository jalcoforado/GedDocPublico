"""Favoritos e marcadores de processo (F5, benchmark SUiTE)

Revision ID: 0114
Revises: 0113
Create Date: 2026-09-17

Três tabelas novas em `aprimora_py` (mesmo schema de `workflow_instance` e
outras tabelas novas ligadas a processo — `protocolos.*` é schema legado):

- `processo_favorito` — lista de acompanhamento PESSOAL. O propósito (só
  ficou claro numa captura do benchmark): o processo continua visível para
  quem favoritou mesmo depois de sair do seu setor. Toggle simples, sem
  soft-delete — desfavoritar apaga a linha, não há valor de auditoria em
  reter "já foi favorito".
- `marcador` — catálogo de etiquetas coloridas. Por TENANT (visível em
  processo de qualquer unidade, decisão do Jorge), com `id_unidade_trabalho`
  nullable registrando qual unidade administra aquela etiqueta (a
  administração é setorial; a visibilidade, não). Soft-delete: marcador
  removido não pode apagar a associação histórica de quem já foi marcado.
- `processo_marcador` — vínculo N:N. Toggle como o favorito (hard-delete ao
  desmarcar); a permanência que importa é a do catálogo (`marcador`), não a
  de cada marcação individual.

RLS/grants: boilerplate padrão (GUC `app.tenant_id`, `current_setting` com o
segundo argumento `true`, ENABLE + FORCE).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0114"
down_revision: str | Sequence[str] | None = "0113"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "aprimora_py"
GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"


def _rls(tabela: str) -> None:
    op.execute(f"ALTER TABLE {S}.{tabela} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.{tabela} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_select ON {S}.{tabela} "
        f"FOR SELECT USING (tenant_id = {GUC})"
    )
    op.execute(
        f"CREATE POLICY tenant_isolation_modify ON {S}.{tabela} "
        f"FOR ALL USING (tenant_id = {GUC}) WITH CHECK (tenant_id = {GUC})"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.{tabela} TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.{tabela}_id_seq TO aprimora_app")


def upgrade() -> None:
    # ------------------------------------------------------ processo_favorito
    op.create_table(
        "processo_favorito",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_usuario", sa.Integer, sa.ForeignKey("utils.usuario.id"), nullable=False),
        sa.Column("id_processo", sa.Integer, sa.ForeignKey("protocolos.processo.id"), nullable=False),
        sa.Column("criado_em", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        schema=S,
    )
    op.create_index(
        "ix_processo_favorito_tenant_usuario",
        "processo_favorito", ["tenant_id", "id_usuario"], schema=S,
    )
    op.create_unique_constraint(
        "uq_processo_favorito_usuario_processo",
        "processo_favorito", ["tenant_id", "id_usuario", "id_processo"], schema=S,
    )
    _rls("processo_favorito")

    # ------------------------------------------------------------- marcador
    op.create_table(
        "marcador",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column(
            "id_unidade_trabalho", sa.Integer,
            sa.ForeignKey("utils.unidade_trabalho.id"), nullable=True,
        ),
        sa.Column("nome", sa.String(60), nullable=False),
        sa.Column("cor", sa.String(7), nullable=False),  # "#RRGGBB"
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("excluido", sa.Boolean, nullable=False, server_default=sa.false()),
        schema=S,
    )
    op.create_index("ix_marcador_tenant", "marcador", ["tenant_id"], schema=S)
    op.execute(
        f"CREATE UNIQUE INDEX uq_marcador_tenant_nome ON {S}.marcador "
        f"(tenant_id, lower(nome)) WHERE excluido = false"
    )
    _rls("marcador")

    # ------------------------------------------------------- processo_marcador
    op.create_table(
        "processo_marcador",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_processo", sa.Integer, sa.ForeignKey("protocolos.processo.id"), nullable=False),
        sa.Column("id_marcador", sa.Integer, sa.ForeignKey(f"{S}.marcador.id"), nullable=False),
        sa.Column("id_usuario", sa.Integer, sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        schema=S,
    )
    op.create_index(
        "ix_processo_marcador_processo",
        "processo_marcador", ["tenant_id", "id_processo"], schema=S,
    )
    op.create_unique_constraint(
        "uq_processo_marcador_processo_marcador",
        "processo_marcador", ["tenant_id", "id_processo", "id_marcador"], schema=S,
    )
    _rls("processo_marcador")


def downgrade() -> None:
    op.drop_table("processo_marcador", schema=S)
    op.drop_table("marcador", schema=S)
    op.drop_table("processo_favorito", schema=S)
