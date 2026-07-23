"""Pagamentos PAG-1 — schema `pagamentos` + cadastros básicos.

Revision ID: 0045
Revises: 0044
Create Date: 2026-07-13

Cria o schema `pagamentos` e as 6 tabelas de cadastro (credor, natureza_despesa,
fonte_recursos, conta_bancaria, contrato, alcada), todas tenant-scoped com RLS/GRANTs
no padrão de `transporte_regulado` (0041/0043). Semeia a transação `pagamento_cadastro`.
Órgão = utils.unidade_trabalho (sem entidade nova). Dados bancários do credor são
cifrados na aplicação (colunas *_cif Text).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0045"
down_revision: str | Sequence[str] | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "pagamentos"
TABELAS = ["credor", "natureza_despesa", "fonte_recursos", "conta_bancaria", "contrato", "alcada"]


def _enable_rls(qualified: str) -> None:
    op.execute(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_isolation_select ON {qualified}
            FOR SELECT USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)"""
    )
    op.execute(
        f"""CREATE POLICY tenant_isolation_modify ON {qualified}
            FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)"""
    )


def _grant(tabela: str) -> None:
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {SCHEMA}.{tabela} TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {SCHEMA}.{tabela}_id_seq TO aprimora_app")


def _cols_comuns() -> list:
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    ]


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    op.execute(f"GRANT USAGE ON SCHEMA {SCHEMA} TO aprimora_app")

    # ---- credor ----
    op.create_table(
        "credor",
        *_cols_comuns(),
        sa.Column("tipo_pessoa", sa.String(length=10), nullable=False),
        sa.Column("cnpj_cpf", sa.String(length=18), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("situacao_cadastral", sa.String(length=10), nullable=False, server_default=sa.text("'REGULAR'")),
        sa.Column("motivo_pendencia", sa.String(length=255), nullable=True),
        sa.Column("banco_cif", sa.Text(), nullable=True),
        sa.Column("agencia_cif", sa.Text(), nullable=True),
        sa.Column("conta_cif", sa.Text(), nullable=True),
        sa.Column("chave_pix_cif", sa.Text(), nullable=True),
        sa.CheckConstraint("tipo_pessoa IN ('FISICA','JURIDICA')", name="ck_credor_tipo_pessoa"),
        sa.CheckConstraint("situacao_cadastral IN ('REGULAR','PENDENTE','IRREGULAR')", name="ck_credor_situacao"),
        schema=SCHEMA,
    )
    op.create_index("uq_credor_tenant_doc", "credor", ["tenant_id", "cnpj_cpf"], unique=True,
                    schema=SCHEMA, postgresql_where=sa.text("excluido = false"))
    op.create_index("ix_credor_tenant_excluido", "credor", ["tenant_id", "excluido"], schema=SCHEMA)

    # ---- natureza_despesa ----
    op.create_table(
        "natureza_despesa",
        *_cols_comuns(),
        sa.Column("codigo", sa.String(length=20), nullable=False),
        sa.Column("descricao", sa.String(length=150), nullable=False),
        sa.Column("criticidade_padrao", sa.String(length=10), nullable=False, server_default=sa.text("'MEDIA'")),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.CheckConstraint("criticidade_padrao IN ('URGENTE','ALTA','MEDIA','BAIXA')", name="ck_natureza_criticidade"),
        schema=SCHEMA,
    )
    op.create_index("uq_natureza_tenant_codigo", "natureza_despesa", ["tenant_id", "codigo"], unique=True,
                    schema=SCHEMA, postgresql_where=sa.text("excluido = false"))
    op.create_index("ix_natureza_tenant_excluido", "natureza_despesa", ["tenant_id", "excluido"], schema=SCHEMA)

    # ---- fonte_recursos ----
    op.create_table(
        "fonte_recursos",
        *_cols_comuns(),
        sa.Column("codigo", sa.String(length=20), nullable=False),
        sa.Column("descricao", sa.String(length=200), nullable=False),
        sa.Column("grupos_despesa_permitidos", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        schema=SCHEMA,
    )
    op.create_index("uq_fonte_tenant_codigo", "fonte_recursos", ["tenant_id", "codigo"], unique=True,
                    schema=SCHEMA, postgresql_where=sa.text("excluido = false"))
    op.create_index("ix_fonte_tenant_excluido", "fonte_recursos", ["tenant_id", "excluido"], schema=SCHEMA)

    # ---- conta_bancaria ----
    op.create_table(
        "conta_bancaria",
        *_cols_comuns(),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("banco", sa.String(length=100), nullable=False),
        sa.Column("agencia", sa.String(length=20), nullable=False),
        sa.Column("conta", sa.String(length=30), nullable=False),
        sa.Column("id_fonte_recursos", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.fonte_recursos.id"), nullable=False),
        sa.Column("grupo_despesa", sa.String(length=20), nullable=False),
        sa.Column("saldo_minimo_alerta", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.CheckConstraint("grupo_despesa IN ('PESSOAL','CUSTEIO','INVESTIMENTO','DIVIDA','OUTRAS')", name="ck_conta_grupo"),
        schema=SCHEMA,
    )
    op.create_index("ix_conta_tenant_excluido", "conta_bancaria", ["tenant_id", "excluido"], schema=SCHEMA)
    op.create_index("ix_conta_fonte", "conta_bancaria", ["id_fonte_recursos"], schema=SCHEMA)

    # ---- contrato ----
    op.create_table(
        "contrato",
        *_cols_comuns(),
        sa.Column("numero", sa.String(length=50), nullable=False),
        sa.Column("id_credor", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.credor.id"), nullable=False),
        sa.Column("id_unidade", sa.Integer(), sa.ForeignKey("utils.unidade_trabalho.id"), nullable=False),
        sa.Column("objeto", sa.String(length=255), nullable=False),
        sa.Column("vigencia_inicio", sa.Date(), nullable=False),
        sa.Column("vigencia_fim", sa.Date(), nullable=False),
        sa.Column("valor_total", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("vigencia_fim >= vigencia_inicio", name="ck_contrato_vigencia"),
        schema=SCHEMA,
    )
    op.create_index("uq_contrato_tenant_numero", "contrato", ["tenant_id", "numero"], unique=True,
                    schema=SCHEMA, postgresql_where=sa.text("excluido = false"))
    op.create_index("ix_contrato_tenant_excluido", "contrato", ["tenant_id", "excluido"], schema=SCHEMA)
    op.create_index("ix_contrato_credor", "contrato", ["id_credor"], schema=SCHEMA)

    # ---- alcada ----
    op.create_table(
        "alcada",
        *_cols_comuns(),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=False),
        sa.Column("id_natureza", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.natureza_despesa.id"), nullable=True),
        sa.Column("valor_maximo", sa.Numeric(14, 2), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("uq_alcada_tenant_usuario_natureza", "alcada", ["tenant_id", "id_usuario", "id_natureza"],
                    unique=True, schema=SCHEMA, postgresql_where=sa.text("excluido = false"))
    op.create_index("ix_alcada_tenant_excluido", "alcada", ["tenant_id", "excluido"], schema=SCHEMA)

    for t in TABELAS:
        _grant(t)
        _enable_rls(f"{SCHEMA}.{t}")

    # transação de permissão (idempotente, padrão 0028/0044)
    op.execute(
        """INSERT INTO utils.transacao (transacao, codigo)
           SELECT 'Cadastros de Pagamentos', 'pagamento_cadastro'
           WHERE NOT EXISTS (SELECT 1 FROM utils.transacao WHERE codigo = 'pagamento_cadastro')"""
    )


def downgrade() -> None:
    op.execute("DELETE FROM utils.grupo_transacao WHERE id_transacao IN (SELECT id FROM utils.transacao WHERE codigo='pagamento_cadastro')")
    op.execute("DELETE FROM utils.sistema_transacao WHERE id_transacao IN (SELECT id FROM utils.transacao WHERE codigo='pagamento_cadastro')")
    op.execute("DELETE FROM utils.transacao WHERE codigo='pagamento_cadastro'")
    for t in reversed(TABELAS):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {SCHEMA}.{t}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {SCHEMA}.{t}")
        op.drop_table(t, schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
