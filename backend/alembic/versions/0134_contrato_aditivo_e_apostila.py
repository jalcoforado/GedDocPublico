"""Contratos G1 — `pagamentos.contrato_aditivo` e `pagamentos.contrato_apostila`.

Revision ID: 0134
Revises: 0133
Create Date: 2026-10-08

Spec: `docs/superpowers/specs/2026-10-08-contratos-g1-modulo-e-contrato-design.md`
(§2.2, §2.3 e §3.2).

**Por que no schema `pagamentos`, e não num `contratos` novo.** O desenho
previa schema próprio. Na implementação ficou claro o custo: a 0078 distribui
`USAGE`/`CREATE`, grants de tabela e `ALTER DEFAULT PRIVILEGES` para
`aprimora_migrator` e `aprimora_worker` por uma lista fechada de schemas
(`SCHEMAS_NEGOCIO`), e `tests/test_rls_papeis_minimos.py` varre a mesma lista.
Schema novo teria de repetir tudo isso à mão — e o que esquecesse só quebraria
no seed seguinte, longe da causa, que é exatamente o defeito que aquela
migration foi escrita para impedir. Ficando ao lado de `pagamentos.contrato`,
as tabelas herdam as default privileges e entram sozinhas na varredura de RLS.
É a mesma razão da decisão Q1: o dono é quem tem a transação.

Aditivo: os seis tipos são os códigos do campo 7 da tabela 511 do SIM, e o
valor é sempre a diferença POSITIVA (inclusive em redução) — é como o Tribunal
recebe. Os CHECKs casam tipo com valor e com a presença da nova data final:
o service valida antes, mas o banco é a última linha.

Apostila: o que o art. 136 da Lei 14.133 dispensa de termo aditivo.

Grant só para `aprimora_app`: nenhuma task Celery escreve aqui na G1.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0134"
down_revision: str | Sequence[str] | None = "0133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "pagamentos"
TABELAS = ("contrato_aditivo", "contrato_apostila")

_TENANT = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int"


def _cols_comuns() -> list:
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_contrato", sa.Integer(), sa.ForeignKey(f"{S}.contrato.id"), nullable=False),
        sa.Column("sequencial", sa.Integer(), nullable=False),
        sa.Column("id_usuario_registro", sa.Integer(), sa.ForeignKey("utils.usuario.id"),
                  nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    ]


def _rls_e_grants(tabela: str) -> None:
    q = f"{S}.{tabela}"
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {q} TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {q}_id_seq TO aprimora_app")
    op.execute(f"ALTER TABLE {q} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {q} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_select ON {q} FOR SELECT USING ({_TENANT})")
    op.execute(
        f"CREATE POLICY tenant_isolation_modify ON {q} FOR ALL "
        f"USING ({_TENANT}) WITH CHECK ({_TENANT})")


def upgrade() -> None:
    op.create_table(
        "contrato_aditivo",
        *_cols_comuns(),
        sa.Column("numero", sa.String(15), nullable=False),
        sa.Column("exercicio", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(2), nullable=False),
        sa.Column("data_assinatura", sa.Date(), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("nova_vigencia_fim", sa.Date(), nullable=True),
        sa.Column("justificativa", sa.String(1000), nullable=True),
        sa.Column("situacao", sa.String(10), nullable=False, server_default="RASCUNHO"),
        sa.Column("motivo_anulacao", sa.String(500), nullable=True),
        sa.Column("pncp_id", sa.String(25), nullable=True),
        sa.Column("pncp_publicado_em", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "tipo IN ('AA', 'AR', 'AP', 'PA', 'PR', 'RE')", name="ck_contrato_aditivo_tipo"),
        sa.CheckConstraint(
            "situacao IN ('RASCUNHO', 'VIGENTE', 'ANULADO')",
            name="ck_contrato_aditivo_situacao"),
        # Aditivo só de prazo vai com zero; todos os outros, diferença positiva.
        sa.CheckConstraint(
            "(tipo = 'AP' AND valor = 0) OR (tipo <> 'AP' AND valor > 0)",
            name="ck_contrato_aditivo_tipo_valor"),
        # Acréscimo e redução puros não mexem na vigência; os demais exigem a nova data.
        sa.CheckConstraint(
            "(tipo IN ('AA', 'AR') AND nova_vigencia_fim IS NULL) "
            "OR (tipo IN ('AP', 'PA', 'PR', 'RE') AND nova_vigencia_fim IS NOT NULL)",
            name="ck_contrato_aditivo_tipo_vigencia"),
        schema=S,
    )
    op.create_index(
        "uq_contrato_aditivo_sequencial", "contrato_aditivo", ["id_contrato", "sequencial"],
        unique=True, schema=S, postgresql_where=sa.text("excluido = false"))
    op.create_index(
        "uq_contrato_aditivo_tenant_exercicio_numero", "contrato_aditivo",
        ["tenant_id", "exercicio", "numero"], unique=True, schema=S,
        postgresql_where=sa.text("excluido = false"))
    op.create_index(
        "ix_contrato_aditivo_tenant_contrato", "contrato_aditivo",
        ["tenant_id", "id_contrato"], schema=S)

    op.create_table(
        "contrato_apostila",
        *_cols_comuns(),
        sa.Column("tipo", sa.String(15), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("valor_delta", sa.Numeric(14, 2), nullable=True),
        sa.Column("indice", sa.String(60), nullable=True),
        sa.Column("descricao", sa.String(1000), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('REAJUSTE', 'REPACTUACAO', 'RAZAO_SOCIAL', 'DOTACAO', 'OUTRO')",
            name="ck_contrato_apostila_tipo"),
        # Só reajuste e repactuação mudam valor — e nesses o delta é obrigatório.
        sa.CheckConstraint(
            "(tipo IN ('REAJUSTE', 'REPACTUACAO') AND valor_delta IS NOT NULL) "
            "OR (tipo NOT IN ('REAJUSTE', 'REPACTUACAO') AND valor_delta IS NULL)",
            name="ck_contrato_apostila_tipo_valor"),
        schema=S,
    )
    op.create_index(
        "uq_contrato_apostila_sequencial", "contrato_apostila", ["id_contrato", "sequencial"],
        unique=True, schema=S, postgresql_where=sa.text("excluido = false"))
    op.create_index(
        "ix_contrato_apostila_tenant_contrato", "contrato_apostila",
        ["tenant_id", "id_contrato"], schema=S)

    for tabela in TABELAS:
        _rls_e_grants(tabela)


def downgrade() -> None:
    for tabela in reversed(TABELAS):
        q = f"{S}.{tabela}"
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {q}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {q}")
        op.execute(f"ALTER TABLE {q} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {q} DISABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON {q}_id_seq FROM aprimora_app")
        op.execute(f"REVOKE ALL ON {q} FROM aprimora_app")

    op.drop_index("ix_contrato_apostila_tenant_contrato", table_name="contrato_apostila", schema=S)
    op.drop_index("uq_contrato_apostila_sequencial", table_name="contrato_apostila", schema=S)
    op.drop_table("contrato_apostila", schema=S)

    op.drop_index("ix_contrato_aditivo_tenant_contrato", table_name="contrato_aditivo", schema=S)
    op.drop_index(
        "uq_contrato_aditivo_tenant_exercicio_numero", table_name="contrato_aditivo", schema=S)
    op.drop_index("uq_contrato_aditivo_sequencial", table_name="contrato_aditivo", schema=S)
    op.drop_table("contrato_aditivo", schema=S)
