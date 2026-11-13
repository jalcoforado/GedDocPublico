"""Relatório montado pela própria pessoa: relatórios salvos (SI-35).

Revision ID: 0138
Revises: 0137
Create Date: 2026-11-12

`aprimora_py.relatorio_salvo` guarda só a DEFINIÇÃO do relatório (JSONB:
colunas, filtros, período, agrupamento, ordem), nunca dados — cada abertura
roda a consulta de novo com o sigilo de quem abre.

Pessoal: a linha é de `(tenant_id, id_usuario)`. Nome único por pessoa, sem
diferença de maiúsculas (`lower(nome)`). Sem soft-delete: como o favorito,
não é registro de negócio; excluir apaga.

RLS/grants: boilerplate padrão (GUC `app.tenant_id`, ENABLE + FORCE).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0138"
down_revision: str | Sequence[str] | None = "0137"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "aprimora_py"
GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"


def upgrade() -> None:
    op.create_table(
        "relatorio_salvo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False
        ),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("definicao", postgresql.JSONB(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        schema=S,
    )
    op.execute(
        f"CREATE UNIQUE INDEX ux_relatorio_salvo_nome ON {S}.relatorio_salvo "
        "(tenant_id, id_usuario, lower(nome))"
    )

    op.execute(f"ALTER TABLE {S}.relatorio_salvo ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.relatorio_salvo FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_select ON {S}.relatorio_salvo "
        f"FOR SELECT USING (tenant_id = {GUC})"
    )
    op.execute(
        f"CREATE POLICY tenant_isolation_modify ON {S}.relatorio_salvo "
        f"FOR ALL USING (tenant_id = {GUC}) WITH CHECK (tenant_id = {GUC})"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.relatorio_salvo TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.relatorio_salvo_id_seq TO aprimora_app")


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {S}.relatorio_salvo")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {S}.relatorio_salvo")
    op.execute(f"DROP INDEX IF EXISTS {S}.ux_relatorio_salvo_nome")
    op.drop_table("relatorio_salvo", schema=S)
