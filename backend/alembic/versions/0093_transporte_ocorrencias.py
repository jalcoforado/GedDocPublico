"""Transporte Regulado P7 — ocorrências regulatórias.

Revision ID: 0093
Revises: 0092
Create Date: 2026-08-21

Spec: `docs/superpowers/specs/2026-08-21-transporte-p7-ocorrencias-design.md`.

Três tabelas. O que carrega a fatia:

- `ux_ocorrencia_tipo_nome` — mesmo padrão do `recadastramento_item` (P5.2):
  único parcial por `(tenant_id, lower(nome))` entre não excluídos.
- **Sem CHECK de alvo em `ocorrencia`.** Registro de balcão exige ao menos um
  alvo (permissionário/empresa/veículo); denúncia do portal pode nascer só
  com `referencia_alvo` textual — o cidadão raramente sabe o id de um
  permissionário, e o vínculo formal é trabalho da apuração
  (`vinculo_alvo`). Um CHECK condicionado à `origem` amarraria política de
  negócio mutável no schema; a regra que o banco não segura fica no serviço
  e provada por teste (ver spec §Modelo).
- `ocorrencia_andamento` é trilha **append-only**, mesmo desenho de
  `recadastramento_decisao` (P5.2/P5.3): decisão é ato na trilha
  cronológica, não coluna que se sobrescreve. Por isso não tem
  `atualizado_em` — ato praticado não se edita.

Boilerplate de RLS completo nas três (GUC `app.tenant_id`, `current_setting`
com `true`, ENABLE + FORCE — os três detalhes da 0078). Sem GRANT para
`aprimora_worker`: nenhuma task Celery escreve aqui (o e-mail da P7.2 nasce
pela via síncrona que o resto do serviço de notificações já usa).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0093"
down_revision: str | Sequence[str] | None = "0092"
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
    # ------------------------------------------------------- ocorrencia_tipo
    op.create_table(
        "ocorrencia_tipo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column(
            "ativo", sa.Boolean(), nullable=False, server_default=sa.text("true"),
        ),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("false"),
        ),
        schema=S,
    )
    op.create_index("ix_ocorrenciatipo_tenant", "ocorrencia_tipo", ["tenant_id"], schema=S)
    op.execute(
        f"CREATE UNIQUE INDEX ux_ocorrencia_tipo_nome ON {S}.ocorrencia_tipo "
        f"(tenant_id, lower(nome)) WHERE excluido = false"
    )
    _rls("ocorrencia_tipo")

    # ------------------------------------------------------------ ocorrencia
    op.create_table(
        "ocorrencia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_tipo", sa.Integer(),
            sa.ForeignKey(f"{S}.ocorrencia_tipo.id"), nullable=False,
        ),
        sa.Column("origem", sa.String(20), nullable=False),
        sa.Column("data_fato", sa.Date(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        # FKs "soft" para alvo — coerência de tenant é do serviço.
        sa.Column(
            "id_permissionario", sa.Integer(),
            sa.ForeignKey(f"{S}.permissionario.id"), nullable=True,
        ),
        sa.Column(
            "id_empresa", sa.Integer(),
            sa.ForeignKey(f"{S}.empresa.id"), nullable=True,
        ),
        sa.Column(
            "id_veiculo", sa.Integer(),
            sa.ForeignKey(f"{S}.veiculo.id"), nullable=True,
        ),
        sa.Column("referencia_alvo", sa.String(200), nullable=True),
        sa.Column(
            "id_cidadao", sa.Integer(),
            sa.ForeignKey("utils.usuario_externo.id"), nullable=True,
        ),
        sa.Column(
            "situacao", sa.String(20), nullable=False, server_default="registrada",
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
            "origem IN ('fiscalizacao', 'denuncia', 'outro')", name="ck_ocorrencia_origem",
        ),
        sa.CheckConstraint(
            "situacao IN ('registrada', 'em_apuracao', 'procedente', 'improcedente', 'arquivada')",
            name="ck_ocorrencia_situacao",
        ),
        # SEM CHECK de alvo — regra de serviço, ver docstring do módulo.
        schema=S,
    )
    op.create_index("ix_ocorrencia_tenant", "ocorrencia", ["tenant_id"], schema=S)
    op.create_index(
        "ix_ocorrencia_tenant_situacao", "ocorrencia", ["tenant_id", "situacao"], schema=S,
    )
    op.create_index(
        "ix_ocorrencia_tenant_tipo", "ocorrencia", ["tenant_id", "id_tipo"], schema=S,
    )
    op.create_index(
        "ix_ocorrencia_tenant_cidadao", "ocorrencia", ["tenant_id", "id_cidadao"], schema=S,
    )
    _rls("ocorrencia")

    # ---------------------------------------------------- ocorrencia_andamento
    op.create_table(
        "ocorrencia_andamento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_ocorrencia", sa.Integer(),
            sa.ForeignKey(f"{S}.ocorrencia.id"), nullable=False,
        ),
        sa.Column("ato", sa.String(20), nullable=False),
        sa.Column("parecer", sa.Text(), nullable=True),
        sa.Column(
            "id_usuario", sa.Integer(),
            sa.ForeignKey("utils.usuario.id"), nullable=True,
        ),
        # Sem atualizado_em: ato praticado não se edita.
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("false"),
        ),
        sa.CheckConstraint(
            "ato IN ('registro', 'inicio_apuracao', 'anotacao', 'vinculo_alvo', 'decisao')",
            name="ck_ocorrandamento_ato",
        ),
        schema=S,
    )
    op.create_index(
        "ix_ocorrandamento_tenant_ocorrencia", "ocorrencia_andamento",
        ["tenant_id", "id_ocorrencia"], schema=S,
    )
    _rls("ocorrencia_andamento")


def downgrade() -> None:
    # Ordem inversa: andamento → ocorrencia → tipo.
    op.drop_index(
        "ix_ocorrandamento_tenant_ocorrencia", table_name="ocorrencia_andamento", schema=S,
    )
    op.drop_table("ocorrencia_andamento", schema=S)

    op.drop_index("ix_ocorrencia_tenant_cidadao", table_name="ocorrencia", schema=S)
    op.drop_index("ix_ocorrencia_tenant_tipo", table_name="ocorrencia", schema=S)
    op.drop_index("ix_ocorrencia_tenant_situacao", table_name="ocorrencia", schema=S)
    op.drop_index("ix_ocorrencia_tenant", table_name="ocorrencia", schema=S)
    op.drop_table("ocorrencia", schema=S)

    op.execute(f"DROP INDEX IF EXISTS {S}.ux_ocorrencia_tipo_nome")
    op.drop_index("ix_ocorrenciatipo_tenant", table_name="ocorrencia_tipo", schema=S)
    op.drop_table("ocorrencia_tipo", schema=S)
