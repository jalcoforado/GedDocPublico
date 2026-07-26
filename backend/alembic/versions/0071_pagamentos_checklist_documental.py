"""Pagamentos v2.0 A6.2 — checklist documental parametrizável (RF-VAL-01/06).

Revision ID: 0071
Revises: 0070
Create Date: 2026-07-26

RF-VAL-01/06: checklist de documentos obrigatórios por tipo de despesa, com
histórico de marcações. Duas tabelas no schema `pagamentos` (RLS + GRANTs):
- checklist_item: itens do checklist (parametrizáveis; opcionalmente escopados
  por natureza; obrigatório ou não).
- debito_checklist_marca: log append-only das marcações por débito (o estado
  atual é a marcação mais recente de cada item).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0071"
down_revision: str | Sequence[str] | None = "0070"
branch_labels = None
depends_on = None
S = "pagamentos"


def _enable_rls(t: str) -> None:
    op.execute(f"ALTER TABLE {S}.{t} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.{t} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation_select ON {S}.{t} FOR SELECT "
               f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)")
    op.execute(f"CREATE POLICY tenant_isolation_modify ON {S}.{t} FOR ALL "
               f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int) "
               f"WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)")


def _grant(t: str) -> None:
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.{t} TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.{t}_id_seq TO aprimora_app")


def upgrade() -> None:
    op.create_table(
        "checklist_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("descricao", sa.String(200), nullable=False),
        sa.Column("obrigatorio", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("id_natureza", sa.Integer(), sa.ForeignKey(f"{S}.natureza_despesa.id"), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        schema=S,
    )
    op.create_index("ix_checklistitem_tenant", "checklist_item", ["tenant_id"], schema=S)
    _enable_rls("checklist_item")
    _grant("checklist_item")

    op.create_table(
        "debito_checklist_marca",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_debito", sa.Integer(), sa.ForeignKey(f"{S}.debito.id"), nullable=False),
        sa.Column("id_checklist_item", sa.Integer(),
                  sa.ForeignKey(f"{S}.checklist_item.id"), nullable=False),
        sa.Column("marcado", sa.Boolean(), nullable=False),
        sa.Column("observacao", sa.String(255), nullable=True),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        schema=S,
    )
    op.create_index("ix_debchecklist_tenant_debito", "debito_checklist_marca",
                    ["tenant_id", "id_debito"], schema=S)
    _enable_rls("debito_checklist_marca")
    _grant("debito_checklist_marca")


def downgrade() -> None:
    op.execute(f"DROP TABLE {S}.debito_checklist_marca CASCADE")
    op.execute(f"DROP TABLE {S}.checklist_item CASCADE")
