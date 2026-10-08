"""Contratos G1 — módulo `contratos` no catálogo e transação `contrato`.

Revision ID: 0131
Revises: 0130
Create Date: 2026-10-08

Sexto módulo contratável. Spec:
`docs/superpowers/specs/2026-10-08-contratos-g1-modulo-e-contrato-design.md`
(§3.3 e §4).

Duas coisas que esta migration NÃO faz, de propósito:

- **Não contrata o módulo para ninguém.** A 0073 fez backfill em todo tenant
  porque estava dividindo um sistema que todos já tinham inteiro. Aqui o módulo
  é novo: contratação é ato comercial, e um INSERT em `tenant_modulo` daria o
  módulo a todo município de uma vez (decisão Q4 do spec). Banco limpo recebe
  pelo `seed_bootstrap`; tenant existente, pelo seed de demonstração ou pela
  aba Módulos.
- **Não liga a transação ao módulo nem ao sistema.** Como na 0074 e na 0090, o
  vínculo é do `seed_bootstrap` (`MODULO_TRANSACOES`), que roda depois.

Idempotente por `ON CONFLICT`/`WHERE NOT EXISTS`.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0131"
down_revision: str | Sequence[str] | None = "0130"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG = "contratos"
NOME = "Contratos e Convênios"
ICONE = "FileSignature"
# Depois de Pagamentos (2) faria mais sentido no launcher, mas renumerar a
# ordem dos outros quatro numa migration de catálogo mexe em linha que o
# operador pode ter ajustado. Entra no fim dos contratáveis; `comum` é 99.
ORDEM = 6

CODIGO = "contrato"
ROTULO = "Contratos"


def upgrade() -> None:
    op.execute(f"""
        INSERT INTO aprimora_py.modulo (slug, nome, icone, ordem, contratavel)
        SELECT '{SLUG}', '{NOME}', '{ICONE}', {ORDEM}, true
         WHERE NOT EXISTS (SELECT 1 FROM aprimora_py.modulo WHERE slug = '{SLUG}')
    """)
    op.execute(
        "INSERT INTO utils.transacao (transacao, codigo, excluido) "
        f"VALUES ('{ROTULO}', '{CODIGO}', false) "
        "ON CONFLICT (codigo) DO NOTHING"
    )


def downgrade() -> None:
    # O vínculo módulo<->transação é derivado (o seed_bootstrap o recria a
    # partir de MODULO_TRANSACOES), então sai primeiro e sem condição — é ele
    # que prenderia por FK os dois DELETEs seguintes.
    op.execute(f"""
        DELETE FROM aprimora_py.modulo_transacao mt
         USING aprimora_py.modulo m
         WHERE mt.id_modulo = m.id AND m.slug = '{SLUG}'
    """)
    # Mesma cautela da 0074: não arrancar permissão de usuário real.
    op.execute(f"""
        DELETE FROM utils.transacao t
         WHERE t.codigo = '{CODIGO}'
           AND NOT EXISTS (
               SELECT 1 FROM utils.grupo_transacao gt WHERE gt.id_transacao = t.id
           )
           AND NOT EXISTS (
               SELECT 1 FROM utils.sistema_transacao st WHERE st.id_transacao = t.id
           )
    """)
    # O módulo só sai se nenhum tenant tem linha de contratação (viva ou
    # soft-deletada): a FK de `tenant_modulo` para `modulo` não é CASCADE, e
    # apagar a contratação aqui seria descontratar município por downgrade.
    op.execute(f"""
        DELETE FROM aprimora_py.modulo m
         WHERE m.slug = '{SLUG}'
           AND NOT EXISTS (
               SELECT 1 FROM aprimora_py.tenant_modulo tm WHERE tm.id_modulo = m.id
           )
    """)
