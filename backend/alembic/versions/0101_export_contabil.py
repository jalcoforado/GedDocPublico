"""Pagamentos C2.1 — export contábil neutro, lotes imutáveis.

Revision ID: 0101
Revises: 0100
Create Date: 2026-08-24

Numeração: o brief original da Task 4 chamava esta migration de "0100", mas
a Task 2 da C2.2 (`0100_extrato_formato_cnab240.py`) já ocupava esse número
antes desta fatia começar. Esta é a 0101.

Duas tabelas:

- `export_contabil_lote` — um lote gerado por `POST /pagamentos/contabil/lotes`.
  `numero` é sequencial POR tenant (índice único parcial entre não excluídos —
  a rede contra corrida, já que o cálculo do próximo número no service é
  best-effort com `pg_advisory_xact_lock`, não um `SELECT ... FOR UPDATE`
  sobre linha que ainda não existe). Imutável depois de gravado: o conteúdo
  do CSV é reconstruído sob demanda a partir dos eventos vinculados e
  conferido contra `hash_conteudo`.
- `export_contabil_evento` — cada linha é um evento do domínio (débito
  empenhado, liquidação, pagamento, estorno de parcela, cancelamento de
  débito) capturado por um lote. A unique `(tenant_id, tipo_evento,
  id_origem)` é o que impede o mesmo evento de entrar em dois lotes — é
  literalmente "pertence a exatamente um lote". `id_origem` referencia a
  linha real que originou o evento no domínio (id de `debito_historico` para
  os quatro tipos ligados a transição de débito, id de `movimentacao_conta`
  para pagamento/estorno — ver `services/pagamentos_contabil.py`), nunca uma
  sequência própria.

Boilerplate de RLS completo nas duas (GUC `app.tenant_id`, `current_setting`
com o segundo argumento `true`, ENABLE + FORCE). Sem GRANT para
`aprimora_worker`: nada aqui é escrito por task Celery nesta fatia.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0101"
down_revision: str | Sequence[str] | None = "0100"
branch_labels = None
depends_on = None

S = "pagamentos"

GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"

TIPOS_EVENTO = (
    "debito_empenhado", "liquidacao", "pagamento", "estorno_parcela", "cancelamento_debito",
)


def _rls(tabela: str) -> None:
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
    # --------------------------------------------------- export_contabil_lote
    op.create_table(
        "export_contabil_lote",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("periodo_inicio", sa.Date(), nullable=True),
        sa.Column("periodo_fim", sa.Date(), nullable=True),
        sa.Column(
            "formato_versao", sa.String(20), nullable=False,
            server_default="neutro-csv-v1",
        ),
        sa.Column(
            "qtd_eventos", sa.Integer(), nullable=False, server_default=sa.text("0"),
        ),
        sa.Column("hash_conteudo", sa.String(64), nullable=True),
        sa.Column(
            "id_usuario", sa.Integer(),
            sa.ForeignKey("utils.usuario.id"), nullable=True,
        ),
        sa.Column(
            "gerado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("false"),
        ),
        schema=S,
    )
    op.create_index(
        "ix_exportcontabillote_tenant", "export_contabil_lote", ["tenant_id"], schema=S,
    )
    op.execute(
        f"CREATE UNIQUE INDEX ux_exportcontabillote_numero ON {S}.export_contabil_lote "
        f"(tenant_id, numero) WHERE excluido = false"
    )
    _rls("export_contabil_lote")

    # -------------------------------------------------- export_contabil_evento
    op.create_table(
        "export_contabil_evento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_lote", sa.Integer(),
            sa.ForeignKey(f"{S}.export_contabil_lote.id"), nullable=False,
        ),
        sa.Column("tipo_evento", sa.String(30), nullable=False),
        sa.Column("id_origem", sa.Integer(), nullable=False),
        sa.Column("ocorrido_em", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "tipo_evento IN (" + ", ".join(f"'{t}'" for t in TIPOS_EVENTO) + ")",
            name="ck_exportcontabilevento_tipo",
        ),
        schema=S,
    )
    op.create_index(
        "ix_exportcontabilevento_tenant_lote", "export_contabil_evento",
        ["tenant_id", "id_lote"], schema=S,
    )
    op.execute(
        f"CREATE UNIQUE INDEX ux_exportcontabilevento_origem ON {S}.export_contabil_evento "
        f"(tenant_id, tipo_evento, id_origem)"
    )
    _rls("export_contabil_evento")


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {S}.ux_exportcontabilevento_origem")
    op.drop_index(
        "ix_exportcontabilevento_tenant_lote", table_name="export_contabil_evento", schema=S,
    )
    op.drop_table("export_contabil_evento", schema=S)

    op.execute(f"DROP INDEX IF EXISTS {S}.ux_exportcontabillote_numero")
    op.drop_index("ix_exportcontabillote_tenant", table_name="export_contabil_lote", schema=S)
    op.drop_table("export_contabil_lote", schema=S)
