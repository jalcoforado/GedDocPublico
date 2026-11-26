"""Protocolo — tipo de manifestante diz se é pessoa física ou jurídica.

Revision ID: 0136
Revises: 0135
Create Date: 2026-11-03

O cadastro de manifestante passa a formatar o documento conforme o tipo
escolhido: CPF para pessoa física, CNPJ para jurídica. Até aqui nada no tipo
dizia qual dos dois ele é — o nome é texto livre da prefeitura, e
`id_categoria` aponta para `protocolos.categoria`, que está vazia.

`protocolos.tipo_manifestante` ganha `natureza` (`'F'` física, `'J'` jurídica),
com CHECK. Backfill: tipo cujo nome fala em "jurídica" vira `'J'`; o resto
nasce `'F'`, que é o único tipo que o provisionamento criava.

Toda prefeitura que ainda não tem tipo jurídico ganha "Pessoa Jurídica". Quem
provisiona tenant novo passa a criar os dois (`provisioning_tenant`).

`ADD COLUMN` em tabela existente herda RLS e grants. O downgrade remove a
coluna, mas NÃO apaga os tipos "Pessoa Jurídica" criados aqui: depois do
upgrade eles podem já ter manifestantes apontando para eles.
"""
from __future__ import annotations

from alembic import op

revision = "0136"
down_revision = "0135"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE protocolos.tipo_manifestante
            ADD COLUMN natureza char(1) NOT NULL DEFAULT 'F',
            ADD CONSTRAINT ck_tipo_manifestante_natureza CHECK (natureza IN ('F', 'J'))
    """)
    # "Jurídica", "JURIDICA", "Pessoa jurídica"... — sem depender da extensão unaccent.
    op.execute("""
        UPDATE protocolos.tipo_manifestante
           SET natureza = 'J'
         WHERE lower(translate(tipo_manifestante, 'Íí', 'Ii')) LIKE '%juridic%'
    """)
    op.execute("""
        INSERT INTO protocolos.tipo_manifestante
            (tenant_id, tipo_manifestante, id_categoria, natureza, ativo, excluido)
        SELECT t.id, 'Pessoa Jurídica', 1, 'J', true, false
          FROM aprimora_py.tenant t
         WHERE NOT EXISTS (
                SELECT 1 FROM protocolos.tipo_manifestante tm
                 WHERE tm.tenant_id = t.id AND tm.natureza = 'J' AND tm.excluido = false
         )
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE protocolos.tipo_manifestante
            DROP CONSTRAINT IF EXISTS ck_tipo_manifestante_natureza,
            DROP COLUMN IF EXISTS natureza
    """)
