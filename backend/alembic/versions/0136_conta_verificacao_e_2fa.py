"""Conta: e-mail verificado, convite, "esqueci a senha" e 2FA por e-mail.

Revision ID: 0136
Revises: 0135
Create Date: 2026-11-06

Duas peças:

- `email_verificado_em` em `utils.usuario` e `utils.usuario_externo`. O
  DEFAULT é `NOW()` de propósito: toda conta que já existe — e toda conta
  criada por um caminho que não manda e-mail (seed, provisionamento do
  tenant, gov.br, admin que ainda informa senha) — nasce verificada. Só os
  dois caminhos novos gravam `NULL` explicitamente: o convite do servidor e o
  autocadastro do cidadão. Assim nenhuma conta existente fica trancada do
  lado de fora pela migration.

- `aprimora_py.token_conta`: os segredos de uso único da conta (convite,
  verificação de e-mail, redefinição de senha e o código de 2FA). Guarda só o
  HMAC do segredo, nunca o segredo. Uma linha aponta para um servidor OU para
  um cidadão (CHECK). `usado_em` preenchido = consumido ou substituído por um
  mais novo; `tentativas` conta erros de código (2FA tem limite).

RLS/grants: boilerplate padrão (GUC `app.tenant_id`, ENABLE + FORCE).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0136"
down_revision: str | Sequence[str] | None = "0135"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "aprimora_py"
GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"


def upgrade() -> None:
    for tabela in ("usuario", "usuario_externo"):
        op.add_column(
            tabela,
            sa.Column(
                "email_verificado_em",
                sa.DateTime(),
                nullable=True,
                server_default=sa.text("NOW()"),
            ),
            schema="utils",
        )

    op.create_table(
        "token_conta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False
        ),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column(
            "id_usuario_externo",
            sa.Integer(),
            sa.ForeignKey("utils.usuario_externo.id"),
            nullable=True,
        ),
        sa.Column("finalidade", sa.String(30), nullable=False),
        sa.Column("segredo_hash", sa.String(64), nullable=False),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("expira_em", sa.DateTime(), nullable=False),
        sa.Column("usado_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "finalidade IN ('convite', 'verificar_email', 'redefinir_senha', 'codigo_2fa')",
            name="ck_token_conta_finalidade",
        ),
        sa.CheckConstraint(
            "(id_usuario IS NULL) <> (id_usuario_externo IS NULL)",
            name="ck_token_conta_um_titular",
        ),
        schema=S,
    )
    op.create_index(
        "ux_token_conta_segredo_hash", "token_conta", ["segredo_hash"], unique=True, schema=S
    )
    op.create_index(
        "ix_token_conta_titular",
        "token_conta",
        ["tenant_id", "finalidade", "id_usuario", "id_usuario_externo"],
        schema=S,
    )

    op.execute(f"ALTER TABLE {S}.token_conta ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.token_conta FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_select ON {S}.token_conta "
        f"FOR SELECT USING (tenant_id = {GUC})"
    )
    op.execute(
        f"CREATE POLICY tenant_isolation_modify ON {S}.token_conta "
        f"FOR ALL USING (tenant_id = {GUC}) WITH CHECK (tenant_id = {GUC})"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.token_conta TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.token_conta_id_seq TO aprimora_app")


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {S}.token_conta")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {S}.token_conta")
    op.drop_index("ix_token_conta_titular", table_name="token_conta", schema=S)
    op.drop_index("ux_token_conta_segredo_hash", table_name="token_conta", schema=S)
    op.drop_table("token_conta", schema=S)
    for tabela in ("usuario", "usuario_externo"):
        op.drop_column(tabela, "email_verificado_em", schema="utils")
