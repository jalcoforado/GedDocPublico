"""Transporte Regulado P5.3 — suspensão, reativação e notificação de faltosos.

Revision ID: 0083
Revises: 0082
Create Date: 2026-08-05

Spec: `docs/superpowers/specs/2026-08-05-transporte-p5.3-atraso-suspensao-design.md`.

Duas mudanças, e o mais importante desta migration é o que ela **não** faz.

1. `ck_recaddecisao_tipo` passa de três para cinco valores, ganhando
   `suspensao` e `reativacao`. A P5.3 decidiu não criar entidade própria de
   recurso: suspender e reativar são atos com parecer na mesma trilha
   cronológica de `recadastramento_decisao`, ao lado de deferir e indeferir.

2. `recadastramento_notificacao` — liga a convocação à `aprimora_py.notificacao`
   criada pelo motor existente. **Sem índice único**: notificar duas vezes é
   legítimo e frequente (segundo aviso, terceiro aviso). Mesmo raciocínio de
   `recadastramento_marca`, que também é log.

O que NÃO está aqui, e é deliberado: a situação `suspenso` de
`recadastramento_convocacao`. Aquela coluna **não tem CHECK** — a `0081` criou
só `ck_recadconv_vinculo_exclusivo`, e o vocabulário de `situacao` é imposto
pelo serviço. Aceitar um valor novo, portanto, não exige nada do banco.
Acrescentar o CHECK agora seria mudar a premissa da P5.1 dentro de um PR que
não é sobre isso; fica registrado aqui como observação para quem for revisitar,
não como dívida silenciosa.

A tabela nova nasce com o boilerplate completo de RLS. Os três detalhes que já
custaram 20 policies quebradas por 7 meses no `transporte_regulado`, corrigidas
na 0078: a GUC é `app.tenant_id`; o segundo argumento `true` do
`current_setting` NÃO é opcional — sem ele a policy derruba a consulta em vez
de negar; e `ENABLE` sem `FORCE` não protege enquanto o dono da tabela for o
papel do runtime.

Sem GRANT para `aprimora_worker`: nenhuma task Celery escreve aqui. O worker é
enumerado de propósito, não por cobertor.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0083"
down_revision: str | Sequence[str] | None = "0082"
branch_labels = None
depends_on = None

S = "transporte_regulado"

TIPOS_ANTES = "('deferimento', 'indeferimento', 'reabertura')"
TIPOS_DEPOIS = (
    "('deferimento', 'indeferimento', 'reabertura', 'suspensao', 'reativacao')"
)


def upgrade() -> None:
    # ------------------------------------------- vocabulário da decisão
    op.execute(
        f"ALTER TABLE {S}.recadastramento_decisao "
        f"DROP CONSTRAINT ck_recaddecisao_tipo"
    )
    op.execute(
        f"ALTER TABLE {S}.recadastramento_decisao "
        f"ADD CONSTRAINT ck_recaddecisao_tipo CHECK (tipo IN {TIPOS_DEPOIS})"
    )

    # ------------------------------------------------ log de notificação
    op.create_table(
        "recadastramento_notificacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_convocacao", sa.Integer(),
            sa.ForeignKey(f"{S}.recadastramento_convocacao.id"), nullable=False,
        ),
        # FK real para a notificação do motor. Guardar só um texto tornaria
        # impossível saber se a mensagem saiu, para onde, e com que erro — tudo
        # isso já está em `aprimora_py.notificacao`.
        sa.Column(
            "id_notificacao", sa.Integer(),
            sa.ForeignKey("aprimora_py.notificacao.id"), nullable=False,
        ),
        # NOT NULL: envio em lote é ato de operador, e sem autor não há a quem
        # perguntar por que o município notificou. Mesma regra da decisão.
        sa.Column(
            "id_usuario", sa.Integer(),
            sa.ForeignKey("utils.usuario.id"), nullable=False,
        ),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema=S,
    )
    # SEM índice único em (id_convocacao, id_notificacao) nem em
    # (id_convocacao): ver o item 2 do docstring.
    op.create_index(
        "ix_recadnotif_tenant_convocacao", "recadastramento_notificacao",
        ["tenant_id", "id_convocacao"], schema=S,
    )

    op.execute(f"ALTER TABLE {S}.recadastramento_notificacao ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.recadastramento_notificacao FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_select ON {S}.recadastramento_notificacao "
        f"FOR SELECT "
        f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)"
    )
    op.execute(
        f"CREATE POLICY tenant_isolation_modify ON {S}.recadastramento_notificacao "
        f"FOR ALL "
        f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int) "
        f"WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)"
    )
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.recadastramento_notificacao "
        f"TO aprimora_app"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON {S}.recadastramento_notificacao_id_seq TO aprimora_app"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recadnotif_tenant_convocacao",
        table_name="recadastramento_notificacao", schema=S,
    )
    op.drop_table("recadastramento_notificacao", schema=S)

    # Voltar o CHECK a três valores só é possível se nenhuma linha usar os dois
    # novos. Apagar decisão para caber na constraint seria destruir trilha de
    # ato administrativo, então este downgrade **falha** no `ADD CONSTRAINT`
    # quando já houve suspensão — o Postgres reclama que a constraint é
    # violada, e resolver é decisão humana. Barulho é melhor que perda
    # silenciosa.
    op.execute(
        f"ALTER TABLE {S}.recadastramento_decisao DROP CONSTRAINT ck_recaddecisao_tipo"
    )
    op.execute(
        f"ALTER TABLE {S}.recadastramento_decisao "
        f"ADD CONSTRAINT ck_recaddecisao_tipo CHECK (tipo IN {TIPOS_ANTES})"
    )
