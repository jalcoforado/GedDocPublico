"""Contratos G1 — `pagamentos.contrato` ganha situação, exercício e os dados do SIM.

Revision ID: 0132
Revises: 0131
Create Date: 2026-10-08

Spec: `docs/superpowers/specs/2026-10-08-contratos-g1-modulo-e-contrato-design.md`
(§3.1). A tabela NÃO muda de schema (decisão Q1): o dono é quem tem a
transação, não o nome do schema.

O que muda de significado sem mudar de nome: `valor_total`, `vigencia_inicio` e
`vigencia_fim` passam a ser **os originais**, congelados na assinatura. Valor
atualizado e vigência atual são derivados dos aditivos e apostilas (0133) e
nunca gravados aqui — `tests/test_guarda_contrato_derivado.py` trava.

Backfill:

- `situacao = 'VIGENTE'` em toda linha existente (é também o DEFAULT da coluna):
  contrato cadastrado por pagamentos nunca teve rascunho.
- `exercicio` = ano de `vigencia_inicio`. Não há data de celebração no legado, e
  a vigência é o dado mais próximo que toda linha tem.

Índice único: sai `(tenant_id, numero)`, entra `(tenant_id, exercicio, numero)`
— o SIM (tabela 511, campo 4) exige unicidade **por exercício**, e município
reinicia a numeração todo ano. A troca só afrouxa: nenhuma linha válida hoje
deixa de ser. Por isso o `downgrade` pode FALHAR ao recriar o índice antigo, se
nesse intervalo dois exercícios tiverem recebido o mesmo número. É o
comportamento certo — desfazer em silêncio perderia dado.

`ADD COLUMN` herda RLS e grants; nada a repetir.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0132"
down_revision: str | Sequence[str] | None = "0131"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "pagamentos"
T = f"{S}.contrato"

SITUACOES = ("RASCUNHO", "VIGENTE", "ENCERRADO", "RESCINDIDO")
# As 18 categorias do campo 6 da tabela 511 do SIM (Manual do SIM 2026).
TIPOS_OBJETO = "ABCDEFGHIJKLMNOPQR"


def upgrade() -> None:
    op.add_column("contrato", sa.Column(
        "situacao", sa.String(15), nullable=False, server_default="VIGENTE"), schema=S)
    op.add_column("contrato", sa.Column("exercicio", sa.Integer(), nullable=True), schema=S)
    op.add_column("contrato", sa.Column("data_celebracao", sa.Date(), nullable=True), schema=S)
    op.add_column("contrato", sa.Column("tipo_objeto", sa.String(1), nullable=True), schema=S)
    op.add_column("contrato", sa.Column("natureza_duracao", sa.String(10), nullable=True), schema=S)
    op.add_column("contrato", sa.Column(
        "reforma", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")), schema=S)
    op.add_column("contrato", sa.Column(
        "id_processo", sa.Integer(), sa.ForeignKey("protocolos.processo.id"), nullable=True),
        schema=S)
    op.add_column("contrato", sa.Column("processo_numero", sa.String(15), nullable=True), schema=S)
    op.add_column("contrato", sa.Column("processo_data_autuacao", sa.Date(), nullable=True), schema=S)
    op.add_column("contrato", sa.Column("pncp_id", sa.String(25), nullable=True), schema=S)
    op.add_column("contrato", sa.Column("pncp_publicado_em", sa.Date(), nullable=True), schema=S)
    op.add_column("contrato", sa.Column("data_encerramento", sa.Date(), nullable=True), schema=S)
    op.add_column("contrato", sa.Column("motivo_rescisao", sa.String(500), nullable=True), schema=S)

    # Backfill inclui os soft-deletados: a coluna vira NOT NULL para a tabela
    # inteira, e a 0107 já pagou por um backfill que esqueceu `excluido`.
    op.execute(f"UPDATE {T} SET exercicio = EXTRACT(YEAR FROM vigencia_inicio)::int")
    op.alter_column("contrato", "exercicio", nullable=False, schema=S)

    op.alter_column("contrato", "objeto", type_=sa.String(3000),
                    existing_type=sa.String(255), existing_nullable=False, schema=S)

    situacoes = ", ".join(f"'{s}'" for s in SITUACOES)
    op.create_check_constraint(
        "ck_contrato_situacao", "contrato", f"situacao IN ({situacoes})", schema=S)
    tipos = ", ".join(f"'{c}'" for c in TIPOS_OBJETO)
    op.create_check_constraint(
        "ck_contrato_tipo_objeto", "contrato",
        f"tipo_objeto IS NULL OR tipo_objeto IN ({tipos})", schema=S)
    op.create_check_constraint(
        "ck_contrato_natureza_duracao", "contrato",
        "natureza_duracao IS NULL OR natureza_duracao IN ('ESCOPO', 'CONTINUO')", schema=S)

    op.drop_index("uq_contrato_tenant_numero", table_name="contrato", schema=S)
    op.create_index(
        "uq_contrato_tenant_exercicio_numero", "contrato",
        ["tenant_id", "exercicio", "numero"], unique=True, schema=S,
        postgresql_where=sa.text("excluido = false"))
    op.create_index(
        "ix_contrato_tenant_situacao_vigencia", "contrato",
        ["tenant_id", "situacao", "vigencia_fim"], schema=S)
    op.create_index("ix_contrato_processo", "contrato", ["id_processo"], schema=S)


def downgrade() -> None:
    op.drop_index("ix_contrato_processo", table_name="contrato", schema=S)
    op.drop_index("ix_contrato_tenant_situacao_vigencia", table_name="contrato", schema=S)
    op.drop_index("uq_contrato_tenant_exercicio_numero", table_name="contrato", schema=S)
    # Pode falhar de propósito — ver docstring.
    op.create_index(
        "uq_contrato_tenant_numero", "contrato", ["tenant_id", "numero"], unique=True,
        schema=S, postgresql_where=sa.text("excluido = false"))

    op.drop_constraint("ck_contrato_natureza_duracao", "contrato", schema=S, type_="check")
    op.drop_constraint("ck_contrato_tipo_objeto", "contrato", schema=S, type_="check")
    op.drop_constraint("ck_contrato_situacao", "contrato", schema=S, type_="check")

    # Objeto volta a 255: trunca o que cresceu. É perda declarada, e a única
    # alternativa seria um downgrade que não desfaz o upgrade.
    op.execute(f"UPDATE {T} SET objeto = LEFT(objeto, 255) WHERE LENGTH(objeto) > 255")
    op.alter_column("contrato", "objeto", type_=sa.String(255),
                    existing_type=sa.String(3000), existing_nullable=False, schema=S)

    for coluna in (
        "motivo_rescisao", "data_encerramento", "pncp_publicado_em", "pncp_id",
        "processo_data_autuacao", "processo_numero", "id_processo", "reforma",
        "natureza_duracao", "tipo_objeto", "data_celebracao", "exercicio", "situacao",
    ):
        op.drop_column("contrato", coluna, schema=S)
