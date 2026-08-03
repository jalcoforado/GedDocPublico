"""SEC-01A (parte 2) — `aprimora_platform` grava a trilha visível ao município.

Revision ID: 0077
Revises: 0076
Create Date: 2026-08-01

A 0076 enumerou os grants cross-tenant do papel de plataforma: `tenant`,
`tenant_modulo`, `modulo`, `modulo_transacao`, `platform_principal` e
`platform_audit_log`. Faltava um, e só a parte 2 revelou qual: **`audit_log`**.

Por quê. A decisão **D-a** manda preservar a entrada que o *município* enxerga
quando a plataforma mexe no cadastro ou na contratação dele — sem ela, a
prefeitura perde o registro de que seu módulo foi contratado, e isso seria
regressão de comportamento dentro de um PR de segurança. Essa entrada mora em
`aprimora_py.audit_log`, tabela **municipal, com RLS FORCE**. Até a 0076, quem a
gravava era a sessão municipal rodando como `ged_user` (SUPERUSER/BYPASSRLS —
achado F-12): funcionava por contorno, não por permissão.

Com a fronteira de plataforma passando a usar `aprimora_platform`
(`NOBYPASSRLS`), a gravação precisa de duas coisas, e ambas são cumpridas:

1. **Grant** — este arquivo. `SELECT, INSERT`, nada além. Nunca `UPDATE`/
   `DELETE`: a trilha é append-only, e um papel que pode reescrever a trilha é
   um papel que pode apagar o próprio rastro. `SELECT` entra porque o INSERT do
   caminho de auditoria devolve colunas e porque a policy de leitura precisa
   ser exercível.
2. **`SET LOCAL app.tenant_id = <tenant ALVO>`** — em
   `app/database_plataforma.py::sessao_no_tenant_alvo`, aplicado por transação.
   Sem ele a policy `tenant_isolation_insert` (`WITH CHECK (tenant_id =
   current_setting('app.tenant_id'))`) nega o INSERT, que é o comportamento
   correto: a linha PERTENCE ao tenant alvo e tem de ser gravada como dele.

O grant sozinho não abre nada indevido — a RLS continua valendo, e é o que
limita o papel a escrever exatamente na linha do tenant que a operação declarou.

Nenhuma tabela nova, nenhum papel novo: `SEC-RLS-00B` é dono dos papéis
municipal, de worker e de DDL (ADR-016 §9.1).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0077"
down_revision: str | Sequence[str] | None = "0076"
branch_labels = None
depends_on = None
S = "aprimora_py"
ROLE = "aprimora_platform"


def upgrade() -> None:
    op.execute(f"GRANT SELECT, INSERT ON {S}.audit_log TO {ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON SEQUENCE {S}.audit_log_id_seq TO {ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE USAGE, SELECT ON SEQUENCE {S}.audit_log_id_seq FROM {ROLE}")
    op.execute(f"REVOKE SELECT, INSERT ON {S}.audit_log FROM {ROLE}")
