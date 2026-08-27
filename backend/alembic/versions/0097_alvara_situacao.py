r"""Alvará ganha `situacao` comandada pelo workflow — P8 D2 (Task 4).

Revision ID: 0097
Revises: 0096
Create Date: 2026-08-23

Spec: `docs/superpowers/specs/2026-08-23-transporte-p8-workflows-design.md`
(fase D, task 4, §Alvará).

`transporte_regulado.alvara.situacao` nasce `varchar(30) NOT NULL DEFAULT
'vigente'` — SEM CHECK. A semente `transporte-alvara`
(`services/transporte_workflow.py::SEMENTES`) é quem arbitra os valores
válidos (`vigente`, `renovado`, `revogado`), e o DSL é por tenant e editável;
um CHECK fixo repetiria o erro que a 0096 já corrigiu para `ocorrencia`
(bloquear tenant que estenda o próprio workflow). Toda linha existente
(alvará emitido antes desta task) recebe `vigente` via `DEFAULT` — é a leitura
correta para o inventário de hoje: nenhum alvará histórico está `renovado`
nem `revogado` no banco, essas transições só passam a existir a partir de
agora.

`ADD COLUMN` herda RLS e grants da tabela `alvara` — não repetir (ver
CLAUDE.md).

## Downgrade

Dropa a coluna. Não há dado a preservar fora dela mesma — nenhuma outra
tabela referencia `alvara.situacao`.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0097"
down_revision: str | Sequence[str] | None = "0096"
branch_labels = None
depends_on = None

S = "transporte_regulado"


def upgrade() -> None:
    op.add_column(
        "alvara",
        sa.Column(
            "situacao",
            sa.String(length=30),
            nullable=False,
            server_default="vigente",
        ),
        schema=S,
    )


def downgrade() -> None:
    op.drop_column("alvara", "situacao", schema=S)
