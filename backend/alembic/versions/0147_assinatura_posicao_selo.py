"""Posição do selo da assinatura com senha na página do documento (SI-68).

Revision ID: 0147
Revises: 0146
Create Date: 2026-11-27

Quem assina escolhe onde o selo aparece no PDF: página e canto superior
esquerdo do quadrado, em FRAÇÃO da página como ela é vista na tela (0–1,
origem no canto superior esquerdo, já com a rotação da página aplicada). A
conversão para pontos do PDF fica no backend (`services/pdf_selo_assinatura.py`),
que conhece a caixa e a rotação de cada página.

## O original não muda

Só se guarda a POSIÇÃO. O selo é desenhado no PDF servido
(`/anexos/{id}/carimbado.pdf` e o processo completo), por cima do carimbo,
na hora do pedido. Gravar o selo no arquivo mudaria o SHA-256 que a assinatura
registrou em `documento_hash`: o `/validar` passaria a dizer "divergente" e
cada novo signatário invalidaria os anteriores.

## Linhas sem posição

As três colunas nulas são a assinatura sem selo: as legadas, as de anexo que
não é PDF e a autoassinatura do despacho (SI-62), que continua como antes.
O CHECK exige as três juntas — meia posição não desenha nada e só confundiria.

`ADD COLUMN` herda RLS e grants da tabela; nada a repetir.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0147"
down_revision: str | Sequence[str] | None = "0146"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CK_COMPLETA = "ck_assinatura_anexo_selo_completo"
CK_FAIXA = "ck_assinatura_anexo_selo_faixa"


def upgrade() -> None:
    op.add_column(
        "assinatura_anexo",
        sa.Column("selo_pagina", sa.Integer(), nullable=True),
        schema="protocolos",
    )
    op.add_column(
        "assinatura_anexo",
        sa.Column("selo_x", sa.Float(), nullable=True),
        schema="protocolos",
    )
    op.add_column(
        "assinatura_anexo",
        sa.Column("selo_y", sa.Float(), nullable=True),
        schema="protocolos",
    )
    op.create_check_constraint(
        CK_COMPLETA,
        "assinatura_anexo",
        "(selo_pagina IS NULL AND selo_x IS NULL AND selo_y IS NULL) OR "
        "(selo_pagina IS NOT NULL AND selo_x IS NOT NULL AND selo_y IS NOT NULL)",
        schema="protocolos",
    )
    op.create_check_constraint(
        CK_FAIXA,
        "assinatura_anexo",
        "selo_pagina IS NULL OR "
        "(selo_pagina >= 1 AND selo_x BETWEEN 0 AND 1 AND selo_y BETWEEN 0 AND 1)",
        schema="protocolos",
    )


def downgrade() -> None:
    op.drop_constraint(CK_FAIXA, "assinatura_anexo", schema="protocolos", type_="check")
    op.drop_constraint(CK_COMPLETA, "assinatura_anexo", schema="protocolos", type_="check")
    op.drop_column("assinatura_anexo", "selo_y", schema="protocolos")
    op.drop_column("assinatura_anexo", "selo_x", schema="protocolos")
    op.drop_column("assinatura_anexo", "selo_pagina", schema="protocolos")
