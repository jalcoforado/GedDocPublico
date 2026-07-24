"""Sigilo gradual — classificação LAI (Lei 12.527/2011).

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-28

Substitui o booleano `processo.publico` por cinco níveis de sigilo
(ostensivo / interno / reservado / secreto / ultrassecreto). `publico` passa
a ser COLUNA GERADA (= nivel_sigilo == 'ostensivo'), garantindo que nunca
divirja do nível — toda a lógica de visibilidade existente segue lendo
`publico` sem mudança.

Os três graus de sigilo legal exigem TCI (Termo de Classificação da
Informação): fundamento legal, autoridade classificadora e prazo de
desclassificação. Esses metadados ficam em colunas dedicadas no processo.

Controle de acesso: `usuario.nivel_acesso_sigilo` é a credencial do servidor
(default 'interno' — vê tudo que é ostensivo/interno, mas não os graus de
sigilo legal). Backfill mantém comportamento atual: processos com
`publico=false` viram 'interno' (continuam visíveis a todos os servidores),
e todos os usuários nascem com credencial 'interno'.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NIVEIS = "'ostensivo','interno','reservado','secreto','ultrassecreto'"


def upgrade() -> None:
    # === processo: nivel_sigilo + TCI =======================================
    op.add_column(
        "processo",
        sa.Column(
            "nivel_sigilo",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'ostensivo'"),
        ),
        schema="protocolos",
    )
    op.add_column(
        "processo",
        sa.Column("sigilo_fundamento_legal", sa.Text(), nullable=True),
        schema="protocolos",
    )
    op.add_column(
        "processo",
        sa.Column("sigilo_autoridade", sa.String(length=300), nullable=True),
        schema="protocolos",
    )
    op.add_column(
        "processo",
        sa.Column("sigilo_prazo_anos", sa.SmallInteger(), nullable=True),
        schema="protocolos",
    )
    op.add_column(
        "processo",
        sa.Column("sigilo_data_classificacao", sa.DateTime(), nullable=True),
        schema="protocolos",
    )
    op.add_column(
        "processo",
        sa.Column("sigilo_data_desclassificacao", sa.Date(), nullable=True),
        schema="protocolos",
    )
    op.add_column(
        "processo",
        sa.Column(
            "sigilo_classificado_por",
            sa.Integer(),
            sa.ForeignKey("utils.usuario.id"),
            nullable=True,
        ),
        schema="protocolos",
    )

    # Backfill a partir do booleano antigo: público → ostensivo; o resto vira
    # 'interno' (não-público, mas sem sigilo legal — preserva visibilidade).
    op.execute(
        """
        UPDATE protocolos.processo
           SET nivel_sigilo = CASE WHEN publico THEN 'ostensivo' ELSE 'interno' END
        """
    )

    op.create_check_constraint(
        "ck_processo_nivel_sigilo",
        "processo",
        f"nivel_sigilo IN ({_NIVEIS})",
        schema="protocolos",
    )

    # publico vira coluna GERADA (= ostensivo). Drop + re-add.
    op.drop_column("processo", "publico", schema="protocolos")
    op.add_column(
        "processo",
        sa.Column(
            "publico",
            sa.Boolean(),
            sa.Computed("nivel_sigilo = 'ostensivo'", persisted=True),
            nullable=False,
        ),
        schema="protocolos",
    )

    op.create_index(
        "ix_processo_nivel_sigilo",
        "processo",
        ["tenant_id", "nivel_sigilo"],
        unique=False,
        schema="protocolos",
    )

    # === usuario: credencial de acesso ======================================
    op.add_column(
        "usuario",
        sa.Column(
            "nivel_acesso_sigilo",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'interno'"),
        ),
        schema="utils",
    )
    op.create_check_constraint(
        "ck_usuario_nivel_acesso_sigilo",
        "usuario",
        f"nivel_acesso_sigilo IN ({_NIVEIS})",
        schema="utils",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_usuario_nivel_acesso_sigilo", "usuario", type_="check", schema="utils"
    )
    op.drop_column("usuario", "nivel_acesso_sigilo", schema="utils")

    op.drop_index(
        "ix_processo_nivel_sigilo", table_name="processo", schema="protocolos"
    )
    # Reverte publico para coluna booleana normal preservando o valor atual.
    op.drop_column("processo", "publico", schema="protocolos")
    op.add_column(
        "processo",
        sa.Column(
            "publico",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        schema="protocolos",
    )
    op.execute(
        """
        UPDATE protocolos.processo
           SET publico = (nivel_sigilo = 'ostensivo')
        """
    )
    op.drop_constraint(
        "ck_processo_nivel_sigilo", "processo", type_="check", schema="protocolos"
    )
    op.drop_column("processo", "sigilo_classificado_por", schema="protocolos")
    op.drop_column("processo", "sigilo_data_desclassificacao", schema="protocolos")
    op.drop_column("processo", "sigilo_data_classificacao", schema="protocolos")
    op.drop_column("processo", "sigilo_prazo_anos", schema="protocolos")
    op.drop_column("processo", "sigilo_autoridade", schema="protocolos")
    op.drop_column("processo", "sigilo_fundamento_legal", schema="protocolos")
    op.drop_column("processo", "nivel_sigilo", schema="protocolos")
