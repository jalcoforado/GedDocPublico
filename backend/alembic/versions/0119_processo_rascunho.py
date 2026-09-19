"""Rascunho = processo sem número (E3, benchmark SUiTE).

Revision ID: 0119
Revises: 0118
Create Date: 2026-09-19

Desenho completo em `docs/superpowers/specs/2026-09-19-e3-rascunho-sem-numero-design.md`.

`protocolos.processo.numero_processo` era NOT NULL desde sempre — todo
processo nascia já numerado em `abrir_processo()`. Esta migration abre
espaço para um segundo estado: `situacao='rascunho'`, criado sem número,
numerado só no primeiro `encaminhar()` (services/acoes_processo.py).

Decisão deliberada: NÃO faz `DROP DEFAULT` na coluna. Ela mantém
`DEFAULT protocolos.gerar_numero_processo_string()` (definido no schema
legado, `ci/legacy-schema.sql:371`). O app Python sempre passa
`numero_processo` explicitamente — inclusive `None` para rascunho — e um
valor explícito, mesmo `NULL`, vai para o INSERT sem tocar o DEFAULT do
servidor. Mas o schema é compartilhado com o monólito PHP legado, e não há
garantia de que todo INSERT feito fora do ORM Python declare a coluna;
manter o DEFAULT é rede de segurança sem custo.

O `CHECK` cruzado (`ck_processo_situacao_numero`) é a garantia que hoje não
existe em teste nenhum — a ausência de `numero_processo` era garantida só
pelo NOT NULL estrutural. Todo processo existente já tem número, então o
`server_default='protocolado'` faz o backfill sem tocar linha nenhuma
explicitamente, e já nasce consistente com o CHECK.

Reversão: só é segura se não houver rascunho vivo. Com
`situacao='rascunho'` gravado, `numero_processo` é NULL e o
`ALTER COLUMN ... SET NOT NULL` do downgrade falha de propósito — melhor
falhar que inventar um número na volta.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0119"
down_revision: str | Sequence[str] | None = "0118"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "processo",
        "numero_processo",
        existing_type=sa.String(length=255),
        nullable=True,
        schema="protocolos",
    )
    op.add_column(
        "processo",
        sa.Column(
            "situacao",
            sa.String(length=20),
            nullable=False,
            server_default="protocolado",
        ),
        schema="protocolos",
    )
    op.create_check_constraint(
        "ck_processo_situacao",
        "processo",
        "situacao IN ('rascunho', 'protocolado')",
        schema="protocolos",
    )
    op.create_check_constraint(
        "ck_processo_situacao_numero",
        "processo",
        "(situacao = 'rascunho') = (numero_processo IS NULL)",
        schema="protocolos",
    )
    op.create_index(
        "ix_processo_situacao",
        "processo",
        ["tenant_id", "situacao", "id_usuario"],
        schema="protocolos",
    )


def downgrade() -> None:
    op.drop_index("ix_processo_situacao", table_name="processo", schema="protocolos")
    op.drop_constraint(
        "ck_processo_situacao_numero", "processo", schema="protocolos", type_="check"
    )
    op.drop_constraint("ck_processo_situacao", "processo", schema="protocolos", type_="check")
    op.drop_column("processo", "situacao", schema="protocolos")
    # Falha de propósito se houver rascunho vivo (numero_processo NULL).
    op.alter_column(
        "processo",
        "numero_processo",
        existing_type=sa.String(length=255),
        nullable=False,
        schema="protocolos",
    )
