"""Retorno do sistema financeiro: valor empenhado e valor liquidado no débito.

Revision ID: 0144
Revises: 0143
Create Date: 2026-11-24

Até aqui o módulo sabia o NÚMERO do empenho (`debito.numero_ne`, string livre)
e que a liquidação foi confirmada (`liquidacao_confirmada`, booleano), mas não
sabia QUANTO foi empenhado nem QUANTO foi liquidado. O export contábil já
emitia os eventos `debito_empenhado` e `liquidacao`
(`services/pagamentos_contabil.py`), só que sem valor — a ida existia, a volta
não tinha onde pousar.

Três colunas, por decisão do Jorge em 2026-11-24 ("vamos fazer simplificado,
por coluna mesmo; se mudar na conciliação vai vir o novo falar e a gente
atualiza"):

- `valor_empenhado` / `valor_liquidado` — NULL de propósito, e NULL não é zero:
  significa "o sistema financeiro ainda não devolveu este valor". Zero seria
  uma afirmação sobre o empenho, e aqui a ausência de resposta é o estado
  normal de todo débito que já existe.
- `revisado` — marca que os valores vieram do retorno do sistema financeiro.
  É a resposta à pergunta "quem é a fonte da verdade": o retorno escreve e
  marca; a edição material do débito (`atualizar_debito`) desmarca, para que
  divergência entre as duas pontas APAREÇA em vez de passar em silêncio.

**Por que isto NÃO mexe no saldo:** `comprometido_conta`
(`services/pagamentos_caixa.py:59`) soma parcelas em aberto de débitos
AUTORIZADOS — o comprometido é do solicitado e autorizado, não do empenhado
(decisão do Jorge, 2026-11-24). Empenhado e liquidado entram como informação
gerencial e de conferência; nenhum indicador de disponibilidade muda de valor
por causa desta migration. Isso é deliberado: se um dia o comprometido passar
a olhar o empenho, é outra fatia, com outra conversa.

`EMPENHO_REGISTRADO` entra no CHECK de `debito_historico.acao` porque o
registro do empenho vira linha de trilha. A liquidação com valor reusa a ação
`LIQUIDADO` que já existe — é o mesmo evento, agora com um dado a mais.

`ADD COLUMN` herda RLS e grants (CLAUDE.md §Migrations).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0144"
down_revision: str | Sequence[str] | None = "0143"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A lista vigente da 0143 + EMPENHO_REGISTRADO. Mantida por extenso porque o
# CHECK é recriado inteiro: omitir um valor aqui quebraria escrita de histórico
# já existente em produção.
_ACOES = (
    "CRIADO", "ENVIADO", "APROVADO", "VALIDADO", "ENCAMINHADO", "DEVOLVIDO",
    "REJEITADO", "AUTORIZADO", "LIBERADO", "LIBERACAO_REVOGADA", "PAGAMENTO",
    "ESTORNO", "CANCELADO", "LIQUIDADO", "SUSPENSO", "REATIVADO", "CONCILIADO",
    "AUTORIZADO_GESTOR", "REJEITADO_GESTOR", "AJUSTE_SOLICITADO",
    "AJUSTE_RESPONDIDO", "INDEFERIDO", "ENVIADO_TESOURARIA", "REVOGADO",
    "PAGO", "PROCESSANDO", "ESTORNADO", "REENVIADO", "APROVACOES_INVALIDADAS",
    "MARCO_REGRAVADO", "FILA_REAVALIADA", "EXCECAO_AUTORIZADA", "LOTE_CRIADO",
    "LOTE_PROGRAMADO", "LOTE_ENVIADO", "PAGAMENTO_CONFIRMADO",
    "PAGAMENTO_FALHOU", "LOTE_CANCELADO", "RETENCAO_RECOLHIDA",
    "CONCILIACAO_DESFEITA",
    "EMPENHO_REGISTRADO",
)

_SEM_EMPENHO_REGISTRADO = tuple(a for a in _ACOES if a != "EMPENHO_REGISTRADO")


def _lista(acoes: Sequence[str]) -> str:
    return ", ".join(f"'{a}'" for a in acoes)


def upgrade() -> None:
    op.execute("""
        ALTER TABLE pagamentos.debito
            ADD COLUMN valor_empenhado numeric(14, 2),
            ADD COLUMN valor_liquidado numeric(14, 2),
            ADD COLUMN revisado boolean NOT NULL DEFAULT false
    """)
    op.execute("ALTER TABLE pagamentos.debito_historico DROP CONSTRAINT ck_debhist_acao")
    op.execute(
        "ALTER TABLE pagamentos.debito_historico ADD CONSTRAINT ck_debhist_acao "
        f"CHECK (acao::text = ANY (ARRAY[{_lista(_ACOES)}]::text[]))"
    )


def downgrade() -> None:
    # Linhas gravadas com a ação nova viram inválidas para o CHECK antigo —
    # apagá-las silenciosamente destruiria trilha de auditoria, então o
    # downgrade falha alto se existir alguma.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pagamentos.debito_historico
                       WHERE acao = 'EMPENHO_REGISTRADO') THEN
                RAISE EXCEPTION
                    'Há trilha com acao=EMPENHO_REGISTRADO; downgrade apagaria auditoria.';
            END IF;
        END $$
    """)
    op.execute("ALTER TABLE pagamentos.debito_historico DROP CONSTRAINT ck_debhist_acao")
    op.execute(
        "ALTER TABLE pagamentos.debito_historico ADD CONSTRAINT ck_debhist_acao "
        f"CHECK (acao::text = ANY (ARRAY[{_lista(_SEM_EMPENHO_REGISTRADO)}]::text[]))"
    )
    op.execute("""
        ALTER TABLE pagamentos.debito
            DROP COLUMN revisado,
            DROP COLUMN valor_liquidado,
            DROP COLUMN valor_empenhado
    """)
