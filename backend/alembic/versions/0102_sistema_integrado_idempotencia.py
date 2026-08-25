"""Pagamentos C2.3 — realm M2M: sistema integrado + idempotência.

Revision ID: 0102
Revises: 0101
Create Date: 2026-08-24

Numeração: o brief original da Task 6 chamava esta migration de "0101", mas a
Task 4/C2.1 (`0101_export_contabil.py`) já ocupava esse número quando esta
fatia começou. Esta é a 0102.

Duas tabelas:

- `pagamentos.sistema_integrado` — credencial de um sistema externo M2M.
  `prefixo` (ex. `apy_ab12cd34`) é **unique GLOBAL**, não `(tenant_id, prefixo)`
  como todo índice de negócio deste projeto. É deliberado: o header
  `X-Api-Key` chega como `<prefixo>.<segredo>` e o tenant do chamador AINDA
  NÃO é conhecido no momento da busca — é o prefixo que resolve QUAL linha
  (e portanto qual tenant), não o inverso. Uma unique por tenant exigiria
  saber o tenant antes de achar a linha que revela o tenant. `hash_chave` é
  bcrypt do segredo, nunca o segredo em claro (ver
  `auth/sistema_integrado.py`).
- `pagamentos.idempotencia` — unique `(tenant_id, id_sistema, chave)`: a
  mesma chave de idempotência do mesmo sistema, no mesmo tenant, identifica
  uma única execução. Aqui SIM o tenant já é conhecido (o request já
  autenticou via `sistema_integrado`), então a unique de negócio volta a ser
  por tenant, como em todo o resto do banco.

Boilerplate de RLS completo nas duas (GUC `app.tenant_id`, `current_setting`
com o segundo argumento `true`, ENABLE + FORCE). Sem GRANT para
`aprimora_worker`: nenhuma task Celery escreve aqui nesta fatia.

Nota sobre a busca por prefixo sob RLS: hoje (F-12) `ged_user` é
SUPERUSER/BYPASSRLS e a policy não filtra nada em produção, então o `SELECT
... WHERE prefixo = :p` em `get_current_sistema_integrado` enxerga qualquer
tenant, como o desenho pede. Quando `APP_DATABASE_URL` apontar para
`aprimora_app` (gate `SEC-RLS-ROLLOUT`), a policy abaixo (`tenant_id = GUC`)
passaria a filtrar essa busca pelo tenant da sessão — que para uma requisição
M2M pode não ser o tenant da chave. Esse é um gap conhecido do rollout, não
desta fatia: registrar aqui para quem ligar o rollout depois.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0102"
down_revision: str | Sequence[str] | None = "0101"
branch_labels = None
depends_on = None

S = "pagamentos"

GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"


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
    # ------------------------------------------------------- sistema_integrado
    op.create_table(
        "sistema_integrado",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("prefixo", sa.String(12), nullable=False),
        sa.Column("hash_chave", sa.String(100), nullable=False),
        sa.Column(
            "escopo_leitura", sa.Boolean(), nullable=False, server_default=sa.text("true"),
        ),
        sa.Column(
            "escopo_escrita", sa.Boolean(), nullable=False, server_default=sa.text("false"),
        ),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("revogado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "id_usuario_criador", sa.Integer(),
            sa.ForeignKey("utils.usuario.id"), nullable=True,
        ),
        schema=S,
    )
    op.create_index(
        "ix_sistemaintegrado_tenant", "sistema_integrado", ["tenant_id"], schema=S,
    )
    op.execute(
        f"CREATE UNIQUE INDEX ux_sistemaintegrado_prefixo ON {S}.sistema_integrado (prefixo)"
    )
    _rls("sistema_integrado")

    # ------------------------------------------------------------- idempotencia
    op.create_table(
        "idempotencia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_sistema", sa.Integer(),
            sa.ForeignKey(f"{S}.sistema_integrado.id"), nullable=False,
        ),
        sa.Column("chave", sa.String(64), nullable=False),
        sa.Column("hash_payload", sa.String(64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("corpo_resposta", JSONB(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        schema=S,
    )
    op.create_index(
        "ix_idempotencia_tenant_sistema", "idempotencia", ["tenant_id", "id_sistema"], schema=S,
    )
    op.execute(
        f"CREATE UNIQUE INDEX ux_idempotencia_chave ON {S}.idempotencia "
        f"(tenant_id, id_sistema, chave)"
    )
    _rls("idempotencia")


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {S}.ux_idempotencia_chave")
    op.drop_index("ix_idempotencia_tenant_sistema", table_name="idempotencia", schema=S)
    op.drop_table("idempotencia", schema=S)

    op.execute(f"DROP INDEX IF EXISTS {S}.ux_sistemaintegrado_prefixo")
    op.drop_index("ix_sistemaintegrado_tenant", table_name="sistema_integrado", schema=S)
    op.drop_table("sistema_integrado", schema=S)
