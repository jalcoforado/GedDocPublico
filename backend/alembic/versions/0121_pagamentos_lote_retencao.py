"""Pagamentos F4 (Task 1) — lote_pagamento, lote_pagamento_parcela, retencao.

Revision ID: 0121
Revises: 0120
Create Date: 2026-09-20

Três tabelas novas para a execução em lote (F4, spec §4.3):

- `pagamentos.lote_pagamento` — artefato da EXECUÇÃO (não confundir com
  `ordem_pagamento`, artefato da AUTORIZAÇÃO — são atos distintos, spec
  premissa 7). Máquina de estados `situacao`: RASCUNHO -> PROGRAMADO ->
  ENVIADO -> PROCESSADO, com CANCELADO alcançável de RASCUNHO/PROGRAMADO.
  `numero` único por tenant, sem partição por `excluido` — este artefato não
  é soft-deletável (mesmo padrão de `ordem_pagamento`, que também não tem
  coluna `excluido`: cancelamento é estado, não exclusão).
- `pagamentos.lote_pagamento_parcela` — vínculo parcela<->lote. Uma parcela
  só tem uma linha ATIVA por vez: `UNIQUE (tenant_id, id_parcela) WHERE
  situacao <> 'FALHOU'` — falha libera a parcela para reentrar num lote
  novo, e a linha falha permanece intacta como registro da tentativa.
- `pagamentos.retencao` — 1:N com débito. `Debito.valor_liquido` continua
  sempre DERIVADO (nunca coluna): `valor_total - soma(retencao.valor não
  excluída)`.

Também amplia `ck_debhist_acao` (de 0069/.../0111) com as 7 ações que F4
introduz: LOTE_CRIADO, LOTE_PROGRAMADO, LOTE_ENVIADO, PAGAMENTO_CONFIRMADO,
PAGAMENTO_FALHOU, LOTE_CANCELADO, RETENCAO_RECOLHIDA. Cabem no VARCHAR(30)
que a 0106 já alargou.

Sem backfill: as três tabelas nascem vazias.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0121"
down_revision: str | Sequence[str] | None = "0120"
branch_labels = None
depends_on = None

S = "pagamentos"

GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"

SITUACOES_LOTE = ("RASCUNHO", "PROGRAMADO", "ENVIADO", "PROCESSADO", "CANCELADO")
SITUACOES_LOTE_PARCELA = ("PENDENTE", "PAGA", "FALHOU")
TIPOS_RETENCAO = ("IRRF", "INSS", "ISS", "PIS_COFINS_CSLL", "OUTRAS")

ACAO_ANTERIOR = (
    "CRIADO", "ENVIADO", "APROVADO", "VALIDADO", "ENCAMINHADO", "DEVOLVIDO",
    "REJEITADO", "AUTORIZADO", "LIBERADO", "LIBERACAO_REVOGADA", "PAGAMENTO",
    "ESTORNO", "CANCELADO", "LIQUIDADO", "SUSPENSO", "REATIVADO", "CONCILIADO",
    "AUTORIZADO_GESTOR", "REJEITADO_GESTOR", "AJUSTE_SOLICITADO",
    "AJUSTE_RESPONDIDO", "INDEFERIDO",
    "ENVIADO_TESOURARIA", "REVOGADO", "PAGO", "PROCESSANDO", "ESTORNADO",
    "REENVIADO", "APROVACOES_INVALIDADAS", "MARCO_REGRAVADO", "FILA_REAVALIADA",
    "EXCECAO_AUTORIZADA",
)
ACOES_NOVAS = (
    "LOTE_CRIADO", "LOTE_PROGRAMADO", "LOTE_ENVIADO", "PAGAMENTO_CONFIRMADO",
    "PAGAMENTO_FALHOU", "LOTE_CANCELADO", "RETENCAO_RECOLHIDA",
)


def _in(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


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
    # -------------------------------------------------------- lote_pagamento
    op.create_table(
        "lote_pagamento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column("numero", sa.String(20), nullable=False),
        sa.Column(
            "id_conta_pagadora", sa.Integer(),
            sa.ForeignKey(f"{S}.conta_bancaria.id"), nullable=False,
        ),
        sa.Column("situacao", sa.String(20), nullable=False, server_default="RASCUNHO"),
        sa.Column("data_programada", sa.Date(), nullable=True),
        sa.Column("valor_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column(
            "id_anexo_comprovante", sa.Integer(),
            sa.ForeignKey("protocolos.anexo.id"), nullable=True,
        ),
        sa.Column(
            "id_usuario", sa.Integer(),
            sa.ForeignKey("utils.usuario.id"), nullable=False,
        ),
        sa.Column(
            "id_usuario_envio", sa.Integer(),
            sa.ForeignKey("utils.usuario.id"), nullable=True,
        ),
        sa.Column("enviado_em", sa.DateTime(), nullable=True),
        sa.Column("processado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "numero", name="uq_lotepagamento_tenant_numero"),
        schema=S,
    )
    op.create_index(
        "ix_lotepagamento_tenant_situacao", "lote_pagamento",
        ["tenant_id", "situacao"], schema=S,
    )
    op.create_check_constraint(
        "ck_lotepagamento_situacao", "lote_pagamento",
        "situacao IN (" + _in(SITUACOES_LOTE) + ")", schema=S,
    )
    _rls("lote_pagamento")

    # ------------------------------------------------ lote_pagamento_parcela
    op.create_table(
        "lote_pagamento_parcela",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_lote", sa.Integer(),
            sa.ForeignKey(f"{S}.lote_pagamento.id"), nullable=False,
        ),
        sa.Column(
            "id_parcela", sa.Integer(),
            sa.ForeignKey(f"{S}.parcela.id"), nullable=False,
        ),
        sa.Column("situacao", sa.String(20), nullable=False, server_default="PENDENTE"),
        sa.Column("motivo_falha", sa.String(255), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        schema=S,
    )
    op.create_index(
        "ix_lotepagamentoparcela_tenant_lote", "lote_pagamento_parcela",
        ["tenant_id", "id_lote"], schema=S,
    )
    op.create_index(
        "uq_lotepagamentoparcela_parcela_ativa", "lote_pagamento_parcela",
        ["tenant_id", "id_parcela"], unique=True, schema=S,
        postgresql_where=sa.text("situacao <> 'FALHOU'"),
    )
    op.create_check_constraint(
        "ck_lotepagamentoparcela_situacao", "lote_pagamento_parcela",
        "situacao IN (" + _in(SITUACOES_LOTE_PARCELA) + ")", schema=S,
    )
    _rls("lote_pagamento_parcela")

    # -------------------------------------------------------------- retencao
    op.create_table(
        "retencao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_debito", sa.Integer(),
            sa.ForeignKey(f"{S}.debito.id"), nullable=False,
        ),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("descricao", sa.String(150), nullable=True),
        sa.Column("base_calculo", sa.Numeric(14, 2), nullable=False),
        sa.Column("aliquota", sa.Numeric(6, 3), nullable=True),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("recolhido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("data_recolhimento", sa.Date(), nullable=True),
        sa.Column("documento_recolhimento", sa.String(50), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        schema=S,
    )
    op.create_index(
        "ix_retencao_tenant_debito", "retencao", ["tenant_id", "id_debito"], schema=S,
    )
    op.create_index(
        "ix_retencao_tenant_recolhido", "retencao",
        ["tenant_id", "recolhido"], schema=S,
        postgresql_where=sa.text("excluido = false"),
    )
    op.create_check_constraint(
        "ck_retencao_tipo", "retencao",
        "tipo IN (" + _in(TIPOS_RETENCAO) + ")", schema=S,
    )
    _rls("retencao")

    # ---------------------------------------------------- ck_debhist_acao +7
    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")
    op.create_check_constraint(
        "ck_debhist_acao", "debito_historico",
        f"acao IN ({_in(ACAO_ANTERIOR + ACOES_NOVAS)})", schema=S,
    )


def downgrade() -> None:
    op.execute(
        f"DELETE FROM {S}.debito_historico WHERE acao IN ({_in(ACOES_NOVAS)})"
    )
    op.drop_constraint("ck_debhist_acao", "debito_historico", schema=S, type_="check")
    op.create_check_constraint(
        "ck_debhist_acao", "debito_historico",
        f"acao IN ({_in(ACAO_ANTERIOR)})", schema=S,
    )

    op.execute(f"DROP INDEX IF EXISTS {S}.ix_retencao_tenant_recolhido")
    op.execute(f"DROP INDEX IF EXISTS {S}.ix_retencao_tenant_debito")
    op.drop_table("retencao", schema=S)

    op.execute(f"DROP INDEX IF EXISTS {S}.uq_lotepagamentoparcela_parcela_ativa")
    op.execute(f"DROP INDEX IF EXISTS {S}.ix_lotepagamentoparcela_tenant_lote")
    op.drop_table("lote_pagamento_parcela", schema=S)

    op.execute(f"DROP INDEX IF EXISTS {S}.ix_lotepagamento_tenant_situacao")
    op.drop_table("lote_pagamento", schema=S)
