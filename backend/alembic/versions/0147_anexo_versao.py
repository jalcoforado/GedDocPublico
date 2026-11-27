"""Versão nova de documento (SI-72, RF-04 V1): corrigir sem apagar o anterior.

Revision ID: 0147
Revises: 0146
Create Date: 2026-11-26

A versão nova é um `protocolos.anexo` NOVO que aponta para o que ela
substitui (`id_anexo_anterior`). Nada é apagado nem renumerado: a versão
anterior continua no processo, com a mesma posição e as mesmas folhas, e a
nova entra no fim, como qualquer juntada. Folha de processo administrativo não
se renumera; uma citação "fls. 70" feita num despacho tem de continuar
apontando para o mesmo papel.

- `versao`: 1 para tudo o que já existe; a nova é a anterior + 1.
- `motivo_versao`: o que mudou (opcional). Serve ao avaliador do RF-04 V2.
- Índice único parcial em `(tenant_id, id_anexo_anterior)`: cada versão tem
  no máximo UMA sucessora viva. Impede ramificar a partir de uma versão já
  substituída, inclusive com dois envios simultâneos.

Versão REDIGIDA no sistema: `protocolos.minuta.id_anexo_substitui` marca o
rascunho que, ao ser finalizado, vira a versão nova daquele anexo (em vez de
um documento avulso); `minuta.motivo_versao` guarda o "o que mudou" até lá.

Coluna nova em tabela existente herda RLS e grants (CLAUDE.md §Migrations);
tabelas legadas, como a 0142.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0147"
down_revision: str | Sequence[str] | None = "0146"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE protocolos.anexo
            ADD COLUMN id_anexo_anterior integer NULL
                REFERENCES protocolos.anexo (id),
            ADD COLUMN versao integer NOT NULL DEFAULT 1,
            ADD COLUMN motivo_versao varchar(1000) NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_anexo_sucessora_unica
            ON protocolos.anexo (tenant_id, id_anexo_anterior)
            WHERE id_anexo_anterior IS NOT NULL AND excluido = false
    """)
    op.execute("""
        ALTER TABLE protocolos.minuta
            ADD COLUMN id_anexo_substitui integer NULL
                REFERENCES protocolos.anexo (id),
            ADD COLUMN motivo_versao varchar(1000) NULL
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE protocolos.minuta
            DROP COLUMN IF EXISTS motivo_versao,
            DROP COLUMN IF EXISTS id_anexo_substitui
    """)
    op.execute("DROP INDEX IF EXISTS protocolos.ux_anexo_sucessora_unica")
    op.execute("""
        ALTER TABLE protocolos.anexo
            DROP COLUMN IF EXISTS motivo_versao,
            DROP COLUMN IF EXISTS versao,
            DROP COLUMN IF EXISTS id_anexo_anterior
    """)
