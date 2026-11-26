"""aprimora_py.tenant — cor de destaque e cor da barra lateral (tema por município)

Revision ID: 0131
Revises: 0130
Create Date: 2026-10-08 18:00:00.000000

``cor_primaria`` existia desde a 0003, mas só tingia o painel do login: o
sistema inteiro seguia verde, qualquer que fosse o município. Com estas duas
colunas a identidade passa a ter três papéis, e o frontend deriva deles toda a
paleta (``frontend/lib/tema-cores.ts``):

- ``cor_primaria``  — marca: botões, links, foco;
- ``cor_destaque``  — acento: realces e o painel da cidade no login;
- ``cor_lateral``   — fundo da barra lateral.

As três são opcionais e independentes; a que faltar cai no padrão do produto.

**Com ``GRANT UPDATE`` por coluna para ``aprimora_app``**, ao contrário das
colunas da 0129/0130: estas são editadas pelo admin municipal em Configurações
(``PUT /tenants/me``), e desde a 0080 coluna nova de ``tenant`` nasce sem
``UPDATE`` para o runtime municipal. As duas entram também em
``COLUNAS_MUNICIPAIS_DE_TENANT`` — ``tests/test_grant_por_coluna_tenant.py``
reprova a divergência entre o grant, a constante e o schema.

O formato (``#RRGGBB``) é validado na borda (``TenantInstitucionalUpdate``) e
garantido aqui por CHECK: o valor vira CSS no navegador de todo usuário do
município, então não pode depender só de quem chama a API.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0131"
down_revision: str | Sequence[str] | None = "0130"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "aprimora_py"
APP = "aprimora_app"
_COLUNAS = ("cor_destaque", "cor_lateral")


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE {S}.tenant
            ADD COLUMN cor_destaque VARCHAR(7) NULL,
            ADD COLUMN cor_lateral VARCHAR(7) NULL,
            ADD CONSTRAINT ck_tenant_cor_destaque_hex
                CHECK (cor_destaque IS NULL OR cor_destaque ~ '^#[0-9A-Fa-f]{{6}}$'),
            ADD CONSTRAINT ck_tenant_cor_lateral_hex
                CHECK (cor_lateral IS NULL OR cor_lateral ~ '^#[0-9A-Fa-f]{{6}}$')
        """
    )
    op.execute(f"GRANT UPDATE ({', '.join(_COLUNAS)}) ON {S}.tenant TO {APP}")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({', '.join(_COLUNAS)}) ON {S}.tenant FROM {APP}")
    op.execute(
        f"""
        ALTER TABLE {S}.tenant
            DROP CONSTRAINT ck_tenant_cor_lateral_hex,
            DROP CONSTRAINT ck_tenant_cor_destaque_hex,
            DROP COLUMN cor_lateral,
            DROP COLUMN cor_destaque
        """
    )
