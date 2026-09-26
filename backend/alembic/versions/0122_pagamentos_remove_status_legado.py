"""Pagamentos F5 — remove a coluna status legada de debito.

Revision ID: 0122
Revises: 0120
Create Date: 2026-09-20

Numerada 0122, não 0121: a F4 (Task 1, PR #68, branch `pagamentos/f4-tesouraria`,
ainda não mesclada em `main`) já usa "0121" para `lote_pagamento`/
`lote_pagamento_parcela`/`retencao`. As duas foram cortadas de `main` no mesmo
dia e colidiram no ID. Descoberto em runtime, não em code review: como
`docker exec` roda contra o MESMO Postgres de desenvolvimento independente de
qual branch está com checkout no host, aplicar a F4 antes (para testá-la) e
depois tentar aplicar esta migration com o mesmo ID "0121" fez o Alembic
concluir — pela igualdade das strings de revisão, não pelo conteúdo do
arquivo — que já estava no head, sem rodar nada; e a tentativa seguinte de
`downgrade` correu a função ERRADA (a desta migration) sobre o estado
deixado pela OUTRA. Quem mesclar a F4 primeiro precisa conferir se esta
migration ainda precisa de renumeração (o inverso: F4 herdar 0122 e esta
ficar 0121) dependendo da ordem real de merge.

Desde a F1 (0085), `debito.status` (16 valores) é DERIVADO de três colunas
que passaram a ser a verdade — `situacao_tramitacao`, `situacao_fila`,
`situacao_pagamento` — via `services/pagamentos_estados.status_legado()`. A
coluna sobreviveu como "divergence risk" temporário (spec §4.2) enquanto
conciliação, exceções, caixa, export, filas, autorização e o frontend ainda a
liam. Essa migração incremental (F5, mesmo branch) terminou: nenhum código de
aplicação lê mais `debito.status` — quem precisa do valor legado (trilha de
auditoria em `debito_historico.status_anterior/novo`, coluna do CSV de
exportação) chama `status_legado()` na hora, sem persistir o resultado em
lugar nenhum além do próprio histórico.

Ordem do DROP: índice → constraint → coluna (a ordem inversa da criação em
0048; a constraint foi reescrita por 0067/0069 mas o nome `ck_debito_status`
nunca mudou).

`downgrade()` recria a coluna NULLABLE, sem backfill — não há como reconstruir
os 16 valores originais a partir das três dimensões com certeza retroativa
para todo histórico de transições já ocorridas (a função `status_legado()` é
determinística PARA FRENTE, calculada no momento de cada transição; rodá-la
hoje sobre o estado ATUAL de cada débito reconstituiria só o status corrente,
não os valores que a coluna teria assumido em cada ponto do passado — e
ninguém lê a coluna de volta, então reconstituir só o valor atual não serve a
nenhum consumidor real). Mesmo padrão de "downgrade não reconstrói dado que
não dá pra reconstruir com fidelidade" da 0107 (lá, um backfill; aqui, uma
coluna inteira).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0122"
down_revision: str | Sequence[str] | None = "0120"
branch_labels = None
depends_on = None
S = "pagamentos"


def upgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {S}.ix_debito_tenant_status")
    op.drop_constraint("ck_debito_status", "debito", schema=S, type_="check")
    op.drop_column("debito", "status", schema=S)


def downgrade() -> None:
    op.add_column("debito", sa.Column("status", sa.String(25), nullable=True), schema=S)
    op.create_check_constraint(
        "ck_debito_status", "debito",
        "status IN ('RASCUNHO','EM_VALIDACAO','DEVOLVIDO','VALIDADO','ENVIADO_SECRETARIO',"
        "'AGUARDANDO_AUTORIZACAO','AUTORIZADO','ENVIADO_TESOURARIA','EM_PROCESSAMENTO',"
        "'PAGO_PARCIAL','PAGO','CONCILIADO','REJEITADO','SUSPENSO','CANCELADO','ESTORNADO')",
        schema=S)
    op.create_index("ix_debito_tenant_status", "debito", ["tenant_id", "status"], schema=S)
