"""aprimora_py.tenant — fonte e cor dos títulos (tema por município)

Revision ID: 0132
Revises: 0131
Create Date: 2026-10-09 18:00:00.000000

Completa o tema da 0131 com o que ela deixou fixo: a tipografia e a cor dos
títulos.

- ``cor_titulos``   — cor dos títulos de página. Sem ela, vale o que valia: o
  título de tela na cor do texto e o do "Menu principal" na cor primária.
- ``fonte_titulos`` — a fonte dos títulos, escolhida numa LISTA FECHADA. Não é
  campo livre de propósito: cada fonte da lista é um arquivo hospedado no
  próprio frontend (``frontend/app/fonts/``), e um nome qualquer aqui seria
  uma fonte que o navegador não tem de onde tirar.

As duas são opcionais; a que faltar cai no padrão do produto.

**Com ``GRANT UPDATE`` por coluna para ``aprimora_app``**, como as da 0131 e
pelo mesmo motivo: são editadas pelo admin municipal em Configurações
(``PUT /tenants/me``), e desde a 0080 coluna nova de ``tenant`` nasce sem
``UPDATE`` para o runtime municipal. Entram também em
``COLUNAS_MUNICIPAIS_DE_TENANT`` — ``tests/test_grant_por_coluna_tenant.py``
reprova a divergência entre o grant, a constante e o schema.

Os dois valores viram CSS no navegador de todo usuário do município, então o
formato é garantido aqui por CHECK, e não só na borda
(``TenantInstitucionalUpdate``). A lista de fontes do CHECK tem de casar com
``FONTES_DE_TITULO`` em ``app/schemas/tenant.py`` e com ``FONTES`` em
``frontend/lib/tema-cores.ts``: fonte nova pede migration nova.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0132"
down_revision: str | Sequence[str] | None = "0131"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "aprimora_py"
APP = "aprimora_app"
_COLUNAS = ("cor_titulos", "fonte_titulos")
_FONTES = ("montserrat", "inter", "roboto_slab", "nunito")


def upgrade() -> None:
    fontes = ", ".join(f"'{f}'" for f in _FONTES)
    op.execute(
        f"""
        ALTER TABLE {S}.tenant
            ADD COLUMN cor_titulos VARCHAR(7) NULL,
            ADD COLUMN fonte_titulos VARCHAR(20) NULL,
            ADD CONSTRAINT ck_tenant_cor_titulos_hex
                CHECK (cor_titulos IS NULL OR cor_titulos ~ '^#[0-9A-Fa-f]{{6}}$'),
            ADD CONSTRAINT ck_tenant_fonte_titulos
                CHECK (fonte_titulos IS NULL OR fonte_titulos IN ({fontes}))
        """
    )
    op.execute(f"GRANT UPDATE ({', '.join(_COLUNAS)}) ON {S}.tenant TO {APP}")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({', '.join(_COLUNAS)}) ON {S}.tenant FROM {APP}")
    op.execute(
        f"""
        ALTER TABLE {S}.tenant
            DROP CONSTRAINT ck_tenant_fonte_titulos,
            DROP CONSTRAINT ck_tenant_cor_titulos_hex,
            DROP COLUMN fonte_titulos,
            DROP COLUMN cor_titulos
        """
    )
