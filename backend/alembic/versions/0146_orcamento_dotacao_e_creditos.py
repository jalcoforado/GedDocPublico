"""Orçamento: dotação, créditos adicionais e o vínculo da despesa (O1).

Revision ID: 0146
Revises: 0145
Create Date: 2026-11-24

Escopo autorizado por Jorge em 2026-11-24 ("o orçamento entra no escopo").
Esta é a FUNDAÇÃO: sem ela, "disponibilidade orçamentária" e "execução
orçamentária" não têm de onde sair, e o catálogo de indicadores as declara
como inexistentes.

## O que entra

- `pagamentos.dotacao` — a dotação de um exercício, com a classificação
  funcional-programática e a natureza da despesa. Guardamos a classificação em
  COLUNAS do próprio registro, e não em seis tabelas de catálogo (função,
  subfunção, programa, ação…). É simplificação deliberada: a prefeitura
  importa a classificação pronta do sistema orçamentário dela, e catalogar cada
  eixo exigiria seis cadastros que ninguém vai manter à mão. Se um dia a
  classificação precisar de hierarquia navegável, ela vira tabela sem quebrar
  esta — os códigos continuam os mesmos.
- `pagamentos.credito_adicional` — suplementação, crédito especial,
  extraordinário e ANULAÇÃO. A dotação ATUALIZADA é derivada
  (`valor_inicial + Σ créditos`), nunca uma coluna: coluna derivada mantida por
  código é fonte de divergência, lição que a F5 deste módulo já pagou ao
  remover o `status` legado do débito.
- `debito.id_dotacao` e `debito.exercicio` — o vínculo que torna a execução
  calculável.

## O que NÃO entra, e por quê

- **Reserva orçamentária** (bloqueio prévio de dotação, antes do empenho): é um
  rito a mais, com ato próprio e cancelamento, e o módulo ainda não tem a
  decisão de quem reserva. O catálogo continua declarando que não existe.
- **Restos a pagar**: agora é POSSÍVEL (a despesa passa a ter exercício), mas
  depende do processo de virada de exercício, que é outra fatia.
- **Empenho automático contra a dotação**: o valor empenhado continua vindo do
  retorno do sistema financeiro (migration 0144). O Aprimora não empenha; ele
  registra o que foi empenhado e confere.

## A regra que não pode ser quebrada

`id_dotacao` é NULLABLE de propósito. Toda despesa que já existe neste banco
nasceu sem dotação, e exigir o vínculo agora travaria o módulo inteiro no dia
do deploy. A consequência é honesta e aparece na tela: despesa sem dotação não
entra na execução orçamentária, e o painel informa quanto do pago está nessa
situação — em vez de inventar um rateio.

`ADD COLUMN` herda RLS e grants; tabela nova precisa do boilerplate explícito
(CLAUDE.md §Migrations).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0146"
down_revision: str | Sequence[str] | None = "0145"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "pagamentos"
GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"

_TABELAS = ("dotacao", "credito_adicional")


def _blindar(tabela: str) -> None:
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
    op.create_table(
        "dotacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"),
                  nullable=False),
        sa.Column("exercicio", sa.Integer(), nullable=False),
        # Unidade orçamentária: reusa a unidade de trabalho, que é onde o
        # módulo já guarda "de quem é a despesa" (Debito.id_unidade).
        sa.Column("id_unidade", sa.Integer(), sa.ForeignKey("utils.unidade_trabalho.id"),
                  nullable=False),
        # Classificação funcional-programática, como códigos.
        sa.Column("funcao", sa.String(10), nullable=False),
        sa.Column("subfuncao", sa.String(10), nullable=False),
        sa.Column("programa", sa.String(20), nullable=False),
        sa.Column("acao", sa.String(20), nullable=False),
        # Natureza da despesa: o código completo (ex.: 3.3.90.30) e o grupo,
        # que é o eixo que o módulo já usa em GrupoDespesa.
        sa.Column("natureza_codigo", sa.String(20), nullable=False),
        sa.Column("grupo_despesa", sa.String(20), nullable=False),
        sa.Column("id_fonte_recursos", sa.Integer(),
                  sa.ForeignKey("pagamentos.fonte_recursos.id"), nullable=False),
        sa.Column("descricao", sa.String(255), nullable=False),
        sa.Column("valor_inicial", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=S,
    )
    # Uma dotação por classificação completa dentro do exercício. É a chave
    # natural do orçamento: duas linhas iguais seriam a mesma dotação contada
    # duas vezes, e a execução sairia pela metade.
    op.execute(
        f"CREATE UNIQUE INDEX ux_dotacao_classificacao ON {S}.dotacao "
        "(tenant_id, exercicio, id_unidade, funcao, subfuncao, programa, acao, "
        " natureza_codigo, id_fonte_recursos) WHERE NOT excluido"
    )
    op.execute(f"CREATE INDEX ix_dotacao_exercicio ON {S}.dotacao (tenant_id, exercicio)")

    op.create_table(
        "credito_adicional",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"),
                  nullable=False),
        sa.Column("id_dotacao", sa.Integer(), sa.ForeignKey("pagamentos.dotacao.id"),
                  nullable=False),
        # SUPLEMENTAR, ESPECIAL, EXTRAORDINARIO, ANULACAO.
        sa.Column("tipo", sa.String(20), nullable=False),
        # SEMPRE positivo. O sinal é do tipo, não do valor: valor negativo
        # gravado por engano viraria suplementação que diminui a dotação, e
        # ninguém olharia duas vezes para um número positivo na soma.
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        # Lei ou decreto que autorizou — crédito adicional sem ato não existe.
        sa.Column("ato", sa.String(120), nullable=False),
        sa.Column("justificativa", sa.String(255), nullable=True),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=S,
    )
    op.execute(
        f"ALTER TABLE {S}.credito_adicional ADD CONSTRAINT ck_credito_tipo "
        "CHECK (tipo IN ('SUPLEMENTAR', 'ESPECIAL', 'EXTRAORDINARIO', 'ANULACAO'))"
    )
    op.execute(
        f"ALTER TABLE {S}.credito_adicional ADD CONSTRAINT ck_credito_valor_positivo "
        "CHECK (valor >= 0)"
    )
    op.execute(
        f"CREATE INDEX ix_credito_dotacao ON {S}.credito_adicional (tenant_id, id_dotacao)"
    )

    for t in _TABELAS:
        _blindar(t)

    # Vínculo da despesa. Nullable: ver o cabeçalho.
    op.execute(f"""
        ALTER TABLE {S}.debito
            ADD COLUMN id_dotacao integer REFERENCES {S}.dotacao(id),
            ADD COLUMN exercicio integer
    """)
    op.execute(f"CREATE INDEX ix_debito_dotacao ON {S}.debito (tenant_id, id_dotacao)")
    # Backfill do exercício a partir da competência (YYYY-MM), que toda despesa
    # tem e é NOT NULL. Não é adivinhação: a competência é o mês de referência
    # informado por quem abriu a despesa.
    op.execute(f"UPDATE {S}.debito SET exercicio = LEFT(competencia, 4)::int "
               "WHERE exercicio IS NULL AND competencia ~ '^[0-9]{4}-'")


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {S}.ix_debito_dotacao")
    op.execute(f"ALTER TABLE {S}.debito DROP COLUMN exercicio, DROP COLUMN id_dotacao")
    for t in reversed(_TABELAS):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {S}.{t}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {S}.{t}")
    op.drop_table("credito_adicional", schema=S)
    op.execute(f"DROP INDEX IF EXISTS {S}.ix_dotacao_exercicio")
    op.execute(f"DROP INDEX IF EXISTS {S}.ux_dotacao_classificacao")
    op.drop_table("dotacao", schema=S)
