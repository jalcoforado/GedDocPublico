"""Transporte Regulado P6b — linhas e itinerários.

Revision ID: 0092
Revises: 0091
Create Date: 2026-08-21

Spec: `docs/superpowers/specs/2026-08-21-transporte-p6b-linhas-design.md`.

Três tabelas. O que carrega a fatia:

- `ck_linha_tem_operador` — ao menos um operador (empresa e/ou permissionário),
  no banco e não só no serviço.
- `ux_linha_nome` — duas linhas com o mesmo nome no mesmo município são erro
  de digitação.
- `ux_linha_horario` — mesmo horário duas vezes no mesmo dia é erro de
  digitação, e a exclusividade mora no banco (lição P5.1/P6): duas requisições
  concorrentes passariam as duas por uma checagem de serviço.

`linha_parada.ordem` NÃO tem índice único, de propósito: um único parcial em
(id_linha, ordem) tornaria reordenar uma dança de colisões. A leitura ordena
por (ordem, id) — estável — e ordem duplicada é inofensiva.

Boilerplate de RLS completo nas três (GUC `app.tenant_id`, `current_setting`
com `true`, ENABLE + FORCE — os três detalhes da 0078). Sem GRANT para
`aprimora_worker`: nenhuma task Celery escreve aqui.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0092"
down_revision: str | Sequence[str] | None = "0091"
branch_labels = None
depends_on = None

S = "transporte_regulado"

GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"


def _rls(tabela: str) -> None:
    """Boilerplate de RLS + grants. Idêntico para as três tabelas."""
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
    # ------------------------------------------------------------- linha
    op.create_table(
        "linha",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("codigo", sa.String(40), nullable=True),
        # Sem CHECK, igual ao resto do módulo: vocabulário imposto pelo
        # Literal `TipoServico` na borda.
        sa.Column("tipo_servico", sa.String(30), nullable=False),
        # FKs "soft" para operador — coerência de tenant é do serviço.
        sa.Column(
            "id_empresa", sa.Integer(),
            sa.ForeignKey(f"{S}.empresa.id"), nullable=True,
        ),
        sa.Column(
            "id_permissionario", sa.Integer(),
            sa.ForeignKey(f"{S}.permissionario.id"), nullable=True,
        ),
        sa.Column("origem", sa.String(150), nullable=False),
        sa.Column("destino", sa.String(150), nullable=False),
        # Feminino: linha ativa/inativa. Lição ativo×ativa da P5.1.
        sa.Column(
            "situacao", sa.String(20), nullable=False, server_default="ativa",
        ),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("false"),
        ),
        sa.CheckConstraint(
            "id_empresa IS NOT NULL OR id_permissionario IS NOT NULL",
            name="ck_linha_tem_operador",
        ),
        sa.CheckConstraint(
            "situacao IN ('ativa', 'inativa')", name="ck_linha_situacao",
        ),
        schema=S,
    )
    op.create_index("ix_linha_tenant", "linha", ["tenant_id"], schema=S)
    op.create_index(
        "ix_linha_tenant_tipo", "linha", ["tenant_id", "tipo_servico"], schema=S,
    )
    op.execute(
        f"CREATE UNIQUE INDEX ux_linha_nome ON {S}.linha "
        f"(tenant_id, lower(nome)) WHERE excluido = false"
    )
    _rls("linha")

    # ------------------------------------------------------- linha_parada
    op.create_table(
        "linha_parada",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_linha", sa.Integer(),
            sa.ForeignKey(f"{S}.linha.id"), nullable=False,
        ),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("descricao", sa.String(200), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("false"),
        ),
        sa.CheckConstraint("ordem > 0", name="ck_linhaparada_ordem_positiva"),
        schema=S,
    )
    op.create_index(
        "ix_linhaparada_tenant_linha", "linha_parada",
        ["tenant_id", "id_linha"], schema=S,
    )
    _rls("linha_parada")

    # ------------------------------------------------------ linha_horario
    op.create_table(
        "linha_horario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_linha", sa.Integer(),
            sa.ForeignKey(f"{S}.linha.id"), nullable=False,
        ),
        # 0=segunda … 6=domingo.
        sa.Column("dia_semana", sa.SmallInteger(), nullable=False),
        sa.Column("partida", sa.Time(), nullable=False),
        # Sem atualizado_em: horário não se edita, se apaga e recria.
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("false"),
        ),
        sa.CheckConstraint(
            "dia_semana BETWEEN 0 AND 6", name="ck_linhahorario_dia",
        ),
        schema=S,
    )
    op.create_index(
        "ix_linhahorario_tenant_linha", "linha_horario",
        ["tenant_id", "id_linha"], schema=S,
    )
    op.execute(
        f"CREATE UNIQUE INDEX ux_linha_horario ON {S}.linha_horario "
        f"(id_linha, dia_semana, partida) WHERE excluido = false"
    )
    _rls("linha_horario")


def downgrade() -> None:
    # Ordem inversa: filhas antes da mãe.
    op.execute(f"DROP INDEX IF EXISTS {S}.ux_linha_horario")
    op.drop_index("ix_linhahorario_tenant_linha", table_name="linha_horario", schema=S)
    op.drop_table("linha_horario", schema=S)

    op.drop_index("ix_linhaparada_tenant_linha", table_name="linha_parada", schema=S)
    op.drop_table("linha_parada", schema=S)

    op.execute(f"DROP INDEX IF EXISTS {S}.ux_linha_nome")
    op.drop_index("ix_linha_tenant_tipo", table_name="linha", schema=S)
    op.drop_index("ix_linha_tenant", table_name="linha", schema=S)
    op.drop_table("linha", schema=S)
