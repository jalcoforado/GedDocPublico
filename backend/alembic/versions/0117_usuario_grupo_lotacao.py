"""Permissão por lotação — UsuarioGrupo ganha escopo (E1, benchmark SUiTE).

Revision ID: 0117
Revises: 0116
Create Date: 2026-09-18

**A coluna já existe.** `utils.usuario_grupo.id_unidade_trabalho` está no
schema legado (`ci/legacy-schema.sql`) desde sempre — inclusive com o gatilho
de auditoria (`func_aud_usuario_grupo`) já preparado para registrar mudanças
nela. `ALTER TABLE ... ADD COLUMN` aqui falharia com `DuplicateColumn`: foi
assim que a descoberta apareceu, tentando aplicar esta migration. O desenho
PHP original já previa permissão por lotação; só nunca foi ligado neste
piloto (`SELECT count(id_unidade_trabalho) FROM utils.usuario_grupo` = 0 em
104 linhas). Esta migration não popula nada — só formaliza o que a coluna
dormente já significa: NULO = vínculo global (o de hoje); PREENCHIDO = só
vale quando a lotação ATIVA da sessão for aquela. Os dois eixos se somam por
UNIÃO, conforme
`docs/superpowers/plans/2026-09-16-aproveitamento-suite.md` §6 Q1.

O que ESTA migration de fato adiciona:
- **FK** para `utils.unidade_trabalho` — a coluna legada não tinha nenhuma;
  seguro de acrescentar porque as 104 linhas existentes estão todas NULAS.
- **Índice** `(tenant_id, id_usuario, id_unidade_trabalho)` — a coluna entra
  no filtro de toda checagem de permissão
  (`services/permissoes.py::load_permissions`), chamada a cada request
  autenticado.

Sem efeito em dado nenhum: nenhuma linha muda, nenhum acesso muda no dia do
deploy. A lotação ATIVA em si (o "alterar setor" do SUiTE) não é uma tabela;
vive como claim `unidade_contexto_id` no JWT, emitida em `/auth/login`
(default: lotação principal) e trocada por `POST /auth/lotacao-ativa`.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0117"
down_revision: str | Sequence[str] | None = "0116"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_usuario_grupo_unidade_trabalho",
        "usuario_grupo",
        "unidade_trabalho",
        ["id_unidade_trabalho"],
        ["id"],
        source_schema="utils",
        referent_schema="utils",
    )
    op.create_index(
        "ix_usuario_grupo_lotacao",
        "usuario_grupo",
        ["tenant_id", "id_usuario", "id_unidade_trabalho"],
        schema="utils",
    )


def downgrade() -> None:
    op.drop_index("ix_usuario_grupo_lotacao", table_name="usuario_grupo", schema="utils")
    op.drop_constraint(
        "fk_usuario_grupo_unidade_trabalho",
        "usuario_grupo",
        schema="utils",
        type_="foreignkey",
    )
