r"""Amplia colunas `situacao` comandadas pelo workflow para varchar(50) — P8
fix-wave (Important 1).

Revision ID: 0098
Revises: 0097
Create Date: 2026-08-24

Spec: `docs/superpowers/specs/2026-08-23-transporte-p8-workflows-design.md`
(review final, Important 1).

`workflow_instance.estado_atual` é `varchar(50)` (migration 0095), mas as
três colunas `situacao` que o motor grava por baixo — `ocorrencia.situacao`
e `recadastramento_convocacao.situacao`, ambas `varchar(20)`, e
`alvara.situacao`, `varchar(30)` (migration 0097) — nasceram menores. O DSL
de workflow é **por tenant** e editável (`services/transporte_workflow.py`);
um tenant que defina um estado com slug de 21 a 50 caracteres (ex.:
`aguardando_analise_documental`, 29 chars) faz a transição gravar
`entidade.situacao = para` (`transporte_regulado.py::transicionar`) e a
coluna curta estoura `StringDataRightTruncation` → HTTP 500 no meio de uma
transação que já tinha mutado a entidade em memória.

As três colunas não têm CHECK (mesma decisão da 0096/0097: o guardião de
valor válido é o DSL, não o schema) — só o tamanho muda aqui.

## Downgrade

Volta cada coluna ao tamanho original (`ocorrencia.situacao` e
`recadastramento_convocacao.situacao` a 20, `alvara.situacao` a 30) — e
FALHA ALTO se existir alguma linha com valor mais longo que o tamanho
original, mesmo padrão das 0094/0095: encolher a coluna por baixo de dado
real trunca silenciosamente, e decidir o que fazer com o excesso é decisão
humana, não escolha automática do downgrade.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0098"
down_revision: str | Sequence[str] | None = "0097"
branch_labels = None
depends_on = None

S = "transporte_regulado"

# (tabela, tamanho original)
_COLUNAS = (
    ("ocorrencia", 20),
    ("recadastramento_convocacao", 20),
    ("alvara", 30),
)


def upgrade() -> None:
    for tabela, _tamanho_original in _COLUNAS:
        op.alter_column(
            tabela, "situacao",
            existing_type=sa.String(length=_tamanho_original),
            type_=sa.String(length=50),
            existing_nullable=False,
            schema=S,
        )


def downgrade() -> None:
    for tabela, tamanho_original in _COLUNAS:
        op.execute(
            f"""
            DO $$
            DECLARE
                n_longa integer;
            BEGIN
                SELECT count(*) INTO n_longa
                FROM {S}.{tabela}
                WHERE length(situacao) > {tamanho_original};

                IF n_longa > 0 THEN
                    RAISE EXCEPTION
                        'downgrade 0098 abortado: % linha(s) em {S}.{tabela} '
                        'com situacao mais longa que varchar({tamanho_original}) '
                        '(não é seguro encolher a coluna)', n_longa;
                END IF;
            END $$;
            """
        )
        op.alter_column(
            tabela, "situacao",
            existing_type=sa.String(length=50),
            type_=sa.String(length=tamanho_original),
            existing_nullable=False,
            schema=S,
        )
