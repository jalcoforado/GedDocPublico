r"""Transporte Fase C2 — notificação automática: gatilho + worker.

Revision ID: 0094
Revises: 0093
Create Date: 2026-08-23

Spec: `docs/superpowers/specs/2026-08-23-transporte-p5-pendencias-design.md`
(seção "Migration 0094").

Sem tabela nova — sem RLS novo. Três mudanças em
`transporte_regulado.recadastramento_notificacao` + grants ao `aprimora_worker`:

1. **`id_usuario` vira NULLABLE.** O NOT NULL original dizia "envio em lote é
   ato de operador"; a automação da Fase C é o segundo autor legítimo, e
   `NULL` passa a significar exatamente "enviado pelo job", não "autor
   perdido".
2. **Coluna nova `gatilho` varchar(30) NULL**, com CHECK dos 5 valores
   (`convocacao`, `lembrete`, `atraso`, `suspensao`, `reativacao`). `NULL` =
   linha manual anterior a esta migration, que não sabia seu gatilho. É a
   chave da idempotência do job: no máximo um envio por
   `(id_convocacao, gatilho)`.
3. **Grants ao `aprimora_worker`** — primeira vez que o worker toca as
   tabelas de recadastramento.

## Conferência ANTES de escrever os grants (obrigatória pelo brief)

`\dp` no banco de dev mostrou que `aprimora_worker` **já tinha**, via a
0078 (`GRANT SELECT ON ALL TABLES IN SCHEMA transporte_regulado` +
`ESCRITA_WORKER`/`SEQUENCES_WORKER`, que cobrem `aprimora_py`):

- `SELECT` em `transporte_regulado.permissionario` e `.empresa` (criadas nas
  migrations 0041/0042, portanto ANTES do `GRANT ... ALL TABLES` da 0078 —
  ficaram no retrato daquele momento);
- `SELECT, INSERT, UPDATE` em `aprimora_py.notificacao` (`ESCRITA_WORKER`,
  motivo já registrado ali: "verificar_sla_workflows dispara notificação de
  SLA estourado" — o mesmo grant serve ao motor de notificações em geral);
- `SELECT, USAGE` em `aprimora_py.notificacao_id_seq` (`SEQUENCES_WORKER`).

Ou seja: **nenhum grant em `aprimora_py.notificacao` ou sua sequence é
necessário aqui** — duplicar um `GRANT` não erra (idempotente), mas o brief
pede grants enumerados e honestos sobre o que já existe, e um GRANT
redundante nesta migration esconderia, para quem ler o `downgrade`, que o
privilégio sobrevive ao `REVOKE` daqui (porque veio de outro lugar).

O que **não** estava coberto — porque as tabelas nasceram DEPOIS do retrato
da 0078 (`recadastramento_ciclo`/`recadastramento_convocacao`: migration
0081; `recadastramento_notificacao`: P5.2) — é o que esta migration concede:
`SELECT` em `recadastramento_ciclo` e `recadastramento_convocacao`,
`SELECT, INSERT` em `recadastramento_notificacao` (+ sequence).

## Downgrade

Revoga só os grants concedidos AQUI (não mexe em `aprimora_py.notificacao`
nem em `permissionario`/`empresa` — não foram concedidos por esta
migration). Dropa o CHECK e a coluna `gatilho`. `id_usuario` só volta a
NOT NULL se não houver linha NULL: um job já pode ter gravado envios
automáticos antes do downgrade, e apagar essa autoria (ou pior, inventar um
autor) seria mais errado que deixar o `ALTER COLUMN` falhar alto com
`column contains null values` — o operador vê o erro e decide (apagar as
linhas do job, ou não descer a migration).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0094"
down_revision: str | Sequence[str] | None = "0093"
branch_labels = None
depends_on = None

S = "transporte_regulado"

# Tabelas do módulo cujo SELECT o worker ainda não tinha (nasceram depois do
# retrato `GRANT ... ALL TABLES` da 0078).
TABELAS_SELECT_NOVO = ("recadastramento_ciclo", "recadastramento_convocacao")


def upgrade() -> None:
    # NULL = envio do sistema (job). O NOT NULL original dizia "envio é ato de
    # operador"; a automação da Fase C é o segundo autor legítimo.
    op.alter_column(
        "recadastramento_notificacao", "id_usuario",
        existing_type=sa.Integer(), nullable=True, schema=S,
    )
    # Chave da idempotência do job: no máximo um envio por (convocacao, gatilho).
    # NULL = linha manual da P5.3, que não sabia seu gatilho.
    op.add_column(
        "recadastramento_notificacao",
        sa.Column("gatilho", sa.String(30), nullable=True),
        schema=S,
    )
    op.create_check_constraint(
        "ck_recadnotif_gatilho", "recadastramento_notificacao",
        "gatilho IS NULL OR gatilho IN "
        "('convocacao', 'lembrete', 'atraso', 'suspensao', 'reativacao')",
        schema=S,
    )
    # Primeiros grants do worker nestas duas tabelas — enumerados, nunca
    # cobertor. `permissionario`/`empresa` já tinham SELECT (0078, retrato
    # anterior às duas terem sido criadas — ver docstring do módulo).
    for t in TABELAS_SELECT_NOVO:
        op.execute(f"GRANT SELECT ON {S}.{t} TO aprimora_worker")
    op.execute(
        f"GRANT SELECT, INSERT ON {S}.recadastramento_notificacao TO aprimora_worker"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON {S}.recadastramento_notificacao_id_seq TO aprimora_worker"
    )
    # `aprimora_py.notificacao` (+ sequence) NÃO entra aqui: `aprimora_worker`
    # já tinha SELECT/INSERT/UPDATE ali desde a 0078 (`ESCRITA_WORKER`) — ver
    # docstring do módulo. Repetir o GRANT seria inofensivo mas mentiria, no
    # downgrade, sobre a origem do privilégio.


def downgrade() -> None:
    op.execute(
        f"REVOKE SELECT, INSERT ON {S}.recadastramento_notificacao FROM aprimora_worker"
    )
    op.execute(
        f"REVOKE USAGE, SELECT ON {S}.recadastramento_notificacao_id_seq "
        f"FROM aprimora_worker"
    )
    for t in TABELAS_SELECT_NOVO:
        op.execute(f"REVOKE SELECT ON {S}.{t} FROM aprimora_worker")

    op.drop_constraint(
        "ck_recadnotif_gatilho", "recadastramento_notificacao", schema=S,
        type_="check",
    )
    op.drop_column("recadastramento_notificacao", "gatilho", schema=S)

    # `id_usuario` só volta a NOT NULL se não houver linha NULL. Se o job já
    # rodou, este ALTER falha alto (`column ... contains null values`) — de
    # propósito: apagar autoria de envio automático, ou inventar um autor
    # fictício para o downgrade passar, é pior que um downgrade que exige
    # decisão humana antes de continuar.
    op.alter_column(
        "recadastramento_notificacao", "id_usuario",
        existing_type=sa.Integer(), nullable=False, schema=S,
    )
