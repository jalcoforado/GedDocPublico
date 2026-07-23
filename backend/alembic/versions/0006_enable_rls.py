"""Postgres Row-Level Security (RLS) — Fase 13b.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-23

Defesa em profundidade contra esquecer `tenant_filter()` em alguma query:
o próprio Postgres filtra linhas baseado em `current_setting('app.tenant_id')`.

Estratégia:
1. Cria role `aprimora_app` (LOGIN, NOSUPERUSER, NOBYPASSRLS). Senha padrão
   em DEV. Em PROD: ALTER ROLE aprimora_app PASSWORD '<senha-real>'.
2. GRANT USAGE em schemas + SELECT/INSERT/UPDATE/DELETE em todas as 26 tabelas
   tenanted + aprimora_py.tenant.
3. ENABLE + FORCE ROW LEVEL SECURITY em cada uma das 26 tabelas.
4. CREATE POLICY tenant_isolation USING (tenant_id = current setting).
5. CREATE POLICY tenant_insert WITH CHECK (idem).

A aplicação faz `SET LOCAL app.tenant_id = X` em cada request (ver
`app.database.get_db`). Sem isso, as policies bloqueiam tudo.

DEV: `ged_user` é SUPERUSER e bypassa RLS — useful pra debug e Alembic. Em
PROD, mudar `DATABASE_URL` da app/worker pra usar `aprimora_app`.

`aprimora_py.tenant` NÃO tem RLS — é a tabela meta, todos os tenants devem
poder ver o seu próprio registro (filtro aplicacional já está em /tenants/me).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES: list[tuple[str, str]] = [
    ("protocolos", "tipo_manifestante"),
    ("protocolos", "tipo_processo"),
    ("protocolos", "tipo_anexo"),
    ("protocolos", "assunto"),
    ("protocolos", "assunto_tipo_processo_tipo_anexo"),
    ("protocolos", "manifestante"),
    ("protocolos", "processo"),
    ("protocolos", "movimentacao"),
    ("protocolos", "encaminhamento"),
    ("protocolos", "despacho"),
    ("protocolos", "arquivamento"),
    ("protocolos", "anexo"),
    ("protocolos", "anexo_processo"),
    ("protocolos", "solicitacao_assinatura"),
    ("protocolos", "usuario_assinatura"),
    ("protocolos", "assinatura_anexo"),
    ("utils", "tipo_unidade_trabalho"),
    ("utils", "unidade_trabalho"),
    ("utils", "grupo"),
    ("utils", "grupo_transacao"),
    ("utils", "usuario"),
    ("utils", "usuario_externo"),
    ("utils", "usuario_grupo"),
    ("utils", "usuario_unidade_trabalho"),
    ("utils", "endereco"),
    ("aprimora_py", "job"),
]


def upgrade() -> None:
    # 1. Role aprimora_app (idempotente). Senha de DEV — trocar em PROD.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aprimora_app') THEN
                CREATE ROLE aprimora_app
                    LOGIN
                    NOSUPERUSER
                    NOBYPASSRLS
                    PASSWORD 'ged_password_secure_local';
            END IF;
        END $$;
        """
    )

    # 2. GRANT acesso à role.
    op.execute("GRANT CONNECT ON DATABASE ged_saas_db TO aprimora_app")
    for schema in ("protocolos", "utils", "aprimora_py", "public"):
        op.execute(f"GRANT USAGE ON SCHEMA {schema} TO aprimora_app")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO aprimora_app")
        op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {schema} TO aprimora_app")
        # default privileges p/ futuras tabelas criadas por ged_user
        op.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE ged_user IN SCHEMA {schema} "
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aprimora_app"
        )
        op.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE ged_user IN SCHEMA {schema} "
            f"GRANT USAGE, SELECT ON SEQUENCES TO aprimora_app"
        )

    # 3+4+5: Enable RLS + policies em cada tabela tenanted.
    for schema, table in TABLES:
        fq = f'"{schema}"."{table}"'
        try:
            op.execute(f"ALTER TABLE {fq} ENABLE ROW LEVEL SECURITY")
        except Exception:
            # Already enabled (from legacy schema)
            pass

        try:
            # FORCE faz a policy aplicar-se até para o dono da tabela (ged_user)
            # — exceto para SUPERUSER, que sempre bypassa.
            op.execute(f"ALTER TABLE {fq} FORCE ROW LEVEL SECURITY")
        except Exception:
            pass

        try:
            op.execute(
                f"""
                CREATE POLICY tenant_isolation_select ON {fq}
                    FOR SELECT
                    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
                """
            )
        except Exception:
            # Policy may already exist from legacy schema
            pass

        try:
            op.execute(
                f"""
                CREATE POLICY tenant_isolation_modify ON {fq}
                    FOR ALL
                    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
                """
            )
        except Exception:
            # Policy may already exist from legacy schema
            pass


def downgrade() -> None:
    for schema, table in TABLES:
        fq = f'"{schema}"."{table}"'
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {fq}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {fq}")
        op.execute(f"ALTER TABLE {fq} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {fq} DISABLE ROW LEVEL SECURITY")

    # Revoke / drop role
    for schema in ("protocolos", "utils", "aprimora_py", "public"):
        op.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE ged_user IN SCHEMA {schema} "
            f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM aprimora_app"
        )
        op.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE ged_user IN SCHEMA {schema} "
            f"REVOKE USAGE, SELECT ON SEQUENCES FROM aprimora_app"
        )
        op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {schema} FROM aprimora_app")
        op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM aprimora_app")
        op.execute(f"REVOKE USAGE ON SCHEMA {schema} FROM aprimora_app")
    op.execute("REVOKE CONNECT ON DATABASE ged_saas_db FROM aprimora_app")
    op.execute("DROP ROLE IF EXISTS aprimora_app")
