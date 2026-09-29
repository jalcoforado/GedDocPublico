"""Manifestante: CPF/CNPJ só com dígitos nos cadastros já gravados.

Revision ID: 0125
Revises: 0124

A partir desta versão o schema normaliza `cpf_cnpj` na entrada (só dígitos;
vazio vira NULL). Esta migration traz os cadastros antigos para o mesmo formato.

Por que importa além da estética: o portal do cidadão liga cidadão a processo
por `Manifestante.cpf_cnpj == cidadao.cpf_cnpj`, e o do cidadão é guardado sem
máscara — um manifestante gravado como "123.456.789-09" nunca aparecia para
ele. CNPJ com máscara (18 caracteres) nem cabia na coluna `varchar(14)`, então
só CPF com máscara e string vazia existem para corrigir.

Não há índice único em `cpf_cnpj`, então a normalização não colide.

Downgrade é no-op: a máscara original não é recuperável e nada depende dela.
"""
from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "0125"
down_revision: str | Sequence[str] | None = "0124"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Reaplicado por tests/test_manifestante_cpf_busca.py — mantenha o SQL aqui.
SQL_NORMALIZA = r"""
UPDATE protocolos.manifestante
   SET cpf_cnpj = NULLIF(regexp_replace(cpf_cnpj, '\D', '', 'g'), '')
 WHERE cpf_cnpj IS NOT NULL
   AND (cpf_cnpj = '' OR cpf_cnpj ~ '\D')
"""


def upgrade() -> None:
    op.execute(SQL_NORMALIZA)


def downgrade() -> None:
    pass
