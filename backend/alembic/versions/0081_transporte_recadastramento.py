"""Transporte Regulado P5.1 — ciclo de recadastramento e convocação.

Revision ID: 0081
Revises: 0080
Create Date: 2026-08-04

Duas tabelas em `transporte_regulado`:

- `recadastramento_ciclo` — a campanha do município, com janela e critério de
  escalonamento.
- `recadastramento_convocacao` — quem foi chamado, com que prazo.

Spec: `docs/superpowers/specs/2026-08-04-transporte-p5-1-recadastramento-ciclo-design.md`.

Duas decisões desta migration que o serviço sozinho não garante:

1. **O vínculo com o regulado é `CHECK` no banco**, não só validação no
   serviço. São duas FKs anuláveis (`id_permissionario`, `id_empresa`) com
   exatamente uma preenchida — o precedente é o `Alvara`, que usa o mesmo par
   com "ao menos uma". Validação de serviço protege o caminho que passa por
   ele; a constraint protege todos, inclusive o script de correção que alguém
   vai rodar às pressas.

2. **A idempotência da geração é índice único parcial**, não `if not exists`
   no Python. Duas execuções concorrentes do endpoint de geração passariam as
   duas pela checagem e inseririam em duplicidade; o índice recusa a segunda.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0081"
down_revision: str | Sequence[str] | None = "0080"
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
    op.create_table(
        "recadastramento_ciclo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("data_inicio", sa.Date(), nullable=False),
        sa.Column("data_fim", sa.Date(), nullable=False),
        # `final_documento` | `sem_escalonamento`. String e não enum: o módulo
        # inteiro usa string para estado, e acrescentar critério não deve exigir
        # migration de tipo.
        sa.Column("criterio_escalonamento", sa.String(30), nullable=False),
        sa.Column(
            "situacao", sa.String(20), nullable=False,
            server_default=sa.text("'rascunho'"),
        ),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.CheckConstraint("data_inicio <= data_fim", name="ck_recadciclo_janela"),
        schema=S,
    )
    op.create_index(
        "ix_recadciclo_tenant", "recadastramento_ciclo", ["tenant_id"], schema=S
    )
    # Dois ciclos "Recadastramento 2026" no mesmo município é erro de digitação,
    # não caso de uso.
    op.execute(
        f"CREATE UNIQUE INDEX uq_recadciclo_tenant_nome ON {S}.recadastramento_ciclo "
        f"(tenant_id, nome) WHERE excluido = false"
    )
    _enable_rls("recadastramento_ciclo")
    _grant("recadastramento_ciclo")

    op.create_table(
        "recadastramento_convocacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_ciclo", sa.Integer(),
            sa.ForeignKey(f"{S}.recadastramento_ciclo.id"), nullable=False,
        ),
        # Exatamente uma das duas — ver o CHECK abaixo.
        sa.Column(
            "id_permissionario", sa.Integer(),
            sa.ForeignKey(f"{S}.permissionario.id"), nullable=True,
        ),
        sa.Column(
            "id_empresa", sa.Integer(),
            sa.ForeignKey(f"{S}.empresa.id"), nullable=True,
        ),
        sa.Column("prazo", sa.Date(), nullable=False),
        # Preservado para que o ajuste seja auditável: sem ele não dá para saber
        # o que a regra tinha dado.
        sa.Column("prazo_original", sa.Date(), nullable=False),
        sa.Column("ajuste_justificativa", sa.Text(), nullable=True),
        sa.Column(
            "ajustado_por", sa.Integer(),
            sa.ForeignKey("utils.usuario.id"), nullable=True,
        ),
        sa.Column("ajustado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "situacao", sa.String(20), nullable=False,
            server_default=sa.text("'convocado'"),
        ),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.CheckConstraint(
            "(id_permissionario IS NOT NULL) <> (id_empresa IS NOT NULL)",
            name="ck_recadconv_vinculo_exclusivo",
        ),
        schema=S,
    )
    op.create_index(
        "ix_recadconv_tenant_ciclo", "recadastramento_convocacao",
        ["tenant_id", "id_ciclo"], schema=S,
    )
    # A idempotência da geração mora AQUI, não no `if not exists` do Python:
    # duas execuções concorrentes passariam as duas pela checagem.
    op.execute(
        f"CREATE UNIQUE INDEX uq_recadconv_ciclo_permissionario "
        f"ON {S}.recadastramento_convocacao (id_ciclo, id_permissionario) "
        f"WHERE excluido = false AND id_permissionario IS NOT NULL"
    )
    op.execute(
        f"CREATE UNIQUE INDEX uq_recadconv_ciclo_empresa "
        f"ON {S}.recadastramento_convocacao (id_ciclo, id_empresa) "
        f"WHERE excluido = false AND id_empresa IS NOT NULL"
    )
    _enable_rls("recadastramento_convocacao")
    _grant("recadastramento_convocacao")


def downgrade() -> None:
    op.execute(f"DROP TABLE {S}.recadastramento_convocacao CASCADE")
    op.execute(f"DROP TABLE {S}.recadastramento_ciclo CASCADE")
