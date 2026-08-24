r"""Workflow instance polimórfica — P8 D1.

Revision ID: 0095
Revises: 0094
Create Date: 2026-08-23

Spec: `docs/superpowers/specs/2026-08-23-transporte-p8-workflows-master.md`
(fase D, task 1).

Até aqui `workflow_instance` só conhecia `processo` (`id_processo` NOT
NULL). O motor BPM da fase P8 precisa instanciar workflow também para
`ocorrencia`, `alvara` e `convocacao` (recadastramento). Esta migration
torna a instância polimórfica no banco:

1. `entidade_tipo varchar(30)` + `entidade_id integer`, com CHECK
   restringindo `entidade_tipo` aos quatro valores conhecidos hoje.
2. Backfill: toda linha existente é de processo, então
   `entidade_tipo='processo'`, `entidade_id=id_processo`.
3. `id_processo` vira NULLABLE — deixa de ser o identificador universal.
4. Índice `ix_workflow_instance_entidade (tenant_id, entidade_tipo,
   entidade_id)` para busca por entidade.
5. Índice único parcial NOVO `uq_workflow_instance_ativa_entidade
   (tenant_id, entidade_tipo, entidade_id) WHERE ativa` — uma instância
   ativa por entidade, agora coberto para as quatro classes.

O índice único parcial ANTIGO da 0008
(`ix_workflow_instance_processo_ativa`, sobre `id_processo WHERE ativa`)
**não é removido aqui**. Ele continua redundante-mas-inofensivo para as
linhas de processo (o novo índice já cobre o mesmo caso via
`entidade_tipo='processo'`), e removê-lo é fora do escopo desta task —
quem tocar o engine de processo (Task 2) decide se ele ainda faz sentido
manter depois que o engine também escrever em `entidade_tipo/entidade_id`
para processo.

O engine (`workflow_engine.py`) permanece sem alterações nesta task — ele
ainda grava só `id_processo`, então o backfill cobre tudo que existe e
tudo que a Task 1 sozinha cria. `entidade_tipo`/`entidade_id` continuam
sem uso pelo motor até a Task 2.

`ADD COLUMN` herda RLS/grants da tabela — não repetidos aqui.

## Downgrade

Antes de restaurar `id_processo` NOT NULL, confere se alguma linha tem
`entidade_tipo != 'processo'` (ou seja, foi criada já como polimórfica
pela Task 2 ou por teste). Se houver, `RAISE EXCEPTION` — devolver essas
linhas para "processo" inventaria um `id_processo` que não existe, e
apagá-las destruiria histórico de workflow em produção. Padrão idêntico
ao `id_usuario` da 0094: erro alto, decisão humana.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0095"
down_revision: str | Sequence[str] | None = "0094"
branch_labels = None
depends_on = None

S = "aprimora_py"
T = "workflow_instance"


def upgrade() -> None:
    op.add_column(T, sa.Column("entidade_tipo", sa.String(30), nullable=True), schema=S)
    op.add_column(T, sa.Column("entidade_id", sa.Integer(), nullable=True), schema=S)

    op.execute(
        f"UPDATE {S}.{T} SET entidade_tipo = 'processo', entidade_id = id_processo "
        f"WHERE entidade_tipo IS NULL"
    )

    op.alter_column(T, "entidade_tipo", existing_type=sa.String(30), nullable=False, schema=S)
    op.alter_column(T, "entidade_id", existing_type=sa.Integer(), nullable=False, schema=S)
    op.create_check_constraint(
        "ck_workflow_instance_entidade_tipo",
        T,
        "entidade_tipo IN ('processo', 'ocorrencia', 'alvara', 'convocacao')",
        schema=S,
    )

    op.alter_column(T, "id_processo", existing_type=sa.Integer(), nullable=True, schema=S)

    op.create_index(
        "ix_workflow_instance_entidade",
        T,
        ["tenant_id", "entidade_tipo", "entidade_id"],
        schema=S,
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_workflow_instance_ativa_entidade
        ON {S}.{T} (tenant_id, entidade_tipo, entidade_id)
        WHERE ativa
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {S}.uq_workflow_instance_ativa_entidade")
    op.drop_index("ix_workflow_instance_entidade", table_name=T, schema=S)

    # `id_processo` só volta a NOT NULL se toda linha ainda for de processo.
    # Linha com entidade_tipo != 'processo' não tem id_processo confiável —
    # inventar um valor ou apagar a linha seria mais errado que falhar alto
    # e deixar o operador decidir (mesmo padrão da 0094 para `id_usuario`).
    op.execute(
        f"""
        DO $$
        DECLARE
            n_nao_processo integer;
        BEGIN
            SELECT count(*) INTO n_nao_processo
            FROM {S}.{T}
            WHERE entidade_tipo != 'processo';

            IF n_nao_processo > 0 THEN
                RAISE EXCEPTION
                    'downgrade 0095 abortado: % linha(s) de workflow_instance '
                    'com entidade_tipo diferente de processo (não é seguro '
                    'restaurar id_processo NOT NULL)', n_nao_processo;
            END IF;
        END $$;
        """
    )
    op.alter_column(T, "id_processo", existing_type=sa.Integer(), nullable=False, schema=S)

    op.drop_constraint("ck_workflow_instance_entidade_tipo", T, schema=S, type_="check")
    op.drop_column(T, "entidade_id", schema=S)
    op.drop_column(T, "entidade_tipo", schema=S)
