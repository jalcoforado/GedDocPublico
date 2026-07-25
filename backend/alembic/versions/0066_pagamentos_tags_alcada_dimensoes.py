"""Pagamentos v2.0 Fase 2 — tags de prioridade + dimensões de alçada.

Revision ID: 0066
Revises: 0065
Create Date: 2026-07-25

RF-CAD-05/06 (spec seção 4):
- tag_prioridade: rótulos de priorização por tenant (RLS+GRANTs).
- alcada: dimensões OPCIONAIS que restringem a alçada — id_unidade (órgão),
  id_fonte (fonte de recursos) e tipo_despesa (grupo de despesa). Todas nulas =
  alçada genérica (comportamento atual preservado).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0066"
down_revision: str | Sequence[str] | None = "0065"
branch_labels = None
depends_on = None
S = "pagamentos"


def upgrade() -> None:
    op.create_table(
        "tag_prioridade",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("nome", sa.String(50), nullable=False),
        sa.Column("cor", sa.String(20), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        schema=S,
    )
    op.create_index("ix_tagprio_tenant", "tag_prioridade", ["tenant_id", "ativa"], schema=S)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.tag_prioridade TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.tag_prioridade_id_seq TO aprimora_app")
    op.execute(f"ALTER TABLE {S}.tag_prioridade ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.tag_prioridade FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation_select ON {S}.tag_prioridade FOR SELECT "
               f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)")
    op.execute(f"CREATE POLICY tenant_isolation_modify ON {S}.tag_prioridade FOR ALL "
               f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int) "
               f"WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)")

    # dimensões opcionais da alçada
    op.add_column("alcada",
                  sa.Column("id_unidade", sa.Integer(),
                            sa.ForeignKey("utils.unidade_trabalho.id"), nullable=True), schema=S)
    op.add_column("alcada",
                  sa.Column("id_fonte", sa.Integer(),
                            sa.ForeignKey(f"{S}.fonte_recursos.id"), nullable=True), schema=S)
    op.add_column("alcada", sa.Column("tipo_despesa", sa.String(20), nullable=True), schema=S)


def downgrade() -> None:
    op.drop_column("alcada", "tipo_despesa", schema=S)
    op.drop_column("alcada", "id_fonte", schema=S)
    op.drop_column("alcada", "id_unidade", schema=S)

    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {S}.tag_prioridade")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {S}.tag_prioridade")
    op.drop_table("tag_prioridade", schema=S)
