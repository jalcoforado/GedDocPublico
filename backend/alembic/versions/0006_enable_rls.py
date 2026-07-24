"""Postgres Row-Level Security (RLS) — Fase 13b.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-23

Defesa em profundidade contra esquecer `tenant_filter()` em alguma query:
o próprio Postgres filtra linhas baseado em `current_setting('app.tenant_id')`.

Estratégia:
1. Cria role `aprimora_app` (LOGIN, NOSUPERUSER, NOBYPASSRLS). Senha padrão
   em DEV. Em PROD: ALTER ROLE aprimora_app PASSWORD '<senha-real>'.
2. GRANT USAGE em schemas + SELECT/INSERT/UPDATE/DELETE nas tabelas tenanted.
3. ENABLE + FORCE ROW LEVEL SECURITY em cada tabela que EXISTE e tem tenant_id.
4. CREATE POLICY tenant_isolation USING (tenant_id = current setting).

A aplicação faz `SET LOCAL app.tenant_id = X` em cada request (ver
`app.database.get_db`). Sem isso, as policies bloqueiam tudo.

DEV: `ged_user` é SUPERUSER e bypassa RLS — útil pra debug e Alembic. Em
PROD, mudar `DATABASE_URL` da app/worker pra usar `aprimora_app`.

ROBUSTEZ (2026-07): toda a lógica roda dentro de blocos `plpgsql DO` com
tratamento de exceção POR-STATEMENT (savepoint interno). Isso é essencial:
no Postgres, um comando que falha aborta a transação inteira — um `try/except`
Python NÃO contém o erro (a próxima instrução e o stamp do Alembic falhariam
com "current transaction is aborted"). Só o `BEGIN ... EXCEPTION` do plpgsql
cria savepoint e contém a falha. Tabelas ausentes ou sem `tenant_id` (o schema
legado filtrado não tem todas) são puladas silenciosamente.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Tabelas alvo de RLS (schema, tabela). Só recebem RLS as que existirem e
# tiverem coluna tenant_id — o loop plpgsql checa antes.
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


def _tables_sql_array() -> str:
    """Monta literal de array 2-D plpgsql: ARRAY[['s','t'],...]."""
    pairs = ",".join(f"['{s}','{t}']" for s, t in TABLES)
    return f"ARRAY[{pairs}]"


def upgrade() -> None:
    # 1. Role aprimora_app (idempotente).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aprimora_app') THEN
                CREATE ROLE aprimora_app
                    LOGIN NOSUPERUSER NOBYPASSRLS
                    PASSWORD 'ged_password_secure_local';
            END IF;
        END $$;
        """
    )

    # 2. GRANTs — cada statement com savepoint próprio (BEGIN/EXCEPTION).
    op.execute(
        """
        DO $$
        DECLARE sch text;
        BEGIN
            BEGIN EXECUTE 'GRANT CONNECT ON DATABASE ged_saas_db TO aprimora_app';
            EXCEPTION WHEN OTHERS THEN NULL; END;
            FOREACH sch IN ARRAY ARRAY['protocolos','utils','aprimora_py','public'] LOOP
                BEGIN EXECUTE format('GRANT USAGE ON SCHEMA %I TO aprimora_app', sch);
                EXCEPTION WHEN OTHERS THEN NULL; END;
                BEGIN EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO aprimora_app', sch);
                EXCEPTION WHEN OTHERS THEN NULL; END;
                BEGIN EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO aprimora_app', sch);
                EXCEPTION WHEN OTHERS THEN NULL; END;
                BEGIN EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE ged_user IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aprimora_app', sch);
                EXCEPTION WHEN OTHERS THEN NULL; END;
                BEGIN EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE ged_user IN SCHEMA %I GRANT USAGE, SELECT ON SEQUENCES TO aprimora_app', sch);
                EXCEPTION WHEN OTHERS THEN NULL; END;
            END LOOP;
        END $$;
        """
    )

    # 3+4. RLS + policies — só em tabelas que existem E têm tenant_id.
    op.execute(
        f"""
        DO $$
        DECLARE tbls text[][] := {_tables_sql_array()};
        DECLARE i int;
        DECLARE sch text; DECLARE tbl text; DECLARE fq text;
        BEGIN
            FOR i IN 1 .. array_length(tbls, 1) LOOP
                sch := tbls[i][1];
                tbl := tbls[i][2];
                CONTINUE WHEN to_regclass(format('%I.%I', sch, tbl)) IS NULL;
                CONTINUE WHEN NOT EXISTS (
                    SELECT 1 FROM information_schema.columns c
                    WHERE c.table_schema = sch AND c.table_name = tbl
                      AND c.column_name = 'tenant_id'
                );
                fq := format('%I.%I', sch, tbl);
                BEGIN
                    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', fq);
                    EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', fq);
                    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_select ON %s', fq);
                    EXECUTE format(
                        'CREATE POLICY tenant_isolation_select ON %s FOR SELECT '
                        'USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::int)',
                        fq
                    );
                    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_modify ON %s', fq);
                    EXECUTE format(
                        'CREATE POLICY tenant_isolation_modify ON %s FOR ALL '
                        'USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::int) '
                        'WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::int)',
                        fq
                    );
                EXCEPTION WHEN OTHERS THEN NULL;
                END;
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    # Remove policies + RLS de forma tolerante (pula tabelas ausentes).
    op.execute(
        f"""
        DO $$
        DECLARE tbls text[][] := {_tables_sql_array()};
        DECLARE i int; DECLARE sch text; DECLARE tbl text; DECLARE fq text;
        BEGIN
            FOR i IN 1 .. array_length(tbls, 1) LOOP
                sch := tbls[i][1]; tbl := tbls[i][2];
                CONTINUE WHEN to_regclass(format('%I.%I', sch, tbl)) IS NULL;
                fq := format('%I.%I', sch, tbl);
                BEGIN
                    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_modify ON %s', fq);
                    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_select ON %s', fq);
                    EXECUTE format('ALTER TABLE %s NO FORCE ROW LEVEL SECURITY', fq);
                    EXECUTE format('ALTER TABLE %s DISABLE ROW LEVEL SECURITY', fq);
                EXCEPTION WHEN OTHERS THEN NULL;
                END;
            END LOOP;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        DECLARE sch text;
        BEGIN
            FOREACH sch IN ARRAY ARRAY['protocolos','utils','aprimora_py','public'] LOOP
                BEGIN EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE ged_user IN SCHEMA %I REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM aprimora_app', sch);
                EXCEPTION WHEN OTHERS THEN NULL; END;
                BEGIN EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE ged_user IN SCHEMA %I REVOKE USAGE, SELECT ON SEQUENCES FROM aprimora_app', sch);
                EXCEPTION WHEN OTHERS THEN NULL; END;
                BEGIN EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA %I FROM aprimora_app', sch);
                EXCEPTION WHEN OTHERS THEN NULL; END;
                BEGIN EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM aprimora_app', sch);
                EXCEPTION WHEN OTHERS THEN NULL; END;
                BEGIN EXECUTE format('REVOKE USAGE ON SCHEMA %I FROM aprimora_app', sch);
                EXCEPTION WHEN OTHERS THEN NULL; END;
            END LOOP;
            BEGIN EXECUTE 'REVOKE CONNECT ON DATABASE ged_saas_db FROM aprimora_app';
            EXCEPTION WHEN OTHERS THEN NULL; END;
            BEGIN EXECUTE 'DROP ROLE IF EXISTS aprimora_app';
            EXCEPTION WHEN OTHERS THEN NULL; END;
        END $$;
        """
    )
