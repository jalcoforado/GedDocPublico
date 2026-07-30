"""FK de tenant_modulo passa a CASCADE no delete do tenant.

Revision ID: 0075
Revises: 0074
Create Date: 2026-07-30

Esta fatia faz o provisionamento contratar módulos, então todo tenant novo
passa a ter linha em aprimora_py.tenant_modulo. A FK nasceu NO ACTION na 0073
e 51 arquivos de teste apagam a linha do tenant no teardown — todos passariam
a morrer com violação de FK.

CASCADE é correto por si, não por conveniência de teste: tenant_modulo é filho
puro do tenant e não tem existência própria. Produção não apaga tenant
fisicamente (convenção de soft-delete do projeto), então o CASCADE só se
manifesta em teste e em ferramenta de remoção de tenant — exatamente onde se
quer que o vínculo vá junto.

A FK de id_modulo continua NO ACTION de propósito: modulo é catálogo global, e
apagar linha de catálogo que algum tenant contratou DEVE falhar.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0075"
down_revision: str | Sequence[str] | None = "0074"
branch_labels = None
depends_on = None

S = "aprimora_py"
FK = "tenant_modulo_tenant_id_fkey"


def upgrade() -> None:
    op.drop_constraint(FK, "tenant_modulo", schema=S, type_="foreignkey")
    op.create_foreign_key(
        FK,
        "tenant_modulo",
        "tenant",
        ["tenant_id"],
        ["id"],
        source_schema=S,
        referent_schema=S,
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(FK, "tenant_modulo", schema=S, type_="foreignkey")
    op.create_foreign_key(
        FK,
        "tenant_modulo",
        "tenant",
        ["tenant_id"],
        ["id"],
        source_schema=S,
        referent_schema=S,
    )
