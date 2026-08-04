"""Transporte Regulado P5.2 — atendimento e fechamento do recadastramento.

Revision ID: 0082
Revises: 0081
Create Date: 2026-08-04

Três tabelas em `transporte_regulado`:

- `recadastramento_item` — o catálogo de documentos exigidos, por tenant.
- `recadastramento_marca` — as marcações do checklist, **append-only**.
- `recadastramento_decisao` — deferimento, indeferimento e reabertura.

Spec: `docs/superpowers/specs/2026-08-04-transporte-p5-2-recadastramento-atendimento-design.md`.

Três decisões desta migration que o serviço sozinho não garante:

1. **`recadastramento_marca` NÃO tem índice único em `(id_convocacao, id_item)`**,
   e a ausência é deliberada. A tabela é um log: marcar, desmarcar e marcar de
   novo são três linhas, e o estado corrente é a mais recente. Um único ali
   transformaria o log em estado e apagaria o rastro de quem voltou atrás.

2. **`recadastramento_decisao.id_usuario` é NOT NULL.** Decisão sem autor não é
   decisão. Diferente de `recadastramento_marca.id_usuario`, que é anulável
   porque marcação pode vir de rotina futura sem usuário.

3. **Os `CHECK` de vocabulário** (`aplica_a`, `tipo`) existem além da validação
   do serviço, pelo mesmo motivo do `ck_recadconv_vinculo_exclusivo` da 0081: a
   validação protege quem passa pelo serviço; a constraint protege todos.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0082"
down_revision: str | Sequence[str] | None = "0081"
branch_labels = None
depends_on = None

S = "transporte_regulado"


def _enable_rls(t: str) -> None:
    """Boilerplate de RLS. Os três detalhes que já custaram um módulo inteiro
    (20 policies quebradas por 7 meses, corrigidas na 0078): o nome da GUC é
    `app.tenant_id`; o segundo argumento `true` do `current_setting` NÃO é
    opcional — sem ele a policy derruba a consulta em vez de negar; e `ENABLE`
    sem `FORCE` não protege enquanto o dono da tabela for o papel do runtime.
    """
    op.execute(f"ALTER TABLE {S}.{t} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.{t} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_select ON {S}.{t} FOR SELECT "
        f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)"
    )
    op.execute(
        f"CREATE POLICY tenant_isolation_modify ON {S}.{t} FOR ALL "
        f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int) "
        f"WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)"
    )


def _grant(t: str) -> None:
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.{t} TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.{t}_id_seq TO aprimora_app")


def upgrade() -> None:
    # ---------------------------------------------------------------- catálogo
    op.create_table(
        "recadastramento_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column("descricao", sa.String(200), nullable=False),
        # `permissionario` | `empresa` | `ambos`. String e não enum: o módulo
        # inteiro usa string para vocabulário, e acrescentar valor não deve
        # exigir migration de tipo.
        sa.Column("aplica_a", sa.String(20), nullable=False),
        sa.Column(
            "obrigatorio", sa.Boolean(), nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.CheckConstraint(
            "aplica_a IN ('permissionario', 'empresa', 'ambos')",
            name="ck_recaditem_aplica_a",
        ),
        schema=S,
    )
    op.create_index("ix_recaditem_tenant", "recadastramento_item", ["tenant_id"], schema=S)
    # Dois itens "CNH válida" no mesmo município é erro de digitação.
    op.execute(
        f"CREATE UNIQUE INDEX uq_recaditem_tenant_descricao ON {S}.recadastramento_item "
        f"(tenant_id, descricao) WHERE excluido = false"
    )
    _enable_rls("recadastramento_item")
    _grant("recadastramento_item")

    # ------------------------------------------------------- marcas (log puro)
    op.create_table(
        "recadastramento_marca",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_convocacao", sa.Integer(),
            sa.ForeignKey(f"{S}.recadastramento_convocacao.id"), nullable=False,
        ),
        sa.Column(
            "id_item", sa.Integer(),
            sa.ForeignKey(f"{S}.recadastramento_item.id"), nullable=False,
        ),
        sa.Column("marcado", sa.Boolean(), nullable=False),
        sa.Column("observacao", sa.String(255), nullable=True),
        # Anulável de propósito, ao contrário de `recadastramento_decisao`:
        # marcação pode vir de rotina automática futura; decisão, nunca.
        sa.Column(
            "id_usuario", sa.Integer(),
            sa.ForeignKey("utils.usuario.id"), nullable=True,
        ),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        schema=S,
    )
    # SEM índice único em (id_convocacao, id_item): ver o item 1 do docstring.
    op.create_index(
        "ix_recadmarca_tenant_convocacao", "recadastramento_marca",
        ["tenant_id", "id_convocacao"], schema=S,
    )
    _enable_rls("recadastramento_marca")
    _grant("recadastramento_marca")

    # ------------------------------------------------------------- decisões
    op.create_table(
        "recadastramento_decisao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_convocacao", sa.Integer(),
            sa.ForeignKey(f"{S}.recadastramento_convocacao.id"), nullable=False,
        ),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("parecer", sa.Text(), nullable=False),
        # NOT NULL: decisão sem autor não é decisão.
        sa.Column(
            "id_usuario", sa.Integer(),
            sa.ForeignKey("utils.usuario.id"), nullable=False,
        ),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "tipo IN ('deferimento', 'indeferimento', 'reabertura')",
            name="ck_recaddecisao_tipo",
        ),
        schema=S,
    )
    op.create_index(
        "ix_recaddecisao_tenant_convocacao", "recadastramento_decisao",
        ["tenant_id", "id_convocacao"], schema=S,
    )
    _enable_rls("recadastramento_decisao")
    _grant("recadastramento_decisao")


def downgrade() -> None:
    op.execute(f"DROP TABLE {S}.recadastramento_decisao CASCADE")
    op.execute(f"DROP TABLE {S}.recadastramento_marca CASCADE")
    op.execute(f"DROP TABLE {S}.recadastramento_item CASCADE")
