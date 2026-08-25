"""Pagamentos C2 — FIX WAVE Critical: snapshot imutável no export contábil.

Revision ID: 0104
Revises: 0103
Create Date: 2026-08-24

`services/pagamentos_contabil.py::reconstruir_csv` reidratava cada evento do
domínio ATUAL (`_reidratar`, removida nesta fatia — ver blame do service).
Isso é um bug, não uma feature: uma edição LEGÍTIMA e POSTERIOR de cadastro
(PUT fornecedor/fonte/conta, ou `atualizar_debito` mudando valor/numero_ne
enquanto o débito ainda está em RASCUNHO) mudava o que a reconstrução
recalculava, o hash gravado na criação parava de bater, e o lote — que nunca
foi tocado — passava a devolver 500 "Corrupção detectada" PARA SEMPRE.

Fix: `ADD COLUMN snapshot JSONB` em `pagamentos.export_contabil_evento`. A
coluna nasce NULLABLE (não dá pra popular NOT NULL no mesmo `ALTER TABLE`
sem um default), o backfill abaixo regenera o snapshot das linhas
existentes A PARTIR DO DOMÍNIO — a mesma reidratação que o service fazia até
aqui, só que rodada UMA VEZ, nesta migration, e não a cada download — e só
então a coluna vira NOT NULL. Em produção só dev tem dados (o export
contábil é da própria Onda C2, ainda não usado por tenant real); o backfill
existe para não deixar a tabela inconsistente se algum dev já tiver gerado
lote localmente.

`ADD COLUMN` em tabela existente herda RLS e GRANTs da criação (migration
0101) — não repetidos aqui.

A partir desta migration, `gerar_lote` grava o snapshot na criação e
`reconstruir_csv` lê exclusivamente dele; `_montar_de_historico`/
`_montar_de_movimentacao` (que sobrevivem no service) só rodam na geração.
"""
from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0104"
down_revision: str | Sequence[str] | None = "0103"
branch_labels = None
depends_on = None

S = "pagamentos"

_TIPOS_HISTORICO = ("debito_empenhado", "liquidacao", "cancelamento_debito")
_TIPOS_MOVIMENTACAO = ("pagamento", "estorno_parcela")


def _moeda(v) -> str | None:
    return None if v is None else str(v)


def _iso(v) -> str | None:
    return None if v is None else v.isoformat()


def _motivo_de_descricao(descricao: str | None) -> str | None:
    """Mesma extração de `services/pagamentos_contabil.py::_motivo_de_descricao`
    — `descricao` de `movimentacao_conta` (origem ESTORNO) carrega
    "Estorno parcela N — débito #ID: <motivo>"."""
    if not descricao or ": " not in descricao:
        return None
    return descricao.split(": ", 1)[1]


def _backfill_snapshots() -> None:
    """Regenera o snapshot das linhas existentes reidratando do domínio —
    a mesma lógica que `reconstruir_csv` fazia antes desta fatia, rodada
    uma única vez. Sem efeito em banco sem dados no export contábil (o caso
    de praticamente todo ambiente hoje)."""
    bind = op.get_bind()

    # ------------------------------------------------------- tipo histórico
    rows = bind.execute(sa.text(f"""
        SELECT e.id AS evento_id, e.tenant_id, e.tipo_evento, e.id_origem,
               e.ocorrido_em, h.justificativa, h.criado_em AS h_criado_em,
               d.id AS debito_id, d.numero_ne, d.valor_total, d.data_liquidacao,
               f.cnpj_cpf, f.nome AS fornecedor_nome, fr.descricao AS fonte_descricao
        FROM {S}.export_contabil_evento e
        JOIN {S}.debito_historico h ON h.id = e.id_origem AND h.tenant_id = e.tenant_id
        JOIN {S}.debito d ON d.id = h.id_debito AND d.tenant_id = e.tenant_id
        LEFT JOIN {S}.fornecedor f ON f.id = d.id_fornecedor AND f.tenant_id = e.tenant_id
        LEFT JOIN {S}.fonte_recursos fr ON fr.id = d.id_fonte_recursos AND fr.tenant_id = e.tenant_id
        WHERE e.snapshot IS NULL AND e.tipo_evento IN :tipos
    """).bindparams(sa.bindparam("tipos", expanding=True)), {"tipos": list(_TIPOS_HISTORICO)}).mappings().all()

    for r in rows:
        snap = {
            "tipo_evento": r["tipo_evento"], "id_origem": r["id_origem"], "id_debito": r["debito_id"],
            "ocorrido_em": r["h_criado_em"].isoformat(),
            "numero_empenho": r["numero_ne"], "fonte": r["fonte_descricao"],
            "credor_doc": r["cnpj_cpf"], "credor_nome": r["fornecedor_nome"],
            "valor": _moeda(r["valor_total"]),
            "vencimento": None,
            "data_liquidacao": _iso(r["data_liquidacao"]) if r["tipo_evento"] == "liquidacao" else None,
            "numero_ordem": None, "conta": None, "data_pagamento": None, "valor_pago": None,
            "excecao_saldo": None, "justificativa": None,
            "motivo": r["justificativa"] if r["tipo_evento"] == "cancelamento_debito" else None,
        }
        bind.execute(sa.text(
            f"UPDATE {S}.export_contabil_evento SET snapshot = CAST(:s AS jsonb) WHERE id = :id"
        ), {"s": json.dumps(snap), "id": r["evento_id"]})

    # ---------------------------------------------------- tipo movimentação
    rows = bind.execute(sa.text(f"""
        SELECT e.id AS evento_id, e.tenant_id, e.tipo_evento, e.id_origem, e.ocorrido_em,
               m.id_debito, m.data AS m_data, m.valor AS m_valor, m.descricao AS m_descricao,
               d.numero_ne, f.cnpj_cpf, f.nome AS fornecedor_nome, fr.descricao AS fonte_descricao,
               cb.nome AS conta_nome, op.numero AS numero_ordem, op.excecao_saldo,
               op.justificativa_excecao
        FROM {S}.export_contabil_evento e
        JOIN {S}.movimentacao_conta m ON m.id = e.id_origem AND m.tenant_id = e.tenant_id
        LEFT JOIN {S}.debito d ON d.id = m.id_debito AND d.tenant_id = e.tenant_id
        LEFT JOIN {S}.fornecedor f ON f.id = d.id_fornecedor AND f.tenant_id = e.tenant_id
        LEFT JOIN {S}.fonte_recursos fr ON fr.id = d.id_fonte_recursos AND fr.tenant_id = e.tenant_id
        LEFT JOIN {S}.conta_bancaria cb ON cb.id = m.id_conta AND cb.tenant_id = e.tenant_id
        LEFT JOIN LATERAL (
            SELECT op2.numero, op2.excecao_saldo, op2.justificativa_excecao
            FROM {S}.ordem_pagamento_debito opd
            JOIN {S}.ordem_pagamento op2 ON op2.id = opd.id_ordem
            WHERE opd.id_debito = m.id_debito AND opd.tenant_id = e.tenant_id
            ORDER BY op2.id DESC LIMIT 1
        ) op ON m.id_debito IS NOT NULL
        WHERE e.snapshot IS NULL AND e.tipo_evento IN :tipos
    """).bindparams(sa.bindparam("tipos", expanding=True)), {"tipos": list(_TIPOS_MOVIMENTACAO)}).mappings().all()

    for r in rows:
        eh_pagamento = r["tipo_evento"] == "pagamento"
        snap = {
            "tipo_evento": r["tipo_evento"], "id_origem": r["id_origem"], "id_debito": r["id_debito"],
            "ocorrido_em": r["ocorrido_em"].isoformat(),
            "numero_empenho": r["numero_ne"], "fonte": r["fonte_descricao"],
            "credor_doc": r["cnpj_cpf"], "credor_nome": r["fornecedor_nome"],
            "valor": None if eh_pagamento else _moeda(r["m_valor"]),
            "vencimento": None, "data_liquidacao": None,
            "numero_ordem": r["numero_ordem"], "conta": r["conta_nome"],
            "data_pagamento": _iso(r["m_data"]) if eh_pagamento else None,
            "valor_pago": _moeda(r["m_valor"]) if eh_pagamento else None,
            "excecao_saldo": r["excecao_saldo"], "justificativa": r["justificativa_excecao"],
            "motivo": None if eh_pagamento else _motivo_de_descricao(r["m_descricao"]),
        }
        bind.execute(sa.text(
            f"UPDATE {S}.export_contabil_evento SET snapshot = CAST(:s AS jsonb) WHERE id = :id"
        ), {"s": json.dumps(snap), "id": r["evento_id"]})


def upgrade() -> None:
    op.add_column(
        "export_contabil_evento", sa.Column("snapshot", JSONB(), nullable=True), schema=S,
    )
    _backfill_snapshots()
    op.execute(f"ALTER TABLE {S}.export_contabil_evento ALTER COLUMN snapshot SET NOT NULL")


def downgrade() -> None:
    op.drop_column("export_contabil_evento", "snapshot", schema=S)
