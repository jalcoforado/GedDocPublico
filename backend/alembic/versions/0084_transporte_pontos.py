"""Transporte Regulado P6 — pontos e vagas.

Revision ID: 0084
Revises: 0083
Create Date: 2026-08-05

Spec: `docs/superpowers/specs/2026-08-05-transporte-p6-pontos-design.md`.

Duas tabelas. O que carrega a fatia são os **dois índices únicos parciais** de
`ponto_ocupacao`, e eles não são detalhe de performance:

- `ux_pontoocup_vaga_vigente` — uma vaga, um ocupante.
- `ux_pontoocup_permissionario_vigente` — um permissionário, uma vaga.

A exclusividade mora aqui e não num `if` do serviço. É a lição da P5.1, escrita
naquela spec e válida igual: duas requisições concorrentes de "ocupar a vaga 3"
passariam **as duas** por uma checagem de serviço, porque entre o `SELECT` e o
`INSERT` não há nada segurando. O serviço continua checando — para devolver 409
com mensagem útil em vez de erro de integridade cru —, mas quem garante é o
índice, e há teste que remove o serviço do caminho para provar isso.

O `WHERE ate IS NULL AND excluido = false` é o que torna o histórico possível:
ocupação encerrada sai do índice, então a mesma vaga pode ser ocupada de novo
sem apagar a linha anterior.

**Não existe tabela de vaga.** A vaga é o inteiro `numero_vaga`, validado contra
`ponto.vagas_total` no serviço. Uma tabela cujo único conteúdo é um número
sequencial custaria join em toda leitura e daria, de novo, exatamente o que
estes índices já dão.

Boilerplate de RLS completo nas duas. Os três detalhes que custaram 20 policies
quebradas por 7 meses neste mesmo schema, corrigidas na 0078: a GUC é
`app.tenant_id` e não `app.current_tenant_id`; o segundo argumento `true` do
`current_setting` NÃO é opcional — sem ele a policy **derruba a consulta** em
vez de negar; e `ENABLE` sem `FORCE` não protege nada enquanto o dono da tabela
for também o papel do runtime.

Sem GRANT para `aprimora_worker`: nenhuma task Celery escreve aqui. O worker é
enumerado de propósito, nunca por cobertor.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0084"
down_revision: str | Sequence[str] | None = "0083"
branch_labels = None
depends_on = None

S = "transporte_regulado"

GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"


def _rls(tabela: str) -> None:
    """Boilerplate de RLS + grants. Idêntico para as duas tabelas."""
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
    # ------------------------------------------------------------- ponto
    op.create_table(
        "ponto",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("codigo", sa.String(40), nullable=True),
        # Sem CHECK restringindo a taxi|mototaxi: o resto do módulo trata
        # `tipo_servico` como texto livre, e apertar só aqui criaria uma
        # incoerência que o próximo desenvolvedor teria de descobrir sozinho.
        # O formulário sugere; o banco não impõe.
        sa.Column("tipo_servico", sa.String(30), nullable=False),
        sa.Column("logradouro", sa.String(200), nullable=True),
        sa.Column("numero", sa.String(20), nullable=True),
        sa.Column("complemento", sa.String(100), nullable=True),
        sa.Column("bairro", sa.String(100), nullable=True),
        sa.Column("cep", sa.String(9), nullable=True),
        sa.Column("vagas_total", sa.Integer(), nullable=False),
        sa.Column(
            "situacao", sa.String(20), nullable=False, server_default="ativo",
        ),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("false"),
        ),
        sa.CheckConstraint("vagas_total > 0", name="ck_ponto_vagas_total_positivo"),
        sa.CheckConstraint(
            "situacao IN ('ativo', 'inativo')", name="ck_ponto_situacao",
        ),
        schema=S,
    )
    op.create_index("ix_ponto_tenant", "ponto", ["tenant_id"], schema=S)
    op.create_index(
        "ix_ponto_tenant_tipo", "ponto", ["tenant_id", "tipo_servico"], schema=S,
    )
    # Dois pontos com o mesmo nome no mesmo município são erro de digitação, não
    # cadastro legítimo. `lower(...)` porque a diferença de caixa não distingue
    # nada para quem lê a lista.
    op.execute(
        f"CREATE UNIQUE INDEX ux_ponto_nome ON {S}.ponto "
        f"(tenant_id, lower(nome)) WHERE excluido = false"
    )
    _rls("ponto")

    # -------------------------------------------------------- ocupação
    op.create_table(
        "ponto_ocupacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_ponto", sa.Integer(),
            sa.ForeignKey(f"{S}.ponto.id"), nullable=False,
        ),
        sa.Column("numero_vaga", sa.Integer(), nullable=False),
        # FK para permissionário, e a coerência de tenant é do serviço: a FK do
        # Postgres não filtra por tenant.
        sa.Column(
            "id_permissionario", sa.Integer(),
            sa.ForeignKey(f"{S}.permissionario.id"), nullable=False,
        ),
        sa.Column("desde", sa.Date(), nullable=False),
        # NULL = vigente. É este NULL que o índice único parcial usa.
        sa.Column("ate", sa.Date(), nullable=True),
        sa.Column("motivo_liberacao", sa.String(30), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("false"),
        ),
        sa.CheckConstraint("numero_vaga > 0", name="ck_pontoocup_vaga_positiva"),
        sa.CheckConstraint(
            "ate IS NULL OR ate >= desde", name="ck_pontoocup_vigencia",
        ),
        schema=S,
    )
    op.create_index(
        "ix_pontoocup_tenant_ponto", "ponto_ocupacao",
        ["tenant_id", "id_ponto"], schema=S,
    )
    op.create_index(
        "ix_pontoocup_tenant_permissionario", "ponto_ocupacao",
        ["tenant_id", "id_permissionario"], schema=S,
    )
    # Os dois índices que carregam a fatia — ver o docstring do módulo.
    op.execute(
        f"CREATE UNIQUE INDEX ux_pontoocup_vaga_vigente ON {S}.ponto_ocupacao "
        f"(id_ponto, numero_vaga) WHERE ate IS NULL AND excluido = false"
    )
    op.execute(
        f"CREATE UNIQUE INDEX ux_pontoocup_permissionario_vigente "
        f"ON {S}.ponto_ocupacao (tenant_id, id_permissionario) "
        f"WHERE ate IS NULL AND excluido = false"
    )
    _rls("ponto_ocupacao")


def downgrade() -> None:
    # Ordem inversa: a filha antes da mãe.
    op.execute(f"DROP INDEX IF EXISTS {S}.ux_pontoocup_permissionario_vigente")
    op.execute(f"DROP INDEX IF EXISTS {S}.ux_pontoocup_vaga_vigente")
    op.drop_index(
        "ix_pontoocup_tenant_permissionario", table_name="ponto_ocupacao", schema=S,
    )
    op.drop_index("ix_pontoocup_tenant_ponto", table_name="ponto_ocupacao", schema=S)
    op.drop_table("ponto_ocupacao", schema=S)

    op.execute(f"DROP INDEX IF EXISTS {S}.ux_ponto_nome")
    op.drop_index("ix_ponto_tenant_tipo", table_name="ponto", schema=S)
    op.drop_index("ix_ponto_tenant", table_name="ponto", schema=S)
    op.drop_table("ponto", schema=S)
