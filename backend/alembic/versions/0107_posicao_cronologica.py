"""Pagamentos F3 (Task 1) — posicao_cronologica + excecao_cronologica.

Revision ID: 0107
Revises: 0106
Create Date: 2026-08-25

Duas tabelas novas para a fila cronológica (F3, spec §4.3):

- `pagamentos.posicao_cronologica` — uma linha por débito em fila (unique
  `(tenant_id, id_debito)`), com a chave de ordenação da fila
  (`id_unidade, id_fonte_recursos, categoria, exercicio, marco_em`) coberta
  pelo índice `ix_posicao_cronologica_fila`. `situacao` espelha
  `debito.situacao_fila` — a Task 2 é quem escreve/mantém sincronizado.
- `pagamentos.excecao_cronologica` — append-only, registra furo de ordem
  cronológica autorizado (LRF/lei de licitações), com autoridade e
  fundamento. Não há UPDATE nem DELETE previstos para o domínio.

`ck_posicao_categoria` usa o MESMO domínio do `ck_contrato_categoria` (0085):
`BENS`, `LOCACOES`, `SERVICOS`, `OBRAS` — mas aqui a coluna é NOT NULL, sem o
`categoria IS NULL OR` que a 0085 precisou porque backfillava em cima de dado
existente. Como `posicao_cronologica` nasce vazia, não há dado legado a
acomodar.

Backfill de `pagamentos.contrato.categoria`: a 0085 fez
`UPDATE ... SET categoria = 'SERVICOS' WHERE categoria IS NULL` sem filtro de
`excluido`, mas o dev acumulou 19 contratos com `categoria IS NULL` desde
então (contrato criado por caminho que não passou por
`services/pagamentos_cadastros.py::criar_contrato` com o default aplicado, ou
seed antigo). Esta migration repete o mesmo UPDATE, sem filtro de `excluido`,
para não deixar NULL residual — a fila cronológica em si não lê
`contrato.categoria` diretamente (lê `posicao_cronologica.categoria`, que a
Task 2 preenche a partir do débito/contrato), mas deixar a coluna com NULL
sob um CHECK que não a permite mais (não é o caso aqui — o CHECK antigo já
aceitava NULL) seria inconsistente com o rumo da F3, que assume categoria
sempre presente.

`downgrade()` derruba as duas tabelas novas. O backfill de `categoria` NÃO é
revertido: não haveria como saber quais das linhas atualizadas por este
UPDATE já estavam NULL antes dele e quais foram tocadas por coincidência
(nenhuma — o WHERE é `categoria IS NULL` — mas o downgrade não tem como
distinguir "ficou NULL por causa desta migration" de "já era NULL desde a
0085"). Downgrade de dado é, por natureza, best-effort aqui.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0107"
down_revision: str | Sequence[str] | None = "0106"
branch_labels = None
depends_on = None

S = "pagamentos"

GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"

CATEGORIAS = ("BENS", "LOCACOES", "SERVICOS", "OBRAS")


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
    # --------------------------------------------------- posicao_cronologica
    op.create_table(
        "posicao_cronologica",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_debito", sa.Integer(),
            sa.ForeignKey(f"{S}.debito.id"), nullable=False,
        ),
        sa.Column(
            "id_unidade", sa.Integer(),
            sa.ForeignKey("utils.unidade_trabalho.id"), nullable=False,
        ),
        sa.Column(
            "id_fonte_recursos", sa.Integer(),
            sa.ForeignKey(f"{S}.fonte_recursos.id"), nullable=False,
        ),
        sa.Column("categoria", sa.String(20), nullable=False),
        sa.Column("exercicio", sa.Integer(), nullable=False),
        sa.Column("marco_em", sa.DateTime(), nullable=False),
        sa.Column("situacao", sa.String(30), nullable=False),
        sa.Column("motivo_bloqueio", sa.String(255), nullable=True),
        sa.Column("previsao_pagamento", sa.Date(), nullable=True),
        sa.Column(
            "registrado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        schema=S,
    )
    op.execute(
        f"CREATE UNIQUE INDEX ux_posicaocronologica_debito ON {S}.posicao_cronologica "
        f"(tenant_id, id_debito)"
    )
    op.create_index(
        "ix_posicao_cronologica_fila", "posicao_cronologica",
        ["tenant_id", "id_unidade", "id_fonte_recursos", "categoria", "exercicio", "marco_em"],
        schema=S,
    )
    op.create_check_constraint(
        "ck_posicao_categoria", "posicao_cronologica",
        "categoria IN ('" + "','".join(CATEGORIAS) + "')", schema=S,
    )
    _rls("posicao_cronologica")

    # --------------------------------------------------- excecao_cronologica
    op.create_table(
        "excecao_cronologica",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_debito", sa.Integer(),
            sa.ForeignKey(f"{S}.debito.id"), nullable=False,
        ),
        sa.Column("justificativa", sa.Text(), nullable=False),
        sa.Column("fundamento", sa.String(255), nullable=False),
        sa.Column(
            "id_autoridade", sa.Integer(),
            sa.ForeignKey("utils.usuario.id"), nullable=False,
        ),
        sa.Column("data_autorizacao", sa.Date(), nullable=False),
        sa.Column(
            "id_usuario_registro", sa.Integer(),
            sa.ForeignKey("utils.usuario.id"), nullable=True,
        ),
        sa.Column("documentos", JSONB(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        schema=S,
    )
    op.create_index(
        "ix_excecaocronologica_debito", "excecao_cronologica",
        ["tenant_id", "id_debito"], schema=S,
    )
    _rls("excecao_cronologica")

    # ------------------------------------------- backfill de contrato.categoria
    op.execute(f"UPDATE {S}.contrato SET categoria = 'SERVICOS' WHERE categoria IS NULL")


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {S}.ix_excecaocronologica_debito")
    op.drop_table("excecao_cronologica", schema=S)

    op.execute(f"DROP INDEX IF EXISTS {S}.ix_posicao_cronologica_fila")
    op.execute(f"DROP INDEX IF EXISTS {S}.ux_posicaocronologica_debito")
    op.drop_table("posicao_cronologica", schema=S)

    # Backfill de categoria NÃO é revertido — ver docstring do módulo.
